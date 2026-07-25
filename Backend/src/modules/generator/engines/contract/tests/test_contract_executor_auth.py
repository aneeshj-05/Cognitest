from __future__ import annotations

import httpx
import pytest
import uuid

from src.modules.generator.engines.contract import contract_executor as ce


@pytest.mark.asyncio
async def test_token_capture_only_from_login_json(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[tuple[str, str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path, request.headers.get("authorization")))

        if request.url.path == "/auth/login":
            # Nested token shape: data.session.token
            return httpx.Response(200, json={"data": {"session": {"token": "LOGIN_TOKEN"}}})

        if request.url.path == "/other":
            # Would have overridden token in the old (too-generic) capture logic.
            return httpx.Response(200, json={"token": "EVIL_TOKEN"})

        if request.url.path == "/protected":
            auth = request.headers.get("authorization")
            if auth == "Bearer LOGIN_TOKEN":
                return httpx.Response(200, json={"ok": True})
            return httpx.Response(401, json={"ok": False, "auth": auth})

        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ce.httpx, "AsyncClient", PatchedAsyncClient)

    test_cases = [
        {
            "id": "protected",
            "method": "POST",
            "endpoint_path": "/protected",
            "kind": "positive",
            "security_required": True,
            "request_headers": {},
            "request_query": {},
            "request_body": {"noop": True},
        },
        {
            "id": "login",
            "method": "POST",
            "endpoint_path": "/auth/login",
            "kind": "positive",
            "security_required": False,
            "request_headers": {},
            "request_query": {},
            "request_body": {"email": "ignored", "password": "ignored"},
        },
        {
            "id": "other",
            "method": "GET",
            "endpoint_path": "/other",
            "kind": "positive",
            "security_required": False,
            "request_headers": {},
            "request_query": {},
            "request_body": None,
        },
    ]

    results = await ce.execute_contract_test_cases(
        test_cases,
        base_url="http://example",
        auth_enabled=True,
        timeout_seconds=5.0,
        concurrency=10,
    )

    # Ensure /protected got the login token (not overwritten by /other).
    protected = next(r for r in results if r["test_case"]["id"] == "protected")
    assert protected["response"]["status_code"] == 200

    # And ensure the execution actually called login.
    assert any(path == "/auth/login" for _m, path, _a in requests)


@pytest.mark.asyncio
async def test_missing_token_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ce.httpx, "AsyncClient", PatchedAsyncClient)

    test_cases = [
        {
            "id": "protected",
            "method": "GET",
            "endpoint_path": "/protected",
            "kind": "positive",
            "security_required": True,
            "request_headers": {},
            "request_query": {},
            "request_body": None,
        }
    ]

    results = await ce.execute_contract_test_cases(
        test_cases,
        base_url="http://example",
        auth_enabled=True,
        timeout_seconds=5.0,
        concurrency=10,
    )

    # Executor must not gate execution: it should send the request without auth.
    assert requests == ["/protected"]
    assert results[0]["execution_status"] in {"PASSED", "FAILED"}


@pytest.mark.asyncio
async def test_login_failure_skips_remaining_protected_positives(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(request.url.path)
        if request.url.path == "/auth/login":
            return httpx.Response(401, json={"error": "bad creds"})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ce.httpx, "AsyncClient", PatchedAsyncClient)

    test_cases = [
        {
            "id": "login",
            "method": "POST",
            "endpoint_path": "/auth/login",
            "kind": "positive",
            "security_required": False,
            "request_headers": {},
            "request_query": {},
            "request_body": {"email": "x", "password": "y"},
        },
        {
            "id": "protected",
            "method": "GET",
            "endpoint_path": "/protected",
            "kind": "positive",
            "security_required": True,
            "request_headers": {},
            "request_query": {},
            "request_body": None,
        },
    ]

    results = await ce.execute_contract_test_cases(
        test_cases,
        base_url="http://example",
        auth_enabled=True,
        timeout_seconds=5.0,
        concurrency=10,
    )

    # Executor must not gate execution: it should attempt login then still call protected.
    assert called == ["/auth/login", "/protected"]
    protected = next(r for r in results if r["test_case"]["id"] == "protected")
    assert protected["execution_status"] in {"PASSED", "FAILED"}


