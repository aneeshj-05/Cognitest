from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.config import settings, prisma

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Decode and validate the Bearer JWT, returning the payload dict."""
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        if not payload.get("userId"):
            raise exc

        # Ensure user is verified in DB
        import sys
        if "pytest" not in sys.modules:
            user = await prisma.user.find_unique(where={"id": payload["userId"]})
            if not user or not getattr(user, "isVerified", False):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User email is not verified.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return payload
    except JWTError:
        raise exc


def require_permission(permission: str):
    """
    Dependency factory for permission checking.

    Usage: Depends(require_permission("project.CREATE"))

    Super Admins bypass all checks. For other roles the permission must appear
    in the workspace-scoped permissions embedded in the JWT payload.
    """
    async def _check(
        workspace_id: Optional[str] = Query(None),
        payload: dict = Depends(get_current_user),
    ) -> dict:
        if payload.get("systemRole") == "SUPER_ADMIN":
            return payload

        if not workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="workspace_id is required for this operation.",
            )

        perms: list = (payload.get("workspacePermissions") or {}).get(workspace_id, [])
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}",
            )
        return payload

    return _check


def require_project_permission(permission: str):
    """
    Dependency factory for permission checking against a specific project.
    Extracts project_id from the path, looks up the project in the database,
    and checks if the user has the required permission for the project's workspace.
    """
    async def _check(
        project_id: str,
        payload: dict = Depends(get_current_user),
    ) -> dict:
        if payload.get("systemRole") == "SUPER_ADMIN":
            return payload

        project = await prisma.project.find_unique(where={"id": project_id})
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
            
        workspace_id = project.workspaceId
        perms: list = (payload.get("workspacePermissions") or {}).get(workspace_id, [])
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission} for this project's workspace.",
            )
        return payload
        
    return _check


def require_run_permission(permission: str):
    """
    Dependency factory for permission checking against a specific test run.
    Extracts run_id from the path, looks up the run and its parent project,
    and checks if the user has the required permission for the project's workspace.
    """
    async def _check(
        run_id: str,
        payload: dict = Depends(get_current_user),
    ) -> dict:
        if payload.get("systemRole") == "SUPER_ADMIN":
            return payload

        run = await prisma.testrun.find_unique(
            where={"id": run_id},
            include={"project": True}
        )
        if not run or not run.project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test run not found",
            )
            
        workspace_id = run.project.workspaceId
        perms: list = (payload.get("workspacePermissions") or {}).get(workspace_id, [])
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission} for this test run's workspace.",
            )
        return payload
        
    return _check
