import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app
from src.config import prisma

@pytest.fixture(scope="session")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

@pytest.fixture(scope="session", autouse=True)
async def manage_db_connection():
    if not prisma.is_connected():
        await prisma.connect()
    yield
    if prisma.is_connected():
        await prisma.disconnect()

@pytest.fixture(autouse=True)
async def setup_db():
    # Delete in order of dependencies to avoid foreign key constraints
    await prisma.testsuitetestcase.delete_many()
    await prisma.testresult.delete_many()
    await prisma.regressionsnapshot.delete_many()
    await prisma.fuzzresult.delete_many()
    await prisma.securityfinding.delete_many()
    await prisma.contractvalidation.delete_many()
    await prisma.testrun.delete_many()
    await prisma.testcase.delete_many()
    await prisma.testsuite.delete_many()
    await prisma.apispec.delete_many()
    await prisma.endpoint.delete_many()
    await prisma.projectmember.delete_many()
    await prisma.project.delete_many()
    await prisma.workspacemember.delete_many()
    await prisma.workspace.delete_many()
    await prisma.rolepermission.delete_many()
    await prisma.permission.delete_many()
    await prisma.role.delete_many()
    await prisma.user.delete_many()
    await prisma.subscription.delete_many()
    await prisma.tenant.delete_many()
    
    yield
