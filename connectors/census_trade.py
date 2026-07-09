"""Census International Trade API connector stub."""

from __future__ import annotations


def fetch_census_trade(
    flow: str,
    hs_codes: list[str],
    country: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    """Prepare Census trade-data metadata records.

    Args:
        flow: "imports" or "exports".
        hs_codes: HS / HTS / Schedule B codes to query.
        country: Optional partner country code or name.
        start: Optional YYYY-MM period/date.
        end: Optional YYYY-MM period/date.

    Expected output:
        Metadata records with source_type="Census",
        evidence_type="trade_data", hs_codes, caveats, and citation_url.

    No network calls are made by this stub.
    """

    # TODO: Use the Census API query builder and mineral_to_hs_codes.yml.
    return []
