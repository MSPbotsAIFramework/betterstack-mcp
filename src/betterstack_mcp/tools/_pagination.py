"""Shared helpers for turning BetterStack's JSON:API list responses into the
compact, token-economical shape required by SOP section 2.5: clamp limit,
trim each resource to the fields an Agent needs, surface has_more/next_cursor
instead of forwarding BetterStack's raw pagination links.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlparse

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_RESPONSE_CHARS = 20_000


def clamp_limit(limit: int | None) -> int:
    if limit is None or limit <= 0:
        return DEFAULT_LIMIT
    return min(limit, MAX_LIMIT)


def next_cursor_from_pagination(pagination: dict[str, Any] | None) -> str | None:
    """BetterStack returns a 'next' URL (or null) in the pagination block.

    We never forward that URL to the Agent (it leaks our upstream host); we
    extract just the opaque 'page' query param so it round-trips as our own
    'cursor' value on the next call.
    """
    if not pagination:
        return None
    next_url = pagination.get("next")
    if not next_url:
        return None
    query = parse_qs(urlparse(next_url).query)
    page_values = query.get("page")
    return page_values[0] if page_values else None


def flatten_resource(resource: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """Flatten a JSON:API {id, type, attributes: {...}} resource to {id, <fields>}."""
    attributes = resource.get("attributes") or {}
    out: dict[str, Any] = {"id": resource.get("id")}
    for field in fields:
        if field in attributes:
            out[field] = attributes[field]
    return out


def truncate_to_budget(items: list[dict[str, Any]], *, has_more: bool) -> tuple[list[dict[str, Any]], bool]:
    """Enforce the 20,000-character response budget (SOP section 2.5).

    The character cap wins over any count-based limit: if the serialized
    items would exceed it, we drop trailing items and force has_more=true.
    """
    kept: list[dict[str, Any]] = []
    running_len = len("[]")
    for item in items:
        item_len = len(json.dumps(item, separators=(",", ":"), ensure_ascii=False)) + 1
        if running_len + item_len > MAX_RESPONSE_CHARS and kept:
            return kept, True
        kept.append(item)
        running_len += item_len
    return kept, has_more