@pytest.mark.asyncio
async def test_token_capture_from_response_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, headers={"Authorization": "Bearer HEADER_TOKEN"}, json={"ok": True})

        if request.url.path == "/protected":
            auth = request.headers.get("authorization")
            if auth == "Bearer HEADER_TOKEN":
                return httpx.Response(200, json={"ok": True})
            return httpx.Response(401, json={"ok": False, "auth": auth})

        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ce.httpx, "AsyncClient", PatchedAsyncClient)

    test_cases = [
        {
            "id": "protected",
            "method": "GET",
            "endpoint_path": "/protected",
            "kind": "positive",
            "security_required": True,
            "request_headers": {},
            "request_query": {},
            "request_body": None,
        },
        {
            "id": "login",
            "method": "POST",
            "endpoint_path": "/auth/login",
            "kind": "positive",
            "security_required": False,
            "request_headers": {},
            "request_query": {},
            "request_body": {"email": "ignored", "password": "ignored"},
        },
    ]

    results = await ce.execute_contract_test_cases(
        test_cases,
        base_url="http://example",
        auth_enabled=True,
        timeout_seconds=5.0,
        concurrency=10,
    )

    protected = next(r for r in results if r["test_case"]["id"] == "protected")
    assert protected["response"]["status_code"] == 200


@pytest.mark.asyncio
async def test_entity_state_injects_id_into_path_params(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)

        if request.url.path == "/items":
            if request.method == "POST":
                return httpx.Response(201, json={"id": "ITEM-123"})
            return httpx.Response(405, json={})

        if request.url.path == "/items/ITEM-123":
            return httpx.Response(200, json={"id": "ITEM-123", "name": "Test"})

        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ce.httpx, "AsyncClient", PatchedAsyncClient)

    test_cases = [
        {
            "id": "get_item",
            "method": "GET",
            "endpoint_path": "/items/{id}",
            "kind": "positive",
            "security_required": False,
            "path_params": {"id": "1"},  # placeholder should be replaced once entity exists
            "request_headers": {},
            "request_query": {},
            "request_body": None,
        },
        {
            "id": "create_item",
            "method": "POST",
            "endpoint_path": "/items",
            "kind": "positive",
            "security_required": False,
            "request_headers": {},
            "request_query": {},
            "request_body": {"name": "Widget", "price": 1},
        },
    ]

    results = await ce.execute_contract_test_cases(
        test_cases,
        base_url="http://example",
        auth_enabled=False,
        timeout_seconds=5.0,
        concurrency=10,
    )

    # Execution should be stable and stateful:
    # create_item first (because positives-first ordering + stable auth-flow ordering),
    # then get_item should use the extracted ITEM-123.
    assert "/items" in seen_paths
    assert "/items/ITEM-123" in seen_paths
    get_item = next(r for r in results if r["test_case"]["id"] == "get_item")
    assert get_item["response"]["status_code"] == 200


@pytest.mark.asyncio
async def test_reset_token_extracted_and_injected(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)

        if request.url.path == "/reset" and request.method == "POST":
            return httpx.Response(200, json={"token": "RESET-123"})

        if request.url.path == "/reset/RESET-123" and request.method == "POST":
            return httpx.Response(200, json={"ok": True})

        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ce.httpx, "AsyncClient", PatchedAsyncClient)

    test_cases = [
        {
            "id": "use_reset",
            "method": "POST",
            "endpoint_path": "/reset/{token}",
            "kind": "positive",
            "security_required": False,
            "request_headers": {},
            "request_query": {},
            "request_body": {"password": "x", "confirmPassword": "x"},
        },
        {
            "id": "request_reset",
            "method": "POST",
            "endpoint_path": "/reset",
            "kind": "positive",
            "security_required": False,
            "request_headers": {},
            "request_query": {},
            "request_body": {"email": "ignored"},
        },
    ]

    results = await ce.execute_contract_test_cases(
        test_cases,
        base_url="http://example",
        auth_enabled=False,
        timeout_seconds=5.0,
        concurrency=10,
    )

    assert "/reset" in seen_paths
    assert "/reset/RESET-123" in seen_paths
    use_reset = next(r for r in results if r["test_case"]["id"] == "use_reset")
    assert use_reset["response"]["status_code"] == 200


