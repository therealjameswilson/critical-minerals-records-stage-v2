"""DOE critical-materials connector stub."""

from __future__ import annotations


def lookup_criticality(mineral: str) -> dict:
    """Return DOE energy critical-materials metadata for one mineral.

    Expected output:
        Metadata describing DOE assessment source, technology relevance,
        confidence, caveats, and citation_url.

    No network calls are made by this stub.
    """

    # TODO: Connect to curated DOE Critical Materials Assessment metadata.
    return {}


def search_doe(query: str, mineral: str | None = None) -> list[dict]:
    """Search DOE metadata for critical-materials evidence records."""

    # TODO: Return list[dict] shaped like sample records.
    return []
