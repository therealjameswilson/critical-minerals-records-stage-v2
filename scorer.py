"""Critical-minerals scoring rules.

The score is intentionally simple and inspectable. It is not a claim about
historical importance; it is a sorting aid for Records Stage.
"""

from __future__ import annotations

from urllib.parse import urlparse


OFFICIAL_SOURCE_TYPES = {
    "FRUS",
    "NARA",
    "Census",
    "USGS",
    "DOE",
    "DLA",
    "Federal Register",
    "State",
    "Other USG",
}

STRONG_EVIDENCE_TYPES = {
    "historical_record",
    "archival_record",
    "trade_data",
    "policy_document",
    "statistical_release",
    "ministerial_document",
}

FSO_USE_CASES = {
    "meeting_prep",
    "reporting",
    "public_diplomacy",
    "investment_climate",
    "historical_context",
    "talking_points",
    "ministerial_follow_up",
    "evidence_pack",
    "questions_for_counterparts",
}

CRITICAL_TERMS = (
    "critical mineral",
    "critical minerals",
    "strategic mineral",
    "strategic minerals",
    "rare earth",
    "battery mineral",
    "supply chain",
    "stockpil",
)


def score_event(event: dict) -> int:
    """Return an integer relevance score for one event."""

    extra = event.get("extra") or {}
    score = 0

    source_type = str(extra.get("source_type") or "").strip()
    evidence_type = str(extra.get("evidence_type") or "").strip()
    minerals = _as_list(extra.get("minerals"))
    countries = _as_list(extra.get("countries"))
    agencies = _as_list(extra.get("agencies"))
    stages = _as_list(extra.get("supply_chain_stage"))
    use_cases = _as_list(extra.get("fso_use_case"))
    hs_codes = _as_list(extra.get("hs_codes"))

    if source_type in OFFICIAL_SOURCE_TYPES:
        score += 22
    if _official_url(event.get("url", "")) or _official_url(extra.get("citation_url", "")):
        score += 8
    if evidence_type in STRONG_EVIDENCE_TYPES:
        score += 10

    searchable = " ".join(
        str(v or "")
        for v in [
            event.get("title"),
            event.get("description"),
            " ".join(event.get("subjects") or []),
            " ".join(minerals),
            " ".join(stages),
        ]
    ).lower()
    if any(term in searchable for term in CRITICAL_TERMS):
        score += 14

    if minerals:
        score += min(18, 8 + 2 * len(minerals))
    if countries:
        score += min(12, 6 + len(countries))
    if agencies:
        score += min(8, 3 + len(agencies))
    if stages:
        score += min(10, 4 + len(stages))
    if set(use_cases) & FSO_USE_CASES:
        score += min(14, 6 + 2 * len(set(use_cases) & FSO_USE_CASES))
    if hs_codes:
        score += 5

    if evidence_type in {"historical_record", "archival_record"}:
        score += 8
    if evidence_type in {"policy_document", "statistical_release", "trade_data", "ministerial_document"}:
        score += 8

    confidence = str(extra.get("confidence") or "").lower()
    if confidence == "high":
        score += 12
    elif confidence == "medium":
        score += 6
    elif confidence == "low":
        score -= 4

    description = str(event.get("description") or "").strip()
    if len(description) >= 80:
        score += 6
    elif description:
        score += 3

    citation_url = str(extra.get("citation_url") or event.get("url") or "").strip()
    if citation_url.startswith("https://"):
        score += 5
    elif citation_url:
        score += 2

    caveat = str(extra.get("caveat") or "").strip()
    if caveat:
        score += 2

    return int(max(score, 0))


def _as_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def _official_url(url: str) -> bool:
    try:
        host = urlparse(str(url)).netloc.lower()
    except Exception:
        return False
    return host.endswith(".gov") or host.endswith(".mil") or host == "history.state.gov"
