"""
Theme classifier for Federal Register subjects.

The FR's subject vocabulary (CFR indexing terms + table-of-contents groupings)
is flat — hundreds of terms with no built-in hierarchy. ``theme_for()`` buckets
each subject into one of a dozen broad themes so the publishing tool's subject
filter has a meaningful top tier (Theme -> Subject) instead of one giant list.

It's deliberately heuristic and keyword-driven. Rules are evaluated in order and
the first match wins, so more specific themes are listed before broad ones. To
re-bucket a subject, adjust the keyword lists below and rebuild the cache.
"""

from __future__ import annotations

# (theme, [keywords]) — ordered; first keyword hit wins.
_RULES: list[tuple[str, list[str]]] = [
    ("Sanctions & Export Control", [
        "sanction", "export control", "embargo", "designation", "blocked", "blocking",
        "ofac", "specially designated", "nonproliferation", "proliferation",
        "munitions", "arms export", "international traffic in arms", "itar",
        "defense trade", "dual-use", "terrorist", "terrorism", "entities pursuant",
        "executive order 13382", "executive order 13224", "weapons of mass",
    ]),
    ("Immigration, Passports & Consular", [
        "passport", "visa", "consular", "immigration", "citizenship", "nationality",
        "naturalization", "refugee", "asylum", "alien", "birth abroad", "emigration",
    ]),
    ("Treaties & International Agreements", [
        "treaty", "treaties", "international agreement", "convention", "protocol",
        "agreement",
    ]),
    ("Human Rights & Democracy", [
        "human rights", "democracy", "trafficking", "war crimes", "atrocit",
        "religious freedom", "genocide", "labor rights",
    ]),
    ("Defense & National Security", [
        "defense", "national security", "military", "arms", "weapon", "nuclear",
        "missile", "security assistance", "wartime",
    ]),
    ("Cultural, Educational & Exchange", [
        "cultural", "culturally significant", "education", "exchange", "fulbright",
        "scholar", "academic", "museum", "exhibition", "heritage", "student", "art ",
    ]),
    ("Health & Social Services", [
        "health", "disease", "medical", "drug", "adoption", "foster care",
        "welfare", "child", "social services",
    ]),
    ("Environment, Energy & Oceans", [
        "environment", "energy", "climate", "ocean", "marine", "fishery",
        "fisheries", "wildlife", "pollution", "arctic", "antarctic", "water",
    ]),
    ("Science, Technology & Communications", [
        "science", "technolog", "telecommunication", "cyber", "internet", "space",
        "satellite", "spectrum", "research", "digital", "communications",
    ]),
    ("Transportation", [
        "transportation", "aviation", "aircraft", "maritime", "shipping", "vessel",
        "port", "railroad", "motor vehicle",
    ]),
    ("Grants, Acquisition & Procurement", [
        "acquisition", "grant", "procurement", "contract", "cooperative agreement",
        "assistance",
    ]),
    ("Finance, Accounting & Fees", [
        "accounting", "fee", "financial", "budget", "appropriation", "claims",
        "debt", "loan", "tax", "customs duties",
    ]),
    ("Information Collection & Paperwork", [
        "information collection", "paperwork", "omb", "survey", "recordkeeping",
        "reporting and recordkeeping",
    ]),
    ("Meetings & Advisory Bodies", [
        "meeting", "advisory committee", "advisory board", "hearing", "proceeding",
        "council", "commission", "panel", "board", "conference",
    ]),
    ("Administrative & Regulatory", [
        "administrative practice", "organization and functions", "delegation",
        "privacy act", "freedom of information", "foia", "regulation", "rulemaking",
        "records", "procedure", "government employees", "officials", "reports",
    ]),
]

DEFAULT_THEME = "Other"


def theme_for(name: str) -> str:
    n = (name or "").lower()
    for theme, keywords in _RULES:
        for kw in keywords:
            if kw in n:
                return theme
    return DEFAULT_THEME
