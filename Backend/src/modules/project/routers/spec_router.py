import json
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from src.middleware.auth_middleware import get_current_user
from src.config import prisma
from ..schema import SpecInfo, UploadSpecResponse, SpecTestResultsResponse, SpecTestResult
from ..services import spec_service, project_service
from ..state import _spec_store, _spec_name_store, _draft_store, _base_url_store

router = APIRouter(prefix="/projects", tags=["Specifications"])

@router.get("/{project_id}/specs", response_model=List[SpecInfo])
async def get_project_specs(project_id: str, user: dict = Depends(get_current_user)):
    await project_service.verify_project_access(project_id, user)
    specs = await prisma.apispec.find_many(
        where={"projectId": project_id},
        order={"createdAt": "desc"}
    )
    return [
        SpecInfo(
            id=s.id,
            file_type=s.file_type,
            version=s.version,
            file_url=s.file_url,
            uploadedBy=s.uploadedBy,
            createdAt=s.createdAt
        )
        for s in specs
    ]

@router.get("/{project_id}/specs/{spec_id}/content")
async def get_project_spec_content(project_id: str, spec_id: str, user: dict = Depends(get_current_user)):
    await project_service.verify_project_access(project_id, user)
    spec = await prisma.apispec.find_unique(where={"id": spec_id})
    if not spec:
        raise HTTPException(status_code=404, detail="Specification not found")

    content = spec.parsed_spec
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            pass
    return content

@router.post("/{project_id}/spec", response_model=UploadSpecResponse)
async def upload_project_spec(
    project_id: str,
    spec: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    spec_id, endpoints_count, size = await spec_service.process_spec_upload(
        project_id, spec, user.get("userId"), 
        _spec_store, _spec_name_store, _draft_store, _base_url_store
    )
    return UploadSpecResponse(
        status="success",
        message=f"Spec uploaded for project {project_id}",
        spec_id=spec_id,
        originalName=spec.filename,
        size=size,
        endpoints_count=endpoints_count,
    )

@router.post("/{project_id}/repair-endpoints")
async def repair_endpoints(project_id: str, user: dict = Depends(get_current_user)):
    await project_service.verify_project_access(project_id, user)
    created, spec_id = await spec_service.repair_project_endpoints(project_id)
    return {"status": "success", "endpoints_created": created, "spec_id": spec_id}

@router.get("/{project_id}/specs/{spec_id}/results", response_model=SpecTestResultsResponse)
async def get_spec_test_results(project_id: str, spec_id: str, user: dict = Depends(get_current_user)):
    await project_service.verify_project_access(project_id, user)
    
    endpoints = await prisma.endpoint.find_many(
        where={"projectId": project_id, "specId": spec_id}
    )
    endpoint_ids = [e.id for e in endpoints if e.id]
    if not endpoint_ids:
        return SpecTestResultsResponse(passed=[], failed=[])

    test_cases = await prisma.testcase.find_many(
        where={"endpointId": {"in": endpoint_ids}, "isActive": True}
    )
    test_case_ids = [t.id for t in test_cases]
    test_case_map = {t.id: t for t in test_cases}

    if not test_case_ids:
        return SpecTestResultsResponse(passed=[], failed=[])

    results = await prisma.testresult.find_many(
        where={"testCaseId": {"in": test_case_ids}},
        order={"executedAt": "desc"}
    )

    latest_results = {}
    for r in results:
        if r.testCaseId not in latest_results:
            latest_results[r.testCaseId] = r

    passed = []
    failed = []
    for tc_id, result in latest_results.items():
        tc = test_case_map.get(tc_id)
        if not tc: continue
        
        status = result.status.name if hasattr(result.status, 'name') else str(result.status)
        spec_result = SpecTestResult(
            endpointId=tc.endpointId,
            testCaseId=tc.id,
            method=tc.method,
            endpoint=tc.endpoint_path,
            name=tc.name,
            expected=result.expected_status,
            actual=result.actual_status,
            message=result.error_message
        )
        if status == "PASSED":
            passed.append(spec_result)
        elif status == "FAILED":
            failed.append(spec_result)

    return SpecTestResultsResponse(passed=passed, failed=failed)
