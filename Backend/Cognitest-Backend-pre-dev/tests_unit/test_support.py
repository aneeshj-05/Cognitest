import pytest
from pydantic import ValidationError
from jose import jwt
from httpx import ASGITransport, AsyncClient
from src.main import app
from src.config import settings, prisma
from src.modules.support.schema import SupportTicketCreate
from src.modules.support.service import create_support_ticket


@pytest.fixture(scope="module", autouse=True)
async def db_conn():
    if not prisma.is_connected():
        await prisma.connect()
    yield
    if prisma.is_connected():
        await prisma.disconnect()


@pytest.fixture
def auth_headers():
    payload = {"userId": "test-user-id", "tenantId": "test-tenant-id"}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return {"Authorization": f"Bearer {token}"}


def test_support_ticket_validation():
    # Valid data
    data = SupportTicketCreate(
        subject="Valid Subject",
        category="bug",
        description="This is a detailed description of the issue."
    )
    assert data.subject == "Valid Subject"
    assert data.category == "bug"
    assert data.description == "This is a detailed description of the issue."

    # Subject under length
    with pytest.raises(ValidationError):
        SupportTicketCreate(
            subject="a",
            category="bug",
            description="This is a detailed description."
        )

    # Description under length
    with pytest.raises(ValidationError):
        SupportTicketCreate(
            subject="Valid Subject",
            category="bug",
            description="Short"
        )

    # Invalid category
    with pytest.raises(ValidationError):
        SupportTicketCreate(
            subject="Valid Subject",
            category="invalid_category",
            description="This is a detailed description."
        )


@pytest.mark.asyncio
async def test_support_ticket_db_persistence():
    data = SupportTicketCreate(
        subject="Test support ticket",
        category="feature",
        description="This is a test to verify database persistence."
    )
    ticket = await create_support_ticket(data, user_id="test-user-id")
    assert ticket.id is not None
    assert ticket.subject == "Test support ticket"
    assert ticket.category == "feature"
    assert ticket.description == "This is a test to verify database persistence."
    assert ticket.userId == "test-user-id"
    assert ticket.status == "open"

    db_ticket = await prisma.supportticket.find_unique(where={"id": ticket.id})
    assert db_ticket is not None
    assert db_ticket.subject == "Test support ticket"

    await prisma.supportticket.delete(where={"id": ticket.id})


@pytest.mark.asyncio
async def test_support_ticket_router_endpoint(auth_headers):
    # Test HTTP POST to support ticket endpoint
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "subject": "Router Test Support Ticket",
            "category": "billing",
            "description": "Verifying that the router endpoint creates and returns the support ticket.",
            "workspaceId": "test-workspace-id"
        }
        response = await client.post(
            "/api/v1/support/tickets",
            json=payload,
            headers=auth_headers
        )

        # Verify 201 Created
        assert response.status_code == 201

        data = response.json()
        assert data["id"] is not None
        assert data["subject"] == "Router Test Support Ticket"
        assert data["category"] == "billing"
        assert data["description"] == "Verifying that the router endpoint creates and returns the support ticket."
        assert data["userId"] == "test-user-id"
        assert data["workspaceId"] == "test-workspace-id"
        assert data["status"] == "open"

        # Verify it actually exists in DB
        db_ticket = await prisma.supportticket.find_unique(where={"id": data["id"]})
        assert db_ticket is not None
        assert db_ticket.subject == "Router Test Support Ticket"

        # Clean up
        await prisma.supportticket.delete(where={"id": data["id"]})


@pytest.mark.asyncio
async def test_support_ticket_router_validation_error(auth_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Invalid payload (short subject, short description, invalid category)
        payload = {
            "subject": "s",
            "category": "invalid-cat",
            "description": "short"
        }
        response = await client.post(
            "/api/v1/support/tickets",
            json=payload,
            headers=auth_headers
        )

        # Verify 422 Unprocessable Entity
        assert response.status_code == 422
