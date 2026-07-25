from fastapi import APIRouter

from .health import router as health_router
from .dashboard import router as dashboard_router
from .gateway import router as gateway_router
from src.modules.auth.router import router as auth_router
from src.modules.workspace.router import router as workspace_router
from src.modules.project.router import router as projects_router
from src.modules.test.router import router as runs_router
from src.modules.roles.router import router as roles_router
from src.modules.generator.router import router as generator_router, contract_router
from src.modules.super_admin.router import router as super_admin_router
from src.modules.support.router import router as support_router
from src.modules.invitation.router import router as invitation_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(workspace_router)
api_router.include_router(projects_router)
api_router.include_router(runs_router)
api_router.include_router(roles_router)
api_router.include_router(generator_router)
api_router.include_router(gateway_router)
api_router.include_router(dashboard_router)
api_router.include_router(super_admin_router)
api_router.include_router(support_router)
api_router.include_router(invitation_router)
api_router.include_router(contract_router, prefix="/contract", tags=["Contract"])

__all__ = ["api_router"]

