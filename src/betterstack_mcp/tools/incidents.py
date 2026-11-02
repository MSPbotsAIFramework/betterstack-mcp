"""Incident list/get/acknowledge/resolve tools (AC6-AC9)."""

from __future__ import annotations

import json
import logging
from typing import Callable

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from betterstack_mcp.api_client import BetterStackClient
from betterstack_mcp.errors import BetterStackAPIError, error_from_api_exception
from betterstack_mcp.tools._pagination import (
    clamp_limit,
    flatten_resource,
    next_cursor_from_pagination,
    truncate_to_budget,
)

logger = logging.getLogger("betterstack_mcp.tools.incidents")

_INCIDENT_FIELDS = (
    "status",
    "started_at",
    "acknowledged_at",
    "resolved_at",
    "acknowledged_by",
    "resolved_by",
)


def register(mcp: FastMCP, client_factory: Callable[[], BetterStackClient]) -> None:
    @mcp.tool(
        description=(
            "List incidents, optionally filtered by monitor, status, or date range.\n"
            "Returns an empty list (not an error) if nothing matches."
        ),
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def betterstack_list_incidents(
        monitor_id: str | None = None,
        resolved: bool | None = None,
        acknowledged: bool | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> str:
        """List incidents.

        Args:
            monitor_id: Only incidents for this monitor.
            resolved: Filter to resolved (true) or still-open (false) incidents.
            acknowledged: Filter to acknowledged (true) or unacknowledged (false) incidents.
            from_date: ISO 8601 lower bound on started_at.
            to_date: ISO 8601 upper bound on started_at.
            limit: Max incidents to return (default 50, hard cap 200).
            cursor: Opaque pagination token from a previous call's next_cursor.
        """
        params: dict[str, object] = {"per_page": clamp_limit(limit)}
        if monitor_id:
            params["monitor_id"] = monitor_id
        if resolved is not None:
            params["resolved"] = "true" if resolved else "false"
        if acknowledged is not None:
            params["acknowledged"] = "true" if acknowledged else "false"
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if cursor:
            params["page"] = cursor

        async with client_factory() as client:
            try:
                body = await client.request("GET", "/incidents", params=params)
            except BetterStackAPIError as exc:
                return error_from_api_exception(exc)

        resources = (body or {}).get("data") or []
        items = [flatten_resource(r, _INCIDENT_FIELDS) for r in resources]
        next_cursor = next_cursor_from_pagination((body or {}).get("pagination"))
        items, has_more = truncate_to_budget(items, has_more=bool(next_cursor))
        return json.dumps(
            {"data": items, "has_more": has_more, "next_cursor": next_cursor if has_more else None},
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @mcp.tool(
        description="Get one BetterStack incident by id, including status and timestamps.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def betterstack_get_incident(id: str) -> str:
        """Get an incident's detail.

        Args:
            id: The incident's BetterStack id.
        """
        async with client_factory() as client:
            try:
                body = await client.request("GET", f"/incidents/{id}")
            except BetterStackAPIError as exc:
                return error_from_api_exception(exc)
        resource = (body or {}).get("data") or {}
        return json.dumps(flatten_resource(resource, _INCIDENT_FIELDS), separators=(",", ":"), ensure_ascii=False)

    @mcp.tool(
        description=(
            "Acknowledge an incident to claim it for triage.\n"
            "Safe to call again on an already-acknowledged incident -- it just succeeds."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
    )
    async def betterstack_acknowledge_incident(id: str) -> str:
        """Acknowledge an incident.

        Args:
            id: The incident's BetterStack id.
        """
        async with client_factory() as client:
            try:
                body = await client.request("POST", f"/incidents/{id}/acknowledge")
            except BetterStackAPIError as exc:
                return error_from_api_exception(exc)
        resource = (body or {}).get("data") or {}
        return json.dumps(flatten_resource(resource, _INCIDENT_FIELDS), separators=(",", ":"), ensure_ascii=False)

    @mcp.tool(
        description="Resolve a BetterStack incident, closing out the triage loop.",
        annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
    )
    async def betterstack_resolve_incident(id: str) -> str:
        """Resolve an incident.

        Args:
            id: The incident's BetterStack id.
        """
        async with client_factory() as client:
            try:
                body = await client.request("POST", f"/incidents/{id}/resolve")
            except BetterStackAPIError as exc:
                return error_from_api_exception(exc)
        resource = (body or {}).get("data") or {}
        return json.dumps(flatten_resource(resource, _INCIDENT_FIELDS), separators=(",", ":"), ensure_ascii=False)
