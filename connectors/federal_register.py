"""Federal Register connector stub."""

from __future__ import annotations


def search_federal_register(
    query: str,
    agencies: list[str] | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
) -> list[dict]:
    """Search Federal Register metadata for critical-minerals notices.

    Expected output:
        Metadata records with source_type="Federal Register",
        evidence_type="policy_document" or "statistical_release", citation_url,
        agencies, and caveats.

    No network calls are made by this stub.
    """

    # TODO: Use the Federal Register API in a future connector refresh command.
    return []
