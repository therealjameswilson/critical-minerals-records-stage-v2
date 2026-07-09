"""State Department release and report connector stub."""

from __future__ import annotations


def search_state_releases(
    query: str,
    country: str | None = None,
    mineral: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
) -> list[dict]:
    """Search curated State Department release/report metadata.

    Expected output:
        Metadata records with source_type="State" and evidence_type such as
        ministerial_document or policy_document.

    No network calls are made by this stub.
    """

    # TODO: Build from a curated release index or operator-provided source file.
    return []
