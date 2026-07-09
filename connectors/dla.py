"""DLA Strategic Materials connector stub."""

from __future__ import annotations


def search_dla(
    query: str,
    mineral: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
) -> list[dict]:
    """Search DLA Strategic Materials metadata.

    Expected output:
        Metadata records with source_type="DLA" and evidence focused on
        stockpiling, defense industrial base, recycling, or procurement.

    No network calls are made by this stub.
    """

    # TODO: Connect to curated DLA pages or notices. Do not scrape live pages in the MVP.
    return []
