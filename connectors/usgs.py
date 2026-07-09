"""USGS critical-minerals connector stub."""

from __future__ import annotations


def lookup_criticality(mineral: str) -> dict:
    """Return local/official metadata about a mineral's criticality status.

    Expected output:
        A dictionary with mineral, source_type="USGS", evidence_type, URL,
        confidence, and caveats suitable for build_evidence_record(...).

    No network calls are made by this stub.
    """

    # TODO: Read from a curated USGS list export or fetch official pages in a
    # keyless, cacheable refresh script outside the core demo path.
    return {}


def search_usgs(query: str, mineral: str | None = None) -> list[dict]:
    """Search curated USGS metadata for Records Stage evidence records."""

    # TODO: Return list[dict] shaped like sample records.
    return []
