import pytest
from httpx import AsyncClient
import os

class TestHealthRouter:
    @pytest.mark.asyncio
    async def test_get_health(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "timestamp" in data

class TestPredictRouter:
    @pytest.mark.asyncio
    async def test_predict(self, client: AsyncClient):
        response = await client.post("/predict", json={"data": "test"})
        assert response.status_code == 200
        assert response.json() == {"message": "This is a dummy endpoint to catch /predict requests."}

class TestProjectsRouter:
    PROJECT_ID = "test-project"

    @pytest.mark.asyncio
    async def test_get_project_meta(self, client: AsyncClient):
        response = await client.get(f"/api/v1/projects/{self.PROJECT_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == self.PROJECT_ID
        assert data["hasSpec"] == False

    @pytest.mark.asyncio
    async def test_upload_project_spec(self, client: AsyncClient):
        # Create a dummy file to upload
        dummy_file_path = "test_spec.json"
        with open(dummy_file_path, "w") as f:
            f.write('{"swagger": "2.0"}')

        with open(dummy_file_path, "rb") as f:
            response = await client.post(
                f"/api/v1/projects/{self.PROJECT_ID}/spec",
                files={"spec": f},
            )
        
        os.remove(dummy_file_path)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["originalName"] == "test_spec.json"

    @pytest.mark.asyncio
    async def test_run_project(self, client: AsyncClient):
        response = await client.post(f"/api/v1/projects/{self.PROJECT_ID}/run")
        assert response.status_code == 200
        data = response.json()
        assert data["runId"] == f"run-{self.PROJECT_ID}-stub"

class TestRunsRouter:
    RUN_ID = "test-run"

    @pytest.mark.asyncio
    async def test_generate_from_spec(self, client: AsyncClient):
        response = await client.post("/api/v1/runs/generate-from-spec", json={"spec": {}})
        assert response.status_code == 200
        data = response.json()
        assert "runId" in data
        assert "collection" in data

    @pytest.mark.asyncio
    async def test_update_test_cases(self, client: AsyncClient):
        response = await client.post("/api/v1/runs/update", json={"runId": self.RUN_ID, "collection": {}})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == f"Test cases updated for run {self.RUN_ID}"

    @pytest.mark.asyncio
    async def test_get_collection(self, client: AsyncClient):
        response = await client.get(f"/api/v1/runs/{self.RUN_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["runId"] == self.RUN_ID
        assert "collection" in data

    @pytest.mark.asyncio
    async def test_get_test_count(self, client: AsyncClient):
        response = await client.get(f"/api/v1/runs/{self.RUN_ID}/count")
        assert response.status_code == 200
        data = response.json()
        assert data["runId"] == self.RUN_ID
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_execute_batch(self, client: AsyncClient):
        response = await client.post(
            f"/api/v1/runs/{self.RUN_ID}/execute-batch",
            json={"batchIndex": 0, "batchSize": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["runId"] == self.RUN_ID
        assert data["batchIndex"] == 0
