"""FRUS / HistoryAtState connector stub.

TODO: Implement against a local FRUS XML checkout or HistoryAtState metadata
exports. Do not fetch full document body text into the Records Stage cache.
"""

from __future__ import annotations


def search_frus(
    query: str,
    country: str | None = None,
    mineral: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
) -> list[dict]:
    """Search FRUS metadata for critical-minerals evidence.

    Expected output:
        A list of metadata records shaped like the sample JSON records, with
        source_type="FRUS" and evidence_type="historical_record".

    No network calls are made by this stub.
    """

    # TODO: Search local FRUS TEI metadata and return build_evidence_record(...)
    # dictionaries with URL, title, date, subjects, minerals, countries, and caveats.
    return []
