"""
Generation router.

POST /{project_id}/generate-tests
  - Rule-based (use_ai=False): runs synchronously, returns 200 + results immediately
    (rule-based generation is fast — typically < 1 s).
  - AI-enhanced (use_ai=True): creates a GenerationJob row, enqueues an ARQ
    background task, returns 202 Accepted with {job_id} immediately.
    Frontend polls GET /{project_id}/generation-jobs/{job_id} for status.

GET /{project_id}/generation-jobs/{job_id}
  - Returns current status, progress, and result once completed.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from prisma import Json as PrismaJson
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any

from src.config.database import prisma
from src.middleware.auth_middleware import get_current_user
from ..schema import GenerateTestsRequest, GenerateTestsResponse
from ..services import generation_service, project_service
from ..state import _spec_store, _base_url_store, _draft_store, _gen_meta_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["Generation"])


# ── Response schemas ──────────────────────────────────────────────────────────

class JobAcceptedResponse(BaseModel):
    job_id: str
    status: str = "pending"
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    project_id: str
    test_type: str
    status: str         # pending | running | completed | failed | partial
    progress: int
    total: int
    suite_id: str | None = None
    result: Any | None = None
    error: str | None = None
    created_at: str
    updated_at: str


# ── POST generate-tests ───────────────────────────────────────────────────────

@router.post("/{project_id}/generate-tests")
async def generate_tests(
    project_id: str,
    data: GenerateTestsRequest,
    user: dict = Depends(get_current_user),
):
    """
    Start test generation.

    - use_ai=False → synchronous, returns GenerateTestsResponse (200)
    - use_ai=True  → async job, returns JobAcceptedResponse (202)
    """
    await project_service.verify_project_access(project_id, user)

    # ── Rule-based: stay synchronous (fast path) ──────────────────────────
    if not data.use_ai:
        result = await generation_service.generate_project_tests(
            project_id, data, _spec_store, _base_url_store, _draft_store, _gen_meta_store
        )
        return result

    # ── AI path: enqueue background job ──────────────────────────────────
    # Resolve total endpoint count for progress tracking
    total_endpoints = await _count_spec_endpoints(project_id, data)

    # Create GenerationJob row
    params_dict = data.model_dump(mode="json")
    params_dict["_total_endpoints"] = total_endpoints

    job = await prisma.generationjob.create(
        data={
            "project":   {"connect": {"id": project_id}},
            "testType":  data.test_type,
            "useAi":     True,
            "status":    "pending",
            "progress":  0,
            "total":     total_endpoints,
            "params":    PrismaJson(params_dict),
        }
    )

    # Enqueue ARQ task — if Redis unavailable, fall back to synchronous execution
    try:
        from src.worker.redis_client import get_redis_pool
        pool = await get_redis_pool()
        await pool.enqueue_job(
            "run_generation_task",
            job_id=job.id,
            project_id=project_id,
            params=params_dict,
        )
        logger.info("[JOB] Enqueued job %s for project %s (%s)", job.id, project_id, data.test_type)

        return JSONResponse(
            status_code=202,
            content={
                "job_id":  job.id,
                "status":  "pending",
                "message": f"AI generation started. Poll GET /projects/{project_id}/generation-jobs/{job.id} for status.",
            },
        )

    except Exception as exc:
        # Redis unavailable — run synchronously and return result directly
        logger.warning("[JOB] Redis unavailable (%s) — running AI generation synchronously", exc)
        await prisma.generationjob.update(
            where={"id": job.id},
            data={"status": "running"},
        )
        try:
            result = await generation_service.generate_project_tests(
                project_id, data, _spec_store, _base_url_store, _draft_store, _gen_meta_store
            )
            await prisma.generationjob.update(
                where={"id": job.id},
                data={"status": "completed", "suiteId": result.suite_id},
            )
            return result
        except Exception as gen_exc:
            await prisma.generationjob.update(
                where={"id": job.id},
                data={"status": "failed", "error": str(gen_exc)[:2000]},
            )
            raise


# ── GET job status ────────────────────────────────────────────────────────────

@router.get("/{project_id}/generation-jobs/{job_id}", response_model=JobStatusResponse)
async def get_generation_job(
    project_id: str,
    job_id: str,
    user: dict = Depends(get_current_user),
):
    """Poll the status of an async AI generation job."""
    await project_service.verify_project_access(project_id, user)

    job = await prisma.generationjob.find_unique(where={"id": job_id})
    if not job or job.projectId != project_id:
        raise HTTPException(status_code=404, detail="Generation job not found")

    return JobStatusResponse(
        job_id=job.id,
        project_id=job.projectId,
        test_type=job.testType,
        status=job.status,
        progress=job.progress,
        total=job.total,
        suite_id=job.suiteId,
        result=job.result,
        error=job.error,
        created_at=job.createdAt.isoformat(),
        updated_at=job.updatedAt.isoformat(),
    )


# ── GET all jobs for a project ────────────────────────────────────────────────

@router.get("/{project_id}/generation-jobs")
async def list_generation_jobs(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """List all generation jobs for a project (newest first)."""
    await project_service.verify_project_access(project_id, user)

    jobs = await prisma.generationjob.find_many(
        where={"projectId": project_id},
        order={"createdAt": "desc"},
        take=20,
    )
    return [
        {
            "job_id":     j.id,
            "test_type":  j.testType,
            "status":     j.status,
            "progress":   j.progress,
            "total":      j.total,
            "suite_id":   j.suiteId,
            "created_at": j.createdAt.isoformat(),
        }
        for j in jobs
    ]


# ── Helper ────────────────────────────────────────────────────────────────────

async def _count_spec_endpoints(project_id: str, data: GenerateTestsRequest) -> int:
    """Estimate total endpoint count from the stored spec for progress tracking."""
    try:
        spec_id = getattr(data, "spec_id", None)
        api_spec = None
        if spec_id:
            api_spec = await prisma.apispec.find_unique(where={"id": spec_id})
        if not api_spec:
            api_spec = await prisma.apispec.find_first(
                where={"projectId": project_id},
                order={"createdAt": "desc"},
            )
        if not api_spec or not api_spec.parsed_spec:
            return 0
        spec = api_spec.parsed_spec if isinstance(api_spec.parsed_spec, dict) else json.loads(api_spec.parsed_spec)
        paths = spec.get("paths") or {}
        count = sum(
            sum(1 for m in methods if m.lower() in ("get","post","put","patch","delete"))
            for methods in paths.values()
            if isinstance(methods, dict)
        )
        return max(count, 1)
    except Exception:
        return 0


# ── GET token budget ──────────────────────────────────────────────────────────

@router.get("/{project_id}/token-budget")
async def get_token_budget(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Return remaining AI token budget for the tenant that owns this project."""
    await project_service.verify_project_access(project_id, user)

    proj = await prisma.project.find_unique(where={"id": project_id})
    tenant_id = (proj.tenantId or "") if proj else ""

    from src.modules.generator.ai.token_manager import token_manager, _FREE_DEFAULT_LIMIT
    remaining = await token_manager.get_remaining_budget(tenant_id)
    limit     = await _get_plan_limit_for_response(tenant_id)

    return {
        "tenant_id":       tenant_id,
        "remaining_tokens": remaining,          # -1 = unlimited
        "monthly_limit":    limit,              # -1 = unlimited
        "unlimited":        remaining == -1,
    }


async def _get_plan_limit_for_response(tenant_id: str) -> int:
    """Return the plan's monthly token limit (exposed in budget endpoint)."""
    from src.modules.generator.ai.token_manager import _get_plan_limit
    return await _get_plan_limit(tenant_id)
