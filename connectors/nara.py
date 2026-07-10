"""Metadata-only client for the National Archives Catalog API v2.

The module reads ``NARA_API_KEY`` from the process environment, sends it only
in the server-side ``x-api-key`` header, and returns a minimal normalized shape.
It never writes responses to disk. GitHub Pages must use the deployment proxy
documented in ``docs/nara-integration.md`` rather than importing this module.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


NARA_SEARCH_URL = "https://catalog.archives.gov/api/v2/records/search"


def _walk_first(node: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(node, dict):
        for key in keys:
            if key in node and node[key] not in (None, "", [], {}):
                return node[key]
        for value in node.values():
            found = _walk_first(value, keys)
            if found not in (None, "", [], {}):
                return found
    elif isinstance(node, list):
        for value in node:
            found = _walk_first(value, keys)
            if found not in (None, "", [], {}):
                return found
    return None


def _find_hits(node: Any) -> list[dict]:
    if isinstance(node, dict):
        if isinstance(node.get("hits"), list):
            return node["hits"]
        for value in node.values():
            found = _find_hits(value)
            if found:
                return found
    return []


def _record_naid(hit: dict) -> str | None:
    candidate = hit.get("_id")
    if candidate is not None and str(candidate).strip().isdigit():
        return str(candidate).strip()
    candidate = _walk_first(hit.get("_source", hit), ("naId",))
    return str(candidate) if candidate is not None else None


def _logical_date(value: Any) -> str | None:
    if isinstance(value, dict):
        if value.get("logicalDate"):
            return str(value["logicalDate"])
        for item in value.values():
            date = _logical_date(item)
            if date:
                return date
    elif isinstance(value, list):
        for item in value:
            date = _logical_date(item)
            if date:
                return date
    return None


def normalize_nara_hit(hit: dict, retrieved_at: str) -> dict:
    """Reduce one API hit to catalog metadata; no extracted body text is kept."""
    source = hit.get("_source", hit)
    naid = _record_naid(hit)
    date = _logical_date(_walk_first(source, (
        "productionDates", "inclusiveStartDate", "coverageStartDate", "releaseDates"
    )))
    catalog_url = f"https://catalog.archives.gov/id/{naid}" if naid else "https://catalog.archives.gov/"
    return {
        "naid": naid,
        "title": str(_walk_first(source, ("title",)) or "Untitled NARA description"),
        "date": date,
        "level_of_description": _walk_first(source, ("levelOfDescription",)),
        "record_group_number": _walk_first(source, ("recordGroupNumber",)),
        "general_records_types": _walk_first(source, ("generalRecordsTypes",)) or [],
        "creator": _walk_first(source, ("creators", "creatingOrganizations")),
        "scope_note": _walk_first(source, ("scopeAndContentNote", "scopeAndContent")),
        "use_restriction": _walk_first(source, ("useRestriction",)),
        "catalog_url": catalog_url,
        "retrieved_at": retrieved_at,
        "record_status": "live",
        "source_type": "NARA",
        "evidence_type": "archival_record",
        "relevance": "unreviewed archival lead",
        "caveat": "Catalog metadata requires substantive relevance review before citation as evidence."
    }


def search_nara(
    query: str,
    date_start: str | None = None,
    date_end: str | None = None,
    available_online: bool = True,
    record_groups: list[str] | None = None,
    limit: int = 25,
) -> list[dict]:
    """Search NARA and return sanitized live archival descriptions.

    ``date_start`` and ``date_end`` must use the same NARA-supported precision:
    YYYY, YYYY-MM, or YYYY-MM-DD. ``record_groups`` is sent as a boolean OR
    expression when more than one group is supplied. The API key is required in
    the environment and is never included in the returned dictionaries.
    """
    query = query.strip()
    if not query:
        raise ValueError("query is required")
    if bool(date_start) != bool(date_end):
        raise ValueError("date_start and date_end must be supplied together")
    key = os.environ.get("NARA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("NARA_API_KEY is not configured")

    params = {
        "q": query,
        "limit": str(max(1, min(100, int(limit)))),
        "availableOnline": str(bool(available_online)).lower(),
    }
    if date_start and date_end:
        params["startDate"] = date_start
        params["endDate"] = date_end
    groups = [str(group).strip() for group in (record_groups or []) if str(group).strip()]
    if groups:
        params["recordGroupNumber"] = groups[0] if len(groups) == 1 else " OR ".join(groups)

    url = f"{NARA_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-api-key": key,
        "User-Agent": "critical-minerals-history-pilot/2.0"
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    retrieved_at = datetime.now(timezone.utc).isoformat()
    return [normalize_nara_hit(hit, retrieved_at) for hit in _find_hits(payload)]
