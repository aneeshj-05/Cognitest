"""
Dashboard & Reports API endpoints.

Provides aggregated statistics from the database for the frontend dashboard
and reports views via the DashboardService.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from src.middleware.auth_middleware import get_current_user
from src.services.dashboard_service import DashboardService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    """
    Aggregated dashboard statistics scoped to the calling user's access level.
    """
    return await DashboardService.get_dashboard_stats(user)


@router.get("/reports")
async def get_reports(user: dict = Depends(get_current_user)):
    """
    Returns a list of test runs formatted as reports for the reports page.
    """
    return await DashboardService.get_reports(user)


@router.get("/reports/{run_id}")
async def get_report_detail(run_id: str, user: dict = Depends(get_current_user)):
    """
    Detailed report for a single test run, including full test results.
    """
    try:
        report = await DashboardService.get_report_detail(run_id, user)
        if not report:
            raise HTTPException(status_code=404, detail="Test run not found")
        return report
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching report detail: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
