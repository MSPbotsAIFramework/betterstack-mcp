"""Incident tool tests (AC6-AC9, TC-BS-012..017)."""

from __future__ import annotations

import json

import httpx

from tests.conftest import TEST_BASE_URL, call_tool


def _incident_resource(id_: str = "1", **attrs: object) -> dict:
    defaults = {
        "status": "started",
        "started_at": "2026-11-02T10:00:00Z",
        "acknowledged_at": None,
        "resolved_at": None,
        "acknowledged_by": None,
        "resolved_by": None,
    }
    defaults.update(attrs)
    return {"id": id_, "type": "incident", "attributes": defaults}


async def test_list_incidents_filters_by_resolved(mcp, credentials, betterstack_api):
    route = betterstack_api.get(f"{TEST_BASE_URL}/incidents").mock(
        return_value=httpx.Response(
            200, json={"data": [_incident_resource("1")], "pagination": {"next": None}}
        )
    )

    result = json.loads(await call_tool(mcp, "betterstack_list_incidents", {"resolved": False}))

    assert route.calls.last.request.url.params["resolved"] == "false"
    assert result["data"][0]["id"] == "1"
    assert result["data"][0]["status"] == "started"


async def test_list_incidents_empty_result_is_not_an_error(mcp, credentials, betterstack_api):
    betterstack_api.get(f"{TEST_BASE_URL}/incidents").mock(
        return_value=httpx.Response(200, json={"data": [], "pagination": {"next": None}})
    )

    result = json.loads(await call_tool(mcp, "betterstack_list_incidents", {"monitor_id": "no-such-monitor"}))

    assert result == {"data": [], "has_more": False, "next_cursor": None}


async def test_get_incident_returns_detail(mcp, credentials, betterstack_api):
    betterstack_api.get(f"{TEST_BASE_URL}/incidents/7").mock(
        return_value=httpx.Response(200, json={"data": _incident_resource("7", status="acknowledged")})
    )

    result = json.loads(await call_tool(mcp, "betterstack_get_incident", {"id": "7"}))

    assert result["id"] == "7"
    assert result["status"] == "acknowledged"


async def test_get_incident_not_found(mcp, credentials, betterstack_api):
    betterstack_api.get(f"{TEST_BASE_URL}/incidents/missing").mock(return_value=httpx.Response(404, json={}))

    result = json.loads(await call_tool(mcp, "betterstack_get_incident", {"id": "missing"}))

    assert result["error"]["code"] == "not_found"


async def test_acknowledge_incident_is_idempotent(mcp, credentials, betterstack_api):
    betterstack_api.post(f"{TEST_BASE_URL}/incidents/7/acknowledge").mock(
        return_value=httpx.Response(200, json={"data": _incident_resource("7", status="acknowledged")})
    )

    first = json.loads(await call_tool(mcp, "betterstack_acknowledge_incident", {"id": "7"}))
    second = json.loads(await call_tool(mcp, "betterstack_acknowledge_incident", {"id": "7"}))

    assert "error" not in first
    assert "error" not in second
    assert first["status"] == "acknowledged"
    assert second["status"] == "acknowledged"

    tool = {t.name: t for t in await mcp.list_tools()}["betterstack_acknowledge_incident"]
    assert tool.annotations.idempotentHint is True


async def test_resolve_incident_happy_path(mcp, credentials, betterstack_api):
    betterstack_api.post(f"{TEST_BASE_URL}/incidents/7/resolve").mock(
        return_value=httpx.Response(200, json={"data": _incident_resource("7", status="resolved")})
    )

    result = json.loads(await call_tool(mcp, "betterstack_resolve_incident", {"id": "7"}))

    assert result["status"] == "resolved"
