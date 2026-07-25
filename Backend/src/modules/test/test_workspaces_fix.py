import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_workspace_creation_membership(client: AsyncClient):
    # 1. Signup
    signup_resp = await client.post("/api/v1/auth/signup", json={
        "email": "creator@example.com",
        "name": "Creator",
        "passcode": "password123",
        "company": "Creator Inc."
    })
    assert signup_resp.status_code == 201
    auth_data = signup_resp.json()
    token = auth_data["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Workspace
    ws_resp = await client.post("/api/v1/workspaces/", json={
        "name": "New Workspace"
    }, headers=headers)
    assert ws_resp.status_code == 200
    ws_data = ws_resp.json()
    ws_id = ws_data["id"]

    # 3. List Workspaces
    list_ws_resp = await client.get("/api/v1/workspaces/", headers=headers)
    assert list_ws_resp.status_code == 200
    workspaces = list_ws_resp.json()
    
    # Verify the new workspace is in the list
    assert any(w["id"] == ws_id for w in workspaces)

@pytest.mark.asyncio
async def test_workspace_rename(client: AsyncClient):
    # 1. Signup
    signup_resp = await client.post("/api/v1/auth/signup", json={
        "email": "renamer@example.com",
        "name": "Renamer",
        "passcode": "password123",
        "company": "Renamer Inc."
    })
    assert signup_resp.status_code == 201
    auth_data = signup_resp.json()
    token = auth_data["token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Rename Workspace
    patch_resp = await client.patch(f"/api/v1/workspaces/{ws_id}", json={
        "name": "Renamed Workspace"
    }, headers=headers)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Renamed Workspace"

    # 3. Verify via List
    list_ws_resp = await client.get("/api/v1/workspaces/", headers=headers)
    assert any(w["id"] == ws_id and w["name"] == "Renamed Workspace" for w in list_ws_resp.json())