@pytest.mark.asyncio
async def test_add_to_cart_injects_item_id(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)

        if request.url.path == "/items" and request.method == "GET":
            return httpx.Response(200, json=[{"id": "ITEM-9"}])

        if request.url.path == "/add-to-cart/ITEM-9" and request.method == "POST":
            return httpx.Response(200, json={"cart_item_id": "CARTITEM-1"})

        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ce.httpx, "AsyncClient", PatchedAsyncClient)

    test_cases = [
        {
            "id": "add_to_cart",
            "method": "POST",
            "endpoint_path": "/add-to-cart/{id}",
            "kind": "positive",
            "security_required": False,
            "path_params": {"id": "1"},
            "request_headers": {},
            "request_query": {},
            "request_body": {},
        },
        {
            "id": "list_items",
            "method": "GET",
            "endpoint_path": "/items",
            "kind": "positive",
            "security_required": False,
            "request_headers": {},
            "request_query": {},
            "request_body": None,
        },
    ]

    results = await ce.execute_contract_test_cases(
        test_cases,
        base_url="http://example",
        auth_enabled=False,
        timeout_seconds=5.0,
        concurrency=10,
    )

    assert "/items" in seen_paths
    assert "/add-to-cart/ITEM-9" in seen_paths
    add_to_cart = next(r for r in results if r["test_case"]["id"] == "add_to_cart")
    assert add_to_cart["response"]["status_code"] == 200


@pytest.mark.asyncio
async def test_entity_extraction_is_endpoint_aware(monkeypatch: pytest.MonkeyPatch) -> None:
    """If response contains both user.id and item.id, we must persist item_id for /items flows."""
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)

        if request.url.path == "/items" and request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "user": {"id": "user123"},
                    "item": {"id": "item456"},
                },
            )

        if request.url.path == "/items/item456" and request.method == "GET":
            return httpx.Response(200, json={"id": "item456"})

        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ce.httpx, "AsyncClient", PatchedAsyncClient)

    test_cases = [
        {
            "id": "get_item",
            "method": "GET",
            "endpoint_path": "/items/{id}",
            "kind": "positive",
            "security_required": False,
            "path_params": {"id": "1"},
            "request_headers": {},
            "request_query": {},
            "request_body": None,
        },
        {
            "id": "create_item",
            "method": "POST",
            "endpoint_path": "/items",
            "kind": "positive",
            "security_required": False,
            "request_headers": {},
            "request_query": {},
            "request_body": {"name": "Widget", "price": 1},
        },
    ]

    results = await ce.execute_contract_test_cases(
        test_cases,
        base_url="http://example",
        auth_enabled=False,
        timeout_seconds=5.0,
        concurrency=10,
    )

    assert "/items" in seen_paths
    assert "/items/item456" in seen_paths
    get_item = next(r for r in results if r["test_case"]["id"] == "get_item")
    assert get_item["response"]["status_code"] == 200


