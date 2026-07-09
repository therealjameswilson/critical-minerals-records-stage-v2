"""NARA Catalog API connector stub.

TODO: Implement API v2 search using an operator-provided API key. Do not store
or hardcode keys; read them from environment variables or a local ignored file.
"""

from __future__ import annotations


def search_nara(
    query: str,
    date_start: str | None = None,
    date_end: str | None = None,
    available_online: bool = True,
) -> list[dict]:
    """Return NARA archival metadata records for a query.

    Expected output:
        A list of metadata-only records with stable Catalog URLs, NAIDs in
        record_id when available, source_type="NARA", and
        evidence_type="archival_record".

    No network calls are made by this stub.
    """

    # TODO: Call the Catalog API only when a key is supplied safely by the operator.
    return []
