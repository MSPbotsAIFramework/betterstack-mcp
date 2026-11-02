"""Monitor CRUD tools: list/get/create/update/delete (AC1-AC5)."""

from __future__ import annotations

import json
import logging
from typing import Callable

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from betterstack_mcp.api_client import BetterStackClient
from betterstack_mcp.errors import BetterStackAPIError, error_envelope, error_from_api_exception
from betterstack_mcp.tools._pagination import (
    clamp_limit,
    flatten_resource,
    next_cursor_from_pagination,
    truncate_to_budget,
)

logger = logging.getLogger("betterstack_mcp.tools.monitors")

_MONITOR_FIELDS = (
    "url",
    "pronounceable_name",
    "monitor_type",
    "status",
    "paused",
    "check_frequency",
)


def register(mcp: FastMCP, client_factory: Callable[[], BetterStackClient]) -> None:
    @mcp.tool(
        description=(
            "List uptime monitors, optionally filtered by URL or name.\n"
            "Returns an empty list (not an error) if nothing matches."
        ),
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def betterstack_list_monitors(
        url: str | None = None,
        pronounceable_name: str | None = None,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> str:
        """List monitors.

        Args:
            url: Exact URL/host to filter by.
            pronounceable_name: Exact monitor name to filter by.
            limit: Max monitors to return (default 50, hard cap 200).
            cursor: Opaque pagination token from a previous call's next_cursor.
        """
        per_page = clamp_limit(limit)
        params: dict[str, object] = {"per_page": per_page}
        if url:
            params["url"] = url
        if pronounceable_name:
            params["pronounceable_name"] = pronounceable_name
        if cursor:
            params["page"] = cursor

        async with client_factory() as client:
            try:
                body = await client.request("GET", "/monitors", params=params)
            except BetterStackAPIError as exc:
                return error_from_api_exception(exc)

        resources = (body or {}).get("data") or []
        items = [flatten_resource(r, _MONITOR_FIELDS) for r in resources]
        next_cursor = next_cursor_from_pagination((body or {}).get("pagination"))
        items, has_more = truncate_to_budget(items, has_more=bool(next_cursor))
        return json.dumps(
            {"data": items, "has_more": has_more, "next_cursor": next_cursor if has_more else None},
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @mcp.tool(
        description="Get one BetterStack monitor by id. Returns not_found if it does not exist.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def betterstack_get_monitor(id: str) -> str:
        """Get a monitor's detail fields.

        Args:
            id: The monitor's BetterStack id.
        """
        async with client_factory() as client:
            try:
                body = await client.request("GET", f"/monitors/{id}")
            except BetterStackAPIError as exc:
                return error_from_api_exception(exc)
        resource = (body or {}).get("data") or {}
        return json.dumps(flatten_resource(resource, _MONITOR_FIELDS), separators=(",", ":"), ensure_ascii=False)

    @mcp.tool(
        description="Create a new BetterStack uptime monitor for a URL.",
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
    )
    async def betterstack_create_monitor(
        url: str,
        monitor_type: str,
        pronounceable_name: str,
        check_frequency: int | None = None,
    ) -> str:
        """Create a monitor.

        Args:
            url: The URL or host to monitor.
            monitor_type: BetterStack monitor type, e.g. "status" or "expected_status_code".
            pronounceable_name: A short human-readable name BetterStack will read aloud on calls.
            check_frequency: Seconds between checks (BetterStack default applies if omitted).
        """
        if not url:
            return error_envelope("invalid_argument", "url is required to create a monitor")
        payload: dict[str, object] = {
            "url": url,
            "monitor_type": monitor_type,
            "pronounceable_name": pronounceable_name,
        }
        if check_frequency is not None:
            payload["check_frequency"] = check_frequency

        async with client_factory() as client:
            try:
                body = await client.request("POST", "/monitors", json_body=payload)
            except BetterStackAPIError as exc:
                return error_from_api_exception(exc)
        resource = (body or {}).get("data") or {}
        return json.dumps(flatten_resource(resource, _MONITOR_FIELDS), separators=(",", ":"), ensure_ascii=False)

    @mcp.tool(
        description=(
            "Update a BetterStack monitor's settings, including pausing/resuming it via "
            "the paused field."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
    )
    async def betterstack_update_monitor(
        id: str,
        paused: bool | None = None,
        check_frequency: int | None = None,
        pronounceable_name: str | None = None,
    ) -> str:
        """Update a monitor.

        Args:
            id: The monitor's BetterStack id.
            paused: Set true to pause checks, false to resume.
            check_frequency: New check interval in seconds.
            pronounceable_name: New display name.
        """
        payload: dict[str, object] = {}
        if paused is not None:
            payload["paused"] = paused
        if check_frequency is not None:
            payload["check_frequency"] = check_frequency
        if pronounceable_name is not None:
            payload["pronounceable_name"] = pronounceable_name

        async with client_factory() as client:
            try:
                body = await client.request("PATCH", f"/monitors/{id}", json_body=payload)
            except BetterStackAPIError as exc:
                return error_from_api_exception(exc)
        resource = (body or {}).get("data") or {}
        return json.dumps(flatten_resource(resource, _MONITOR_FIELDS), separators=(",", ":"), ensure_ascii=False)

    @mcp.tool(
        description=(
            "Delete a monitor by its id. This cannot be undone.\n"
            "Requires one explicit id; never deletes by filter or in bulk."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True),
    )
    async def betterstack_delete_monitor(id: str) -> str:
        """Delete a monitor by id.

        Args:
            id: The monitor's BetterStack id. Must be a single explicit id.
        """
        async with client_factory() as client:
            try:
                await client.request("DELETE", f"/monitors/{id}")
            except BetterStackAPIError as exc:
                return error_from_api_exception(exc)
        return json.dumps({"deleted": True, "id": id}, separators=(",", ":"), ensure_ascii=False)
