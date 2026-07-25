"""
ARQ worker entry point.

Start with:
    uv run arq src.worker.main.WorkerSettings

Scale with:
    # Run N concurrent worker processes (each handles concurrent async tasks)
    for i in $(seq 1 4); do uv run arq src.worker.main.WorkerSettings & done
Or via Docker Compose:
    docker compose up --scale worker=4
"""
from __future__ import annotations

import logging
import os
from typing import Any

from arq.connections import RedisSettings

from src.worker.tasks import run_generation_task

logger = logging.getLogger(__name__)


def _redis_settings() -> RedisSettings:
    from src.config.settings import settings
    url = settings.redis_url
    # Parse redis://[:password@]host[:port][/db]
    url = url.replace("redis://", "")
    host = "localhost"
    port = 6379
    password = None
    db = 0
    if "@" in url:
        password, url = url.rsplit("@", 1)
    if "/" in url:
        url, db_str = url.rsplit("/", 1)
        try:
            db = int(db_str)
        except ValueError:
            pass
    if ":" in url:
        host, port_str = url.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            pass
    else:
        host = url or "localhost"
    # Force IPv4 — on Windows, "localhost" resolves to IPv6 (::1) first
    # but Redis binds to 127.0.0.1 (IPv4) only by default.
    if host in ("localhost", "LOCALHOST"):
        host = "127.0.0.1"
    return RedisSettings(host=host, port=port, password=password, database=db)


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [run_generation_task]
    redis_settings = _redis_settings()

    # Each worker handles up to 10 concurrent async tasks.
    # AI calls are I/O-bound so high concurrency is fine per worker.
    max_jobs = 10

    # Retry failed jobs once after 30 s
    retry_jobs = True
    max_tries = 2

    on_startup = None
    on_shutdown = None

    job_timeout = 600  # 10 min max per job
    keep_result = 3600  # keep result in Redis for 1 hour (DB is the real store)
