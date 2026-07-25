import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, List, Optional
from src.middleware import AppError
from src.config import prisma
from prisma import Json as PrismaJson
from ..utils import sanitize_json, substitute_path_params
from ..schema import (
    ProjectResponse,
    ProjectMetaResponse,
    CreateProjectRequest,
    UpdateProjectRequest,
)

logger = logging.getLogger(__name__)

async def verify_project_access(project_id: str, user: dict):
    system_role = user.get("systemRole")
    tenant_id = user.get("tenantId")
    user_id = user.get("userId")

    project = await prisma.project.find_unique(where={"id": project_id})
    if not project:
        raise AppError("Project not found", status_code=404)

    if system_role not in {"SUPER_ADMIN", "TENANT_ADMIN"}:
        if not user_id:
            raise AppError("User ID is required for project access verification", status_code=401)
        membership = await prisma.projectmember.find_unique(
            where={"projectId_userId": {
                "projectId": project_id,
                "userId": user_id
            }}
        )
        if not membership:
            raise AppError("Access denied to this project", status_code=403)
    elif system_role == "TENANT_ADMIN" and project.tenantId != tenant_id:
        raise AppError("Access denied to this tenant's project", status_code=403)

    return project

async def create_project(tenant_id: str, data: CreateProjectRequest) -> ProjectResponse:
    """
    Create a new project within a workspace.
    Enforces plan limits on project count.
    """
    subscription = await prisma.subscription.find_first(
        where={"tenantId": tenant_id},
        include={"plan": True}
    )
    
    if not subscription or not subscription.plan:
        raise AppError("No active subscription found. Please contact support.", status_code=403)
    
    existing_projects_count = await prisma.project.count(
        where={"tenantId": tenant_id}
    )
    
    max_projects = subscription.plan.maxProjects
    
    if existing_projects_count >= max_projects:
        raise AppError(
            f"Project limit reached. Your current plan allows {max_projects} project(s). "
            f"Please upgrade your subscription to create more projects.",
            status_code=403
        )
    
    workspace = await prisma.workspace.find_first(
        where={
            "id": data.workspaceId,
            "tenantId": tenant_id
        }
    )
    
    workspace_id = data.workspaceId
    
    if not workspace:
        logger.warning(f"Workspace {data.workspaceId} not found or not associated with tenant {tenant_id}. Falling back to default.")
        default_workspace = await prisma.workspace.find_first(
            where={"tenantId": tenant_id},
            order={"createdAt": "asc"}
        )
        if not default_workspace:
            raise AppError(f"No workspace found for tenant {tenant_id}", status_code=404)
        workspace_id = default_workspace.id

    project = await prisma.project.create(
        data={
            "tenantId": tenant_id,
            "workspaceId": workspace_id,
            "name": data.name,
            "description": data.description
        }
    )
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        workspaceId=project.workspaceId,
        tenantId=project.tenantId,
        createdAt=project.createdAt,
        updatedAt=project.updatedAt
    )

async def get_workspace_projects(tenant_id: str = None, workspace_id: str = None, user_id: str = None, is_admin: bool = False) -> List[ProjectResponse]:
    where_clause = {
        "workspaceId": workspace_id
    }
    
    if tenant_id:
        where_clause["tenantId"] = tenant_id
    
    if not is_admin and user_id:
        where_clause["members"] = {
            "some": {
                "userId": user_id
            }
        }

    projects = await prisma.project.find_many(
        where=where_clause,
        order={"createdAt": "desc"}
    )
    return [
        ProjectResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            workspaceId=p.workspaceId,
            tenantId=p.tenantId,
            createdAt=p.createdAt,
            updatedAt=p.updatedAt
        ) for p in projects
    ]

