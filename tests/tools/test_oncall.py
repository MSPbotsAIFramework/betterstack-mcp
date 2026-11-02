"""On-call tool tests (AC10-AC11, TC-BS-018..020)."""

from __future__ import annotations

import json

import httpx

from tests.conftest import TEST_BASE_URL, call_tool


async def test_list_oncall_schedules(mcp, credentials, betterstack_api):
    route = betterstack_api.get(f"{TEST_BASE_URL}/on-calls").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "s1", "type": "on_call_calendar", "attributes": {"name": "Primary"}},
                    {"id": "s2", "type": "on_call_calendar", "attributes": {"name": "Secondary"}},
                ],
                "pagination": {"next": None},
            },
        )
    )

    result = json.loads(await call_tool(mcp, "betterstack_list_oncall_schedules", {}))

    assert route.calls.last.request.url.params["per_page"] == "50"
    assert result["data"] == [{"id": "s1", "name": "Primary"}, {"id": "s2", "name": "Secondary"}]


async def test_list_oncall_events_default_schedule_now(mcp, credentials, betterstack_api):
    betterstack_api.get(f"{TEST_BASE_URL}/on-calls/default/events").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "evt-1",
                        "type": "on_call_event",
                        "attributes": {
                            "user_name": "Alex",
                            "starts_at": "2026-11-02T00:00:00Z",
                            "ends_at": "2026-11-09T00:00:00Z",
                        },
                    }
                ]
            },
        )
    )

    result = json.loads(await call_tool(mcp, "betterstack_list_oncall_events", {}))

    assert result["data"] == [
        {"event_id": "evt-1", "user_name": "Alex", "starts_at": "2026-11-02T00:00:00Z", "ends_at": "2026-11-09T00:00:00Z"}
    ]
    assert result["has_more"] is False


async def test_list_oncall_events_unknown_schedule_not_found(mcp, credentials, betterstack_api):
    betterstack_api.get(f"{TEST_BASE_URL}/on-calls/bogus-schedule/events").mock(
        return_value=httpx.Response(404, json={})
    )

    result = json.loads(await call_tool(mcp, "betterstack_list_oncall_events", {"schedule_id": "bogus-schedule"}))

    assert result["error"]["code"] == "not_found"
