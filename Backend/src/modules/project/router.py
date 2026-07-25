from fastapi import APIRouter
from .routers import (
    project_router,
    spec_router,
    member_router,
    generation_router,
    test_case_router,
    run_router,
)
from .state import (
    _draft_store,
    _spec_store,
    _spec_name_store,
    _base_url_store,
    _gen_meta_store,
    _run_results_store,
    _results_store,
    _generation_meta
)

router = APIRouter()

# Include sub-routers
router.include_router(project_router)
router.include_router(spec_router)
router.include_router(member_router)
router.include_router(generation_router)
router.include_router(test_case_router)
router.include_router(run_router)

# Legacy exports for compatibility
__all__ = [
    "router",
    "_draft_store",
    "_spec_store",
    "_spec_name_store",
    "_base_url_store",
    "_gen_meta_store",
    "_run_results_store",
    "_results_store",
    "_generation_meta"
]