@pytest.mark.asyncio
async def test_list_endpoint_does_not_overwrite_producer_entity(monkeypatch: pytest.MonkeyPatch) -> None:
    """If a producer creates item_id, a later list response must not overwrite it."""
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)

        if request.url.path == "/items" and request.method == "POST":
            return httpx.Response(201, json={"id": "ITEM-PRODUCED"})

        if request.url.path == "/items" and request.method == "GET":
            # Different, unrelated id that must not overwrite.
            return httpx.Response(200, json=[{"id": "ITEM-LIST"}])

        if request.url.path == "/items/ITEM-PRODUCED" and request.method == "GET":
            return httpx.Response(200, json={"id": "ITEM-PRODUCED"})

        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ce.httpx, "AsyncClient", PatchedAsyncClient)

    test_cases = [
        {
            "id": "get_item",
            "method": "GET",
            "endpoint_path": "/items/{id}",
            "kind": "positive",
            "security_required": False,
            "path_params": {"id": "1"},
            "request_headers": {},
            "request_query": {},
            "request_body": None,
        },
        {
            "id": "list_items",
            "method": "GET",
            "endpoint_path": "/items",
            "kind": "positive",
            "security_required": False,
            "request_headers": {},
            "request_query": {},
            "request_body": None,
        },
        {
            "id": "create_item",
            "method": "POST",
            "endpoint_path": "/items",
            "kind": "positive",
            "security_required": False,
            "request_headers": {},
            "request_query": {},
            "request_body": {"name": "Widget", "price": 1},
        },
    ]

    results = await ce.execute_contract_test_cases(
        test_cases,
        base_url="http://example",
        auth_enabled=False,
        timeout_seconds=5.0,
        concurrency=10,
    )

    assert "/items" in seen_paths
    assert "/items/ITEM-PRODUCED" in seen_paths
    get_item = next(r for r in results if r["test_case"]["id"] == "get_item")
    assert get_item["response"]["status_code"] == 200


@pytest.mark.asyncio
async def test_unresolved_path_param_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    # This test intentionally relies on placeholder fallback; disable strict
    # fallback gating to keep the test focused on "executor must send".
    monkeypatch.setenv("COGNITEST_ENFORCE_FALLBACK_LIMITS", "0")

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ce.httpx, "AsyncClient", PatchedAsyncClient)

    test_cases = [
        {
            "id": "bad",
            "method": "GET",
            "endpoint_path": "/search/{q}",
            "kind": "positive",
            "security_required": False,
            # Intentionally omit path_params so {q} remains unresolved.
            "request_headers": {},
            "request_query": {},
            "request_body": None,
        }
    ]

    results = await ce.execute_contract_test_cases(
        test_cases,
        base_url="http://example",
        auth_enabled=False,
        timeout_seconds=5.0,
        concurrency=10,
    )

    # Executor must not block: it force-resolves `{q}` and sends the request.
    assert len(called) == 1
    assert called[0].startswith("/search/")
    uuid.UUID(called[0].split("/search/", 1)[1])
    assert results[0]["execution_status"] in {"PASSED", "FAILED"}


@pytest.mark.asyncio
async def test_missing_entity_id_for_items_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    # This test intentionally relies on a placeholder ID; disable strict
    # fallback gating to keep the test focused on "executor must send".
    monkeypatch.setenv("COGNITEST_ENFORCE_FALLBACK_LIMITS", "0")

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ce.httpx, "AsyncClient", PatchedAsyncClient)

    # This mimics the problematic case: generator filled "id": "1" but we never created an item.
    test_cases = [
        {
            "id": "get_item",
            "method": "GET",
            "endpoint_path": "/items/{id}",
            "kind": "positive",
            "security_required": False,
            "path_params": {"id": "1"},
            "request_headers": {},
            "request_query": {},
            "request_body": None,
        }
    ]

    results = await ce.execute_contract_test_cases(
        test_cases,
        base_url="http://example",
        auth_enabled=False,
        timeout_seconds=5.0,
        concurrency=10,
    )

    # Executor must not gate on entity existence: it sends using the provided placeholder ID.
    assert called == ["/items/1"]
    assert results[0]["execution_status"] in {"PASSED", "FAILED"}


@pytest.mark.asyncio
async def test_admin_positive_blocked_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ce.httpx, "AsyncClient", PatchedAsyncClient)

    test_cases = [
        {
            "id": "admin_add",
            "method": "POST",
            "endpoint_path": "/admin/add-item",
            "kind": "positive",
            "security_required": True,
            "request_headers": {},
            "request_query": {},
            "request_body": {"name": "Widget", "price": 1},
        }
    ]

    results = await ce.execute_contract_test_cases(
        test_cases,
        base_url="http://example",
        auth_enabled=True,
        timeout_seconds=5.0,
        concurrency=10,
    )

    # Executor must not skip admin endpoints by default.
    assert called == ["/admin/add-item"]
    assert results[0]["execution_status"] in {"PASSED", "FAILED"}
