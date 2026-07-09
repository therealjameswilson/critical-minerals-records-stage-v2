"""Shared connector helpers.

Connector functions return dictionaries shaped like the sample records in
``examples/critical_minerals_sample/critical_minerals_sample.json``. Callers
can pass those records to the parser or serialize them to JSON/CSV before
building the cache.
"""

from __future__ import annotations

from datetime import datetime, timezone


def build_evidence_record(
    source: str,
    title: str,
    url: str,
    date: str,
    description: str = "",
    extra: dict | None = None,
) -> dict:
    """Build one metadata-only evidence record.

    Args:
        source: Human-readable source label, such as "USGS" or "FRUS / HistoryAtState".
        title: Record title or analyst-facing placeholder title.
        url: Stable source URL.
        date: ISO date string when known. Use YYYY-MM-DD when possible.
        description: Short summary or workflow note. Do not pass full body text.
        extra: Critical-minerals metadata fields such as minerals, countries,
            source_type, evidence_type, supply_chain_stage, and confidence.

    Returns:
        A dict compatible with the critical-minerals parser's input shape.
    """

    payload = dict(extra or {})
    payload.setdefault("retrieved_at", datetime.now(timezone.utc).date().isoformat())
    payload.setdefault("citation_url", url)
    return {
        "source": source,
        "date": date,
        "title": title,
        "url": url,
        "description": description,
        **payload,
    }
