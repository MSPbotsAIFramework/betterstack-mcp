"""Monitor CRUD tool tests (AC1-AC5, TC-BS-001..011)."""

from __future__ import annotations

import json

import httpx

from tests.conftest import TEST_BASE_URL, call_tool


def _monitor_resource(id_: str = "1", **attrs: object) -> dict:
    defaults = {
        "url": "https://example.com",
        "pronounceable_name": "Example",
        "monitor_type": "status",
        "status": "up",
        "paused": False,
        "check_frequency": 30,
    }
    defaults.update(attrs)
    return {"id": id_, "type": "monitor", "attributes": defaults}


async def test_list_monitors_default_limit_and_fields(mcp, credentials, betterstack_api):
    route = betterstack_api.get(f"{TEST_BASE_URL}/monitors").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [_monitor_resource("1"), _monitor_resource("2", url="https://b.com")],
                "pagination": {"next": None},
            },
        )
    )

    result = json.loads(await call_tool(mcp, "betterstack_list_monitors", {}))

    assert route.calls.last.request.url.params["per_page"] == "50"
    assert result["has_more"] is False
    assert result["next_cursor"] is None
    assert len(result["data"]) == 2
    assert result["data"][0] == {
        "id": "1",
        "url": "https://example.com",
        "pronounceable_name": "Example",
        "monitor_type": "status",
        "status": "up",
        "paused": False,
        "check_frequency": 30,
    }


async def test_list_monitors_clamps_limit_to_200(mcp, credentials, betterstack_api):
    route = betterstack_api.get(f"{TEST_BASE_URL}/monitors").mock(
        return_value=httpx.Response(200, json={"data": [], "pagination": {"next": None}})
    )

    await call_tool(mcp, "betterstack_list_monitors", {"limit": 500})

    assert route.calls.last.request.url.params["per_page"] == "200"


async def test_list_monitors_empty_result_is_not_an_error(mcp, credentials, betterstack_api):
    betterstack_api.get(f"{TEST_BASE_URL}/monitors").mock(
        return_value=httpx.Response(200, json={"data": [], "pagination": {"next": None}})
    )

    result = json.loads(await call_tool(mcp, "betterstack_list_monitors", {"url": "https://nomatch.example"}))

    assert result == {"data": [], "has_more": False, "next_cursor": None}


async def test_get_monitor_returns_detail(mcp, credentials, betterstack_api):
    betterstack_api.get(f"{TEST_BASE_URL}/monitors/42").mock(
        return_value=httpx.Response(200, json={"data": _monitor_resource("42")})
    )

    result = json.loads(await call_tool(mcp, "betterstack_get_monitor", {"id": "42"}))

    assert result["id"] == "42"
    assert result["url"] == "https://example.com"


async def test_get_monitor_not_found_maps_404(mcp, credentials, betterstack_api):
    betterstack_api.get(f"{TEST_BASE_URL}/monitors/missing").mock(return_value=httpx.Response(404, json={}))

    result = json.loads(await call_tool(mcp, "betterstack_get_monitor", {"id": "missing"}))

    assert result == {"error": {"code": "not_found", "message": result["error"]["message"], "retryable": False}}


async def test_create_monitor_happy_path(mcp, credentials, betterstack_api):
    route = betterstack_api.post(f"{TEST_BASE_URL}/monitors").mock(
        return_value=httpx.Response(201, json={"data": _monitor_resource("99", url="https://new.example")})
    )

    result = json.loads(
        await call_tool(
            mcp,
            "betterstack_create_monitor",
            {"url": "https://new.example", "monitor_type": "status", "pronounceable_name": "New"},
        )
    )

    assert result["id"] == "99"
    assert result["url"] == "https://new.example"
    sent_body = json.loads(route.calls.last.request.content)
    assert sent_body == {"url": "https://new.example", "monitor_type": "status", "pronounceable_name": "New"}


async def test_create_monitor_missing_url_is_invalid_argument(mcp, credentials, betterstack_api):
    # "missing" is the empty-string case: the tool parameter is contractually
    # required by the MCP input schema, so an entirely absent argument is
    # rejected by protocol-level validation before our code runs. Passing an
    # empty string is the case our own validation (AC3) is responsible for.
    route = betterstack_api.post(f"{TEST_BASE_URL}/monitors").mock(return_value=httpx.Response(200, json={}))

    result = json.loads(
        await call_tool(
            mcp,
            "betterstack_create_monitor",
            {"url": "", "monitor_type": "status", "pronounceable_name": "New"},
        )
    )

    assert result["error"]["code"] == "invalid_argument"
    assert route.called is False


async def test_update_monitor_pauses_it(mcp, credentials, betterstack_api):
    route = betterstack_api.patch(f"{TEST_BASE_URL}/monitors/42").mock(
        return_value=httpx.Response(200, json={"data": _monitor_resource("42", paused=True)})
    )

    result = json.loads(await call_tool(mcp, "betterstack_update_monitor", {"id": "42", "paused": True}))

    assert result["paused"] is True
    sent_body = json.loads(route.calls.last.request.content)
    assert sent_body == {"paused": True}


async def test_update_monitor_not_found(mcp, credentials, betterstack_api):
    betterstack_api.patch(f"{TEST_BASE_URL}/monitors/missing").mock(return_value=httpx.Response(404, json={}))

    result = json.loads(await call_tool(mcp, "betterstack_update_monitor", {"id": "missing", "paused": True}))

    assert result["error"]["code"] == "not_found"


async def test_delete_monitor_requires_explicit_id(mcp, credentials, betterstack_api):
    route = betterstack_api.delete(f"{TEST_BASE_URL}/monitors/42").mock(return_value=httpx.Response(204))

    result = json.loads(await call_tool(mcp, "betterstack_delete_monitor", {"id": "42"}))

    assert result == {"deleted": True, "id": "42"}
    assert route.called is True
    tool = {t.name: t for t in await mcp.list_tools()}["betterstack_delete_monitor"]
    assert tool.annotations.destructiveHint is True
    assert set(tool.inputSchema["required"]) == {"id"}


async def test_delete_monitor_not_found(mcp, credentials, betterstack_api):
    betterstack_api.delete(f"{TEST_BASE_URL}/monitors/missing").mock(return_value=httpx.Response(404, json={}))

    result = json.loads(await call_tool(mcp, "betterstack_delete_monitor", {"id": "missing"}))

    assert result["error"]["code"] == "not_found"
