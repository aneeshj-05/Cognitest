import logging
import json
import re
from typing import Any, cast, List, TYPE_CHECKING
from fastapi import HTTPException
from src.config import prisma

# NOTE: Runtime `prisma` exports `Json`, but its type stubs may not.
# Keep runtime behavior while making Pyright/Pylance happy.
if TYPE_CHECKING:
    def PrismaJson(value: Any) -> Any: ...
else:
    from prisma import Json as PrismaJson
from .schema import CreateProjectRequest, ProjectResponse

logger = logging.getLogger(__name__)

async def create_project(tenant_id: str, data: CreateProjectRequest) -> ProjectResponse:
    """
    Create a new project within a workspace.
    Enforces plan limits on project count.
    """
    # Check subscription and plan limits
    subscription = await prisma.subscription.find_first(
        where={"tenantId": tenant_id},
        include={"plan": True}
    )
    
    if not subscription or not subscription.plan:
        raise ValueError("No active subscription found. Please contact support.")
    
    # Count existing projects for this tenant
    existing_projects_count = await prisma.project.count(
        where={"tenantId": tenant_id}
    )
    
    max_projects = subscription.plan.maxProjects
    
    # Check if limit is reached
    if existing_projects_count >= max_projects:
        raise ValueError(
            f"Project limit reached. Your current plan allows {max_projects} project(s). "
            f"Please upgrade your subscription to create more projects."
        )
    
    # Verify the workspace exists and belongs to the tenant
    workspace = await prisma.workspace.find_first(
        where={
            "id": data.workspaceId,
            "tenantId": tenant_id
        }
    )
    
    workspace_id = data.workspaceId
    
    if not workspace:
        logger.warning(f"Workspace {data.workspaceId} not found or not associated with tenant {tenant_id}. Falling back to default.")
        # Fallback to the first workspace of the tenant
        default_workspace = await prisma.workspace.find_first(
            where={"tenantId": tenant_id},
            order={"createdAt": "asc"}
        )
        if not default_workspace:
            raise ValueError(f"No workspace found for tenant {tenant_id}")
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

async def get_workspace_projects(
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    user_id: str | None = None,
    is_admin: bool = False,
) -> List[ProjectResponse]:
    """
    Get all projects for a specific workspace.
    If tenant_id is provided, filter by it.
    If user is not an admin, only return projects where they are a member.
    """
    where_clause: dict[str, Any] = {
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
        where=cast(Any, where_clause),
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

async def verify_project_access(project_id: str, user: dict):
    """
    Verify if the user has access to a project.
    """
    system_role = user.get("systemRole")
    tenant_id = user.get("tenantId")
    user_id = user.get("userId")

    project = await prisma.project.find_unique(where={"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if system_role not in {"SUPER_ADMIN", "TENANT_ADMIN"}:
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID is required for project access verification")
        membership = await prisma.projectmember.find_unique(
            where={"projectId_userId": {
                "projectId": project_id,
                "userId": user_id
            }}
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied to this project")
    elif system_role == "TENANT_ADMIN" and project.tenantId != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied to this tenant's project")

    return project

def contract_allowed_status(expected_statuses_str: str, actual: int, kind: str) -> bool:
    """
    Check if the actual status code is allowed given the expected statuses.
    """
    if not expected_statuses_str:
        return True

    if isinstance(expected_statuses_str, list):
        expected = {str(s).strip() for s in expected_statuses_str}
    else:
        expected = {s.strip() for s in str(expected_statuses_str).split(",")}

    STANDARD_ERROR_STATUSES = {400, 401, 403, 404, 405, 409, 415, 422, 429}

    if "default" in expected:
        if 500 <= actual <= 599:
            return True

    if kind.startswith("negative"):
        if kind == "negative_auth_missing":
            return actual in (401, 403)
        return actual in STANDARD_ERROR_STATUSES

    if str(actual) in expected:
        return True

    for s in expected:
        if s.isdigit() and int(s) // 100 == actual // 100:
            return True
        if len(s) == 3 and s[1:] == "xx" and s[0].isdigit() and int(s[0]) == actual // 100:
            return True

    return False

def sanitize_json(data):
    """Force-sanitize data through JSON roundtrip and wrap with PrismaJson."""
    if data is None:
        return None
    try:
        clean = json.loads(json.dumps(data, default=str))
        return PrismaJson(clean)
    except (TypeError, ValueError):
        return None

def substitute_path_params(path_template: str, path_params: dict[str, Any] | None) -> str:
    rendered = (path_template or "/")
    for k, v in (path_params or {}).items():
        rendered = rendered.replace("{" + str(k) + "}", str(v))

    rendered = re.sub(r"\{([a-zA-Z0-9_-]+)\}", r"{{\1}}", rendered)
    return rendered

def extract_contract_meta(case: dict[str, Any]) -> dict[str, Any]:
    """Best-effort extraction of strict contract metadata."""
    meta: dict[str, Any] = {}

    if isinstance(case.get("expected_statuses"), list):
        meta["expected_statuses"] = case.get("expected_statuses")
    if "security_required" in case:
        meta["security_required"] = bool(case.get("security_required"))
    if "auth_negative" in case:
        meta["auth_negative"] = bool(case.get("auth_negative"))
    if "kind" in case:
        meta["kind"] = case.get("kind")
    if "operation_key" in case:
        meta["operation_key"] = case.get("operation_key")

    assertions = case.get("assertions")
    if isinstance(assertions, list):
        for a in assertions:
            if not isinstance(a, str):
                continue
            if a.startswith("__contract_meta__="):
                try:
                    meta.update(json.loads(a.split("=", 1)[1]))
                except Exception:
                    pass
                break

    return meta
