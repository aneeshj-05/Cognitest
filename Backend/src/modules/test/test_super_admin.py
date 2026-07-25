import pytest
from httpx import AsyncClient
from src.config.settings import settings

@pytest.mark.asyncio
class TestSuperAdminCRUD:
    @pytest.fixture(autouse=True)
    async def setup_auth(self, client: AsyncClient):
        # Login as Super Admin to get token
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": settings.super_admin_email,
                "passcode": settings.super_admin_password
            }
        )
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def test_tenant_lifecycle(self, client: AsyncClient):
        # 1. Create Tenant
        create_data = {
            "name": "Test Tenant",
            "email": "test@tenant.com",
            "plan": "PROFESSIONAL",
            "password": "testpassword123"
        }
        response = await client.post("/api/v1/super-admin/tenants", json=create_data, headers=self.headers)
        assert response.status_code == 200
        tenant_id = response.json()["tenantId"]

        # 2. Update Tenant Status (Lock/Unlock Account / Suspend Tenant)
        # Update Tenant Status
        status_response = await client.patch(
            f"/api/v1/super-admin/tenants/{tenant_id}/status",
            json={"status": "SUSPENDED"},
            headers=self.headers
        )
        assert status_response.status_code == 200

        # 3. Edit Tenant
        edit_data = {
            "name": "Updated Test Tenant",
            "plan": "ENTERPRISE"
        }
        edit_response = await client.patch(
            f"/api/v1/super-admin/tenants/{tenant_id}",
            json=edit_data,
            headers=self.headers
        )
        assert edit_response.status_code == 200

        # 4. Delete Tenant (Cascading)
        delete_response = await client.delete(f"/api/v1/super-admin/tenants/{tenant_id}", headers=self.headers)
        assert delete_response.status_code == 200

    async def test_project_deletion(self, client: AsyncClient):
        # Create a tenant and project first
        create_data = {
            "name": "Project Test Tenant",
            "email": "project@test.com",
            "plan": "FREE"
        }
        response = await client.post("/api/v1/super-admin/tenants", json=create_data, headers=self.headers)
        tenant_id = response.json()["tenantId"]
        
        # Super Admin API returns tenants including projects. 
        # But we need to find the project ID.
        tenants_response = await client.get("/api/v1/super-admin/tenants", headers=self.headers)
        tenant = next(t for t in tenants_response.json() if t["id"] == tenant_id)
        project_id = tenant["projects"][0]["id"]
        
        # Delete Project
        delete_project_response = await client.delete(
            f"/api/v1/super-admin/projects/{project_id}",
            headers=self.headers
        )
        assert delete_project_response.status_code == 200
        
        # Verify project is gone
        tenants_response = await client.get("/api/v1/super-admin/tenants", headers=self.headers)
        tenant = next(t for t in tenants_response.json() if t["id"] == tenant_id)
        assert len(tenant["projects"]) == 0
        
        # Cleanup tenant
        await client.delete(f"/api/v1/super-admin/tenants/{tenant_id}", headers=self.headers)
