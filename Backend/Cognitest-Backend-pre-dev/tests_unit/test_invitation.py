import pytest
import uuid
from jose import jwt
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.config import settings, prisma

@pytest.fixture(scope="module", autouse=True)
async def db_conn():
    if not prisma.is_connected():
        await prisma.connect()
    yield
    if prisma.is_connected():
        await prisma.disconnect()

@pytest.mark.asyncio
async def test_invitation_lifecycle():
    uid = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-{uid}"
    user_id = f"user-{uid}"

    payload = {"userId": user_id, "tenantId": tenant_id}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Setup test tenant, user, workspace and role
    tenant = await prisma.tenant.create(
        data={
            "id": tenant_id,
            "name": f"Test Tenant {uid}",
            "status": "ACTIVE"
        }
    )
    user = await prisma.user.create(
        data={
            "id": user_id,
            "email": f"inviter-{uid}@example.com",
            "name": "Inviter Admin",
            "passwordHash": "dummy-hash",
            "tenantId": tenant.id,
            "systemRole": "TENANT_ADMIN",
            "isVerified": True
        }
    )
    workspace = await prisma.workspace.create(
        data={
            "name": f"Workspace {uid}",
            "tenantId": tenant.id
        }
    )
    role = await prisma.role.create(
        data={
            "name": f"ROLE_{uid}",
            "tenantId": tenant.id
        }
    )

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Create invitation
            payload = {
                "email": f"invitee-{uid}@example.com",
                "roleId": role.id,
                "workspaceId": workspace.id,
                "message": "Welcome to the workspace"
            }
            response = await client.post(
                "/api/v1/invitations",
                json=payload,
                headers=auth_headers
            )
            assert response.status_code == 201
            inv_data = response.json()
            assert inv_data["email"] == f"invitee-{uid}@example.com"
            assert inv_data["roleId"] == role.id
            assert inv_data["status"] == "PENDING"
            assert inv_data["token"] is not None

            token_str = inv_data["token"]
            invitation_id = inv_data["id"]

            # 2. Validate invitation token
            validate_resp = await client.get(f"/api/v1/invitations/{token_str}/validate")
            assert validate_resp.status_code == 200
            val_data = validate_resp.json()
            assert val_data["valid"] is True
            assert val_data["invitation"]["email"] == f"invitee-{uid}@example.com"

            # 3. List invitations
            list_resp = await client.get(
                f"/api/v1/invitations?workspace_id={workspace.id}",
                headers=auth_headers
            )
            assert list_resp.status_code == 200
            list_data = list_resp.json()
            assert len(list_data) >= 1
            assert list_data[0]["id"] == invitation_id

            # 4. Resend invitation
            resend_resp = await client.post(
                f"/api/v1/invitations/{invitation_id}/resend",
                headers=auth_headers
            )
            assert resend_resp.status_code == 200
            assert resend_resp.json()["status"] == "PENDING"

            # 5. Revoke invitation
            revoke_resp = await client.post(
                f"/api/v1/invitations/{invitation_id}/revoke",
                headers=auth_headers
            )
            assert revoke_resp.status_code == 200
            assert revoke_resp.json()["status"] == "REVOKED"

            # 6. Check validation fails for revoked token
            validate_revoked = await client.get(f"/api/v1/invitations/{token_str}/validate")
            assert validate_revoked.status_code == 200
            assert validate_revoked.json()["valid"] is False

    finally:
        # Clean up database records
        await prisma.invitation.delete_many(where={"workspaceId": workspace.id})
        await prisma.workspace.delete(where={"id": workspace.id})
        await prisma.role.delete(where={"id": role.id})
        await prisma.user.delete(where={"id": user.id})
        await prisma.tenant.delete(where={"id": tenant.id})
