from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from src.middleware.auth_middleware import require_run_permission, get_current_user
from src.config import prisma
from .schema import (
    GenerateFromSpecResponse,
    UpdateTestCasesResponse,
    GetCollectionResponse,
    GetTestCountResponse,
    ExecuteBatchResponse,
    Collection,
    CollectionInfo
)

router = APIRouter(prefix="/runs", tags=["Runs"])

class GenerateFromSpecRequest(BaseModel):
    projectId: str
    spec: dict

class UpdateTestCasesRequest(BaseModel):
    runId: str
    collection: dict | list | None = None

class ExecuteBatchRequest(BaseModel):
    batchIndex: int
    batchSize: int = 10

@router.post("/generate-from-spec", response_model=GenerateFromSpecResponse)
async def generate_from_spec(data: GenerateFromSpecRequest, user: dict = Depends(get_current_user)):
    if user.get("systemRole") != "SUPER_ADMIN":
        project = await prisma.project.find_unique(where={"id": data.projectId})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        perms = (user.get("workspacePermissions") or {}).get(project.workspaceId, [])
        if "create_test_cases" not in perms:
            raise HTTPException(status_code=403, detail="Missing required permission: create_test_cases")
    """
    Generate test cases from a Swagger/OpenAPI spec.
    Stub - returns a mock run with empty test cases.
    """
    stub_run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    return GenerateFromSpecResponse(
        runId=stub_run_id,
        testCases=[],
        collection=Collection(
            info=CollectionInfo(name="Generated Collection (stub)"),
            item=[],
        ),
    )

@router.post("/update", response_model=UpdateTestCasesResponse)
async def update_test_cases(data: UpdateTestCasesRequest, user: dict = Depends(get_current_user)):
    if user.get("systemRole") != "SUPER_ADMIN":
        run = await prisma.testrun.find_unique(where={"id": data.runId}, include={"project": True})
        if not run or not run.project:
            raise HTTPException(status_code=404, detail="Test run not found")
        perms = (user.get("workspacePermissions") or {}).get(run.project.workspaceId, [])
        if "modify_test_cases" not in perms:
            raise HTTPException(status_code=403, detail="Missing required permission: modify_test_cases")
    """
    Update test cases for a run.
    Stub - acknowledges the update.
    """
    return UpdateTestCasesResponse(
        status="success",
        message=f"Test cases updated for run {data.runId}",
    )

@router.get("/{run_id}", response_model=GetCollectionResponse)
async def get_collection(run_id: str):
    """
    Get the collection for a specific run.
    Stub - returns an empty collection.
    """
    return GetCollectionResponse(
        runId=run_id,
        collection=Collection(
            info=CollectionInfo(name=f"Collection for {run_id} (stub)"),
            item=[],
        ),
    )

@router.get("/{run_id}/count", response_model=GetTestCountResponse)
async def get_test_count(run_id: str):
    """
    Get the total number of tests in a collection.
    Stub - returns 0.
    """
    return GetTestCountResponse(
        runId=run_id,
        count=0,
    )

@router.post("/{run_id}/execute-batch", response_model=ExecuteBatchResponse, dependencies=[Depends(require_run_permission("run_test_cases"))])
async def execute_batch(run_id: str, data: ExecuteBatchRequest):
    """
    Execute a batch of tests.
    Stub - returns empty results.
    """
    return ExecuteBatchResponse(
        runId=run_id,
        batchIndex=data.batchIndex,
        batchSize=data.batchSize,
        results=[],
        summary={
            "total": 0,
            "passed": 0,
            "failed": 0,
        },
    )
