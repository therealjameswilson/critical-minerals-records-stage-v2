"""
Cache schema constants and compact-format definitions.

The cache has two representations:

1. **JSON** (events_cache.json) — full fields, source of truth, ~10–120 MB
   depending on corpus size. Not embedded in the HTML tool.

2. **JS compact** (events_cache.js) — embedded in the HTML tool. Drops fields
   the browser doesn't need; uses short keys to save bytes.

Both are keyed by `MM-DD` strings ("01-15", ..., "12-31"). Within each day,
events are sorted by score descending.

Adopters typically only need to touch:
  - MIN_SCORE (threshold for cache inclusion)
  - COMPACT_EXTRA_FIELDS (which extra.* fields surface in the HTML tool)
"""

# --- Tuning knobs ----------------------------------------------------------

# Hard floor for cache inclusion: events scoring below MIN_SCORE are dropped.
# Keep this at 0 and set the real editorial threshold in the Tune scoring tab
# (scoring_config.json → "threshold"); build_cache honors whichever is higher.
# Raise MIN_SCORE only if you want a floor the per-corpus config can't drop below.
MIN_SCORE: int = 0

# Path defaults (override on the build_cache.py command line as needed).
DEFAULT_JSON_OUT = "events_cache.json"
DEFAULT_JS_OUT = "events_cache.js"


# --- Compact-format field map ---------------------------------------------
#
# Long-form field name (in JSON) → compact key (in JS).
# When you add a corpus-specific field that the HTML tool needs to surface,
# add it here AND to the HTML tool's renderer.
#
# This map is an ALLOW-LIST: build_compact() copies only the fields listed
# here (plus COMPACT_EXTRA_FIELDS). Everything else — body text, description,
# date_display, month, day, etc. — is dropped from the browser cache
# automatically, so there is no separate deny-list that could drift out of
# sync with this one.

COMPACT_FIELD_MAP: dict[str, str] = {
    "year": "y",
    "title": "t",
    "url": "u",
    "source": "s",
    "score": "sc",
    "description": "de",
    "date_display": "dd",
    # Subject indices (filled in by taxonomy.enrich()).
    "subject_indices": "sb",
    # Optional per-event media (used by image- or video-rich corpora like
    # State Magazine). Adopters whose events don't carry these fields
    # see no behavior change — the HTML renders text-only cards.
    "thumbnail_url": "th",
    "media_type": "m",
    # Per-article image catalog (one entry per image inside the article).
    # build_cache slims each entry to {p, t, c, a} to keep the compact
    # cache small; full descriptions remain in events_cache.json.
    "images": "im",
}

# Fields lifted out of event["extra"] into the compact representation.
# Each entry maps the extra-dict key to a compact JS key.
# Examples from upstream FRUS toolkit:
#   "doc_type": "dt", "classification": "cl", "recently_published": "rp",
#   "country": "co", "traveler": "tr"
# For State Magazine the proposed additions are "au" (author) and "dp" (department).
COMPACT_EXTRA_FIELDS: dict[str, str] = {
    # FRUS adapter fields (data/frus/parser.py stashes these in event["extra"]).
    "doc_type": "dt",            # e.g. "Memorandum of Conversation"
    "classification": "cl",      # "Top Secret" | "Secret" | "Confidential" | ""
    "recently_published": "rp",  # bool
    "pub_year": "py",            # volume publication year (int)
    # Federal Register adapter fields (data/federal-register/parser.py).
    # Only emitted when present, so other sources are unaffected.
    "president": "pr",           # signing president, e.g. "Donald Trump"
    "eo_number": "eo",           # instrument number, e.g. "E.O. 14406"
    "citation": "ci",            # Federal Register citation, e.g. "91 FR 30479"
    # Critical Minerals Records Stage fields.
    "minerals": "mi",
    "countries": "cty",
    "source_type": "st",
    "evidence_type": "et",
    "supply_chain_stage": "ch",
    "fso_use_case": "fu",
    "agencies": "ag",
    "confidence": "cf",
    "hs_codes": "hs",
    "citation_url": "cu",
    "caveat": "cv",
    "record_id": "rid",
}
