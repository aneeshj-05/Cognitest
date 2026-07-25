import pytest

from src.modules.project.services.execution_service import _legacy_negative_expected_statuses


@pytest.fixture(autouse=True)
def setup_db():
    """Override global DB cleanup fixture for pure unit tests."""
    yield


@pytest.fixture(scope="session")
def manage_db_connection():
    """Override global DB connection fixture for pure unit tests."""
    yield


def test_legacy_negative_validation_case_accepts_422():
    case = {
        "category": "NEGATIVE",
        "test_type": "Negative",
        "subCategory": "MISSING_PARAMS",
    }
    assert _legacy_negative_expected_statuses(case, 400) == [400, 422]


def test_non_negative_case_does_not_apply_422_fallback():
    case = {
        "category": "FUNCTIONAL",
        "test_type": "Functional",
        "subCategory": "CRUD_VALIDATION",
    }
    assert _legacy_negative_expected_statuses(case, 400) == []


def test_non_validation_negative_case_does_not_apply_422_fallback():
    case = {
        "category": "NEGATIVE",
        "test_type": "Negative",
        "subCategory": "RESOURCE_NOT_FOUND",
    }
    assert _legacy_negative_expected_statuses(case, 400) == []


def test_legacy_negative_crud_validation_accepts_422():
    case = {
        "category": "NEGATIVE",
        "test_type": "Negative",
        "subCategory": "CRUD_VALIDATION",
    }
    assert _legacy_negative_expected_statuses(case, 400) == [400, 422]


def test_legacy_invalid_headers_accepts_415_and_422():
    case = {
        "category": "NEGATIVE",
        "test_type": "Negative",
        "subCategory": "INVALID_HEADERS",
    }
    assert _legacy_negative_expected_statuses(case, 400) == [400, 415, 422]