async def get_project_meta_service(project_id: str, user: dict, spec_store: dict, base_url_store: dict, spec_name_store: dict):
    project = await verify_project_access(project_id, user)

    has_spec = project_id in spec_store
    base_url_from_store = base_url_store.get(project_id)

    db_spec = None
    if not has_spec:
        db_spec = await prisma.apispec.find_first(
            where={"projectId": project_id},
            order={"createdAt": "desc"},
        )
        if db_spec:
            has_spec = True

    endpoints_count = await prisma.endpoint.count(where={"projectId": project_id})
    test_suites_count = await prisma.testsuite.count(where={"projectId": project_id})
    test_runs_count = await prisma.testrun.count(where={"projectId": project_id})

    test_runs = await prisma.testrun.find_many(
        where={"projectId": project_id},
        order={"createdAt": "desc"},
    )

    tests_run = sum(r.passed + r.failed for r in test_runs)
    tests_passed = sum(r.passed for r in test_runs)
    tests_failed = sum(r.failed for r in test_runs)

    last_run_obj = None
    last_run_at = None
    if test_runs:
        def _status_name(run: Any) -> str:
            st = getattr(run, "status", None)
            if hasattr(st, "value"):
                return str(st.value)
            if hasattr(st, "name"):
                return str(st.name)
            return str(st) if st is not None else ""

        latest_finished = next(
            (
                r
                for r in test_runs
                if _status_name(r).upper() in ("COMPLETED", "FAILED")
            ),
            None,
        )
        latest = latest_finished or test_runs[0]

        last_dt = getattr(latest, "completedAt", None) or getattr(latest, "createdAt", None)
        last_run_at = last_dt.isoformat() if last_dt else None
        last_run_obj = {
            "executedAt": last_run_at,
            "summary": {
                "total": (latest.passed or 0) + (latest.failed or 0),
                "passed": latest.passed or 0,
                "failed": latest.failed or 0,
            },
        }

    spec_name = spec_name_store.get(project_id)
    if not spec_name and db_spec:
        spec_name = db_spec.file_url or "spec"
    spec_info = None
    if has_spec:
        spec_info = {
            "originalName": spec_name or "swagger.json",
            "baseUrl": base_url_from_store or project.baseUrl,
        }

    project_category_summary = {}

    all_cases = await prisma.testcase.find_many(where={"projectId": project_id, "isActive": True})
    active_case_ids = set()
    for tc in all_cases:
        try:
            active_case_ids.add(tc.id)
        except Exception:
            pass
        cat = tc.category
        if hasattr(cat, "value"):
            cat = str(cat.value)
        else:
            cat = str(cat)

        if cat not in project_category_summary:
            project_category_summary[cat] = {"total": 0, "passed": 0, "failed": 0}

        project_category_summary[cat]["total"] += 1

    project_results = await prisma.testresult.find_many(
        where={"run": {"projectId": project_id}},
        order={"executedAt": "desc"},
    )

    seen_test_cases = set()
    for r in project_results:
        tc_id = r.testCaseId
        if active_case_ids and tc_id not in active_case_ids:
            continue

        if tc_id in seen_test_cases:
            continue
        seen_test_cases.add(tc_id)

        cat = r.category or "FUNCTIONAL"
        if hasattr(cat, "value"):
            cat = cat.value
        else:
            cat = str(cat)

        if cat not in project_category_summary:
            project_category_summary[cat] = {"total": 0, "passed": 0, "failed": 0}

        status = r.status.name if hasattr(r.status, "name") else str(r.status)
        if status == "PASSED":
            project_category_summary[cat]["passed"] += 1
        elif status == "FAILED":
            project_category_summary[cat]["failed"] += 1

    # Resolve effective baseUrl: explicit store/project > spec servers[0].url > None
    effective_base_url = base_url_from_store or project.baseUrl
    if not effective_base_url:
        # Try to extract from the parsed OpenAPI spec's servers field
        spec_obj = None
        if db_spec and db_spec.parsed_spec:
            spec_obj = db_spec.parsed_spec if isinstance(db_spec.parsed_spec, dict) else None
            if spec_obj is None:
                try:
                    spec_obj = json.loads(db_spec.parsed_spec)
                except Exception:
                    pass
        if spec_obj and isinstance(spec_obj.get("servers"), list) and spec_obj["servers"]:
            first_server = spec_obj["servers"][0]
            if isinstance(first_server, dict) and first_server.get("url"):
                effective_base_url = str(first_server["url"]).rstrip("/")

    return ProjectMetaResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        workspaceId=project.workspaceId,
        tenantId=project.tenantId or "",
        createdAt=project.createdAt,
        updatedAt=project.updatedAt,
        hasSpec=has_spec,
        spec=spec_info,
        lastRun=last_run_obj,
        baseUrl=effective_base_url,
        testsRun=tests_run,
        testsPassed=tests_passed,
        testsFailed=tests_failed,
        categorySummary=project_category_summary,
        endpointsCount=endpoints_count,
        testSuitesCount=test_suites_count,
        testRunsCount=test_runs_count,
        lastRunAt=last_run_at,
    )
