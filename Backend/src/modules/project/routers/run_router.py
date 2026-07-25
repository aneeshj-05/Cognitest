import json
import logging
import uuid
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from src.config import prisma
from src.middleware.auth_middleware import get_current_user
from ..schema import RunProjectRequest, StreamTicketRequest, StreamTicketResponse
from ..services import execution_service, project_service
from ..state import _run_results_store, _stream_tickets_store
from src.utils.egress_guard import validate_egress_url_async, SsrfBlockedError, EgressResult

router = APIRouter(prefix="/projects", tags=["Execution"])
logger = logging.getLogger(__name__)


def _is_security_suite(cases: list[dict]) -> bool:
    """Return True when every case in the list belongs to the SECURITY category."""
    if not cases:
        return False
    for c in cases:
        raw = c.get("test_type") or c.get("category") or ""
        if hasattr(raw, "value"):
            raw = raw.value
        elif hasattr(raw, "name") and not isinstance(raw, str):
            raw = raw.name
        if str(raw).upper() not in ("SECURITY", "FUZZ"):
            return False
    return True


async def _load_spec(project_id: str) -> dict | None:
    """Fetch the latest parsed spec for a project from the DB."""
    try:
        api_spec = await prisma.apispec.find_first(
            where={"projectId": project_id},
            order={"createdAt": "desc"},
        )
        if not api_spec or not api_spec.parsed_spec:
            return None
        return (
            api_spec.parsed_spec
            if isinstance(api_spec.parsed_spec, dict)
            else json.loads(api_spec.parsed_spec)
        )
    except Exception:
        return None


@router.post("/{project_id}/run-suite/ticket", response_model=StreamTicketResponse)
async def create_stream_ticket(
    project_id: str,
    data: StreamTicketRequest,
    user: dict = Depends(get_current_user),
):
    """Generate a one-time use ticket for the SSE stream to prevent URL credential exposure."""
    await project_service.verify_project_access(project_id, user)
    
    # Cleanup expired tickets
    current_time = time.time()
    expired = [k for k, v in _stream_tickets_store.items() if v["expires_at"] < current_time]
    for k in expired:
        _stream_tickets_store.pop(k, None)
        
    ticket_id = str(uuid.uuid4())
    _stream_tickets_store[ticket_id] = {
        "data": data.model_dump(),
        "user_id": user["userId"],
        "expires_at": current_time + 60, # 60 seconds TTL
    }
    return StreamTicketResponse(ticket=ticket_id)

@router.get("/{project_id}/run-suite/stream")
async def run_suite_stream(
    project_id: str,
    ticket: str = Query(...),
):
    """SSE streaming endpoint using a secure one-time ticket."""
    ticket_data = _stream_tickets_store.pop(ticket, None)
    if not ticket_data or ticket_data["expires_at"] < time.time():
        raise HTTPException(status_code=401, detail="Invalid or expired ticket")
        
    data = ticket_data["data"]
    user_id = ticket_data["user_id"]
    
    base_url = data.get("base_url")
    case_ids = data.get("case_ids")
    manual_token = data.get("manual_token")
    register_url = data.get("register_url")
    login_url = data.get("login_url")
    auth_email = data.get("auth_email")
    auth_password = data.get("auth_password")
    admin_token = data.get("admin_token")

    # ── SSRF guard: validate base_url before any outbound request ──────────
    if base_url:
        try:
            _guard = await validate_egress_url_async(base_url)
            base_url = _guard.url   # original URL preserved (TLS/vhost safe)
        except SsrfBlockedError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    if case_ids:
        ids = [cid.strip() for cid in case_ids.split(",") if cid.strip()]
        cases_db = await prisma.testcase.find_many(
            where={"id": {"in": ids}, "projectId": project_id},
            order={"execution_order": "asc"},
        )
    else:
        cases_db = await prisma.testcase.find_many(
            where={"projectId": project_id, "isActive": True},
            order={"execution_order": "asc"},
        )

    if not cases_db:
        raise HTTPException(status_code=400, detail="No test cases found to run")

    cases = [c.model_dump() for c in cases_db]

    # ── Security suites get the dedicated runner with upfront user setup ──────
    if _is_security_suite(cases):
        spec = await _load_spec(project_id)
        return StreamingResponse(
            execution_service.stream_security_suite(
                cases=cases,
                base_url=base_url,
                project_id=project_id,
                user_id=user_id,
                spec=spec,
                admin_token=admin_token or None,
                manual_token=manual_token,
                auth_register_url=register_url,
                auth_login_url=login_url,
                auth_email=auth_email,
                auth_password=auth_password,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── All other test types ──────────────────────────────────────────────────
    return StreamingResponse(
        execution_service.stream_run_suite(
            cases=cases,
            base_url=base_url,
            project_id=project_id,
            user_id=user_id,
            manual_token=manual_token,
            auth_register_url=register_url,
            auth_login_url=login_url,
            auth_email=auth_email,
            auth_password=auth_password,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{project_id}/run")
async def run_project(
    project_id: str,
    request: Request,
    data: RunProjectRequest,
    user: dict = Depends(get_current_user),
):
    await project_service.verify_project_access(project_id, user)

    if data.case_ids:
        cases_db = await prisma.testcase.find_many(
            where={"id": {"in": data.case_ids}, "projectId": project_id}
        )
    else:
        cases_db = await prisma.testcase.find_many(
            where={"projectId": project_id, "isActive": True}
        )

    if not cases_db:
        raise HTTPException(status_code=400, detail="No test cases found to run")

    cases = [c.model_dump() for c in cases_db]
    base_url = data.base_url or "https://api.example.com"

    # ── SSRF guard: validate base_url before any outbound request ──────────
    try:
        _guard = await validate_egress_url_async(base_url)
        base_url = _guard.url   # original URL preserved (TLS/vhost safe)
    except SsrfBlockedError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if _is_security_suite(cases):
        spec = await _load_spec(project_id)
        return StreamingResponse(
            execution_service.stream_security_suite(
                cases=cases,
                base_url=base_url,
                project_id=project_id,
                user_id=user["userId"],
                spec=spec,
                admin_token=data.admin_token or None,
                manual_token=data.token,
                auth_register_url=data.register_url,
                auth_login_url=data.login_url,
                auth_email=data.auth_email,
                auth_password=data.auth_password,
                request=request,
            ),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        execution_service.stream_run_suite(
            cases=cases,
            base_url=base_url,
            project_id=project_id,
            user_id=user["userId"],
            manual_token=data.token,
            auth_register_url=data.register_url,
            auth_login_url=data.login_url,
            auth_email=data.auth_email,
            auth_password=data.auth_password,
            request=request,
        ),
        media_type="text/event-stream",
    )


@router.get("/{project_id}/run-results")
async def get_run_results(project_id: str, user: dict = Depends(get_current_user)):
    await project_service.verify_project_access(project_id, user)
    return _run_results_store.get(project_id, {"results": [], "summary": {}})
