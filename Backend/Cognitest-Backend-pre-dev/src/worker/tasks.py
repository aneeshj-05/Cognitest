"""
ARQ background tasks for AI test generation.

Each task receives the job_id and generation parameters, runs the full
AI generation pipeline, and updates GenerationJob status/progress in DB.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from arq import ArqRedis
from prisma import Prisma, Json as PrismaJson

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper: update job row atomically
# ---------------------------------------------------------------------------

async def _update_job(db: Prisma, job_id: str, **fields) -> None:
    try:
        await db.generationjob.update(where={"id": job_id}, data=fields)
    except Exception as exc:
        logger.warning("[ARQ] Could not update job %s: %s", job_id, exc)


# ---------------------------------------------------------------------------
# Main generation task
# ---------------------------------------------------------------------------

async def run_generation_task(
    ctx: dict[str, Any],
    *,
    job_id: str,
    project_id: str,
    params: dict[str, Any],
) -> None:
    """
    ARQ task: run AI test generation and persist results.

    Progress is updated after every endpoint's AI call completes
    (uses the natural per-endpoint batch boundary in functional_generator_ai).
    """
    from src.config.database import connect_db, disconnect_db, prisma
    from src.modules.project.services.generation_service import generate_project_tests
    from src.modules.project.schema import GenerateTestsRequest
    from src.modules.project.state import _spec_store, _base_url_store, _draft_store, _gen_meta_store

    # Connect DB inside the worker process
    await connect_db()

    try:
        await _update_job(prisma, job_id, status="running")

        # Reconstruct request object from serialised params
        # Strip internal tracking keys before passing to the schema
        req_params = {k: v for k, v in params.items() if not k.startswith("_")}
        req = GenerateTestsRequest(**req_params)

        # Monkey-patch the AI client to push progress updates
        # We wrap the per-endpoint call in functional_generator_ai to increment
        # progress after each endpoint completes.
        _patch_progress_callback(prisma, job_id, project_id, params)

        result = await generate_project_tests(
            project_id=project_id,
            data=req,
            spec_store=_spec_store,
            base_url_store=_base_url_store,
            draft_store=_draft_store,
            gen_meta_store=_gen_meta_store,
        )

        # Store final result (just summary — full cases are in DB)
        summary = {
            "project_id":        result.project_id,
            "test_type":         result.test_type,
            "count":             result.count,
            "suite_id":          result.suite_id,
            "generation_method": result.generation_method,
            "base_url":          result.base_url,
        }
        await _update_job(
            prisma, job_id,
            status="completed",
            progress=params.get("_total_endpoints", 0),
            result=PrismaJson(summary),
            suiteId=result.suite_id,
        )
        logger.info("[ARQ] Job %s completed — %d cases", job_id, result.count)

    except Exception as exc:
        logger.exception("[ARQ] Job %s failed: %s", job_id, exc)
        await _update_job(prisma, job_id, status="failed", error=str(exc)[:2000])

    finally:
        await disconnect_db()


# ---------------------------------------------------------------------------
# Progress callback injection
# ---------------------------------------------------------------------------

def _patch_progress_callback(
    db: Prisma,
    job_id: str,
    project_id: str,
    params: dict,
) -> None:
    """
    Wrap functional_generator_ai._process_single_endpoint to increment
    GenerationJob.progress after each endpoint completes.
    This uses the natural per-endpoint call boundary as the progress unit.
    """
    import asyncio
    import src.modules.generator.ai.generators.functional_generator_ai as fg

    original = fg._process_single_endpoint

    async def _wrapped(*args, **kwargs):
        result = await original(*args, **kwargs)
        # Fire-and-forget DB progress update (don't block the generation)
        asyncio.create_task(_increment_progress(db, job_id))
        return result

    fg._process_single_endpoint = _wrapped


async def _increment_progress(db: Prisma, job_id: str) -> None:
    try:
        job = await db.generationjob.find_unique(where={"id": job_id})
        if job:
            await db.generationjob.update(
                where={"id": job_id},
                data={"progress": job.progress + 1},
            )
    except Exception:
        pass  # Progress update failure is non-fatal
