"""On-call visibility tools: list schedules, list who's on call (AC10-AC11).

Read-only by design (see docs/tickets/PRD-21258.md "Decisions made by
DEV01") -- editing on-call rotations is left to BetterStack's own UI in v1.
"""

from __future__ import annotations

import json
import logging
from typing import Callable

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from betterstack_mcp.api_client import BetterStackClient
from betterstack_mcp.errors import BetterStackAPIError, error_from_api_exception
from betterstack_mcp.telemetry import logged_tool
from betterstack_mcp.tools._pagination import (
    clamp_limit,
    flatten_resource,
    next_cursor_from_pagination,
    truncate_to_budget,
)

logger = logging.getLogger("betterstack_mcp.tools.oncall")

_SCHEDULE_FIELDS = ("name",)
_EVENT_FIELDS = ("user_name", "starts_at", "ends_at")


def register(mcp: FastMCP, client_factory: Callable[[], BetterStackClient]) -> None:
    @mcp.tool(
        description="List BetterStack on-call schedules (id and name only).",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    @logged_tool
    async def betterstack_list_oncall_schedules(limit: int | None = 50, cursor: str | None = None) -> str:
        """List on-call schedules.

        Args:
            limit: Max schedules to return (default 50, hard cap 200).
            cursor: Opaque pagination token from a previous call's next_cursor.
        """
        params: dict[str, object] = {"per_page": clamp_limit(limit)}
        if cursor:
            params["page"] = cursor

        async with client_factory() as client:
            try:
                body = await client.request("GET", "/on-calls", params=params)
            except BetterStackAPIError as exc:
                return error_from_api_exception(exc)

        resources = (body or {}).get("data") or []
        items = [flatten_resource(r, _SCHEDULE_FIELDS) for r in resources]
        next_cursor = next_cursor_from_pagination((body or {}).get("pagination"))
        items, has_more = truncate_to_budget(items, has_more=bool(next_cursor))
        return json.dumps(
            {"data": items, "has_more": has_more, "next_cursor": next_cursor if has_more else None},
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @mcp.tool(
        description=(
            "List who is on call for a schedule, in a given time window.\n"
            "Defaults to the 'default' schedule and the events covering right now."
        ),
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    @logged_tool
    async def betterstack_list_oncall_events(
        schedule_id: str = "default",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> str:
        """List on-call events (who's on call and when).

        Args:
            schedule_id: Which schedule to query; "default" if the team has one schedule.
            from_date: ISO 8601 lower bound on the shift window.
            to_date: ISO 8601 upper bound on the shift window.
        """
        params: dict[str, object] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        async with client_factory() as client:
            try:
                body = await client.request("GET", f"/on-calls/{schedule_id}/events", params=params)
            except BetterStackAPIError as exc:
                return error_from_api_exception(exc)

        resources = (body or {}).get("data") or []
        items = []
        for resource in resources:
            flat = flatten_resource(resource, _EVENT_FIELDS)
            flat["event_id"] = flat.pop("id")
            items.append(flat)
        # This endpoint has no upstream pagination (SOP risk note in the tech
        # design): we enforce our own response-size budget regardless of how
        # many events BetterStack returns.
        items, has_more = truncate_to_budget(items, has_more=False)
        return json.dumps({"data": items, "has_more": has_more}, separators=(",", ":"), ensure_ascii=False)
