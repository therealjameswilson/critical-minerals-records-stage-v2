"""
The event contract — the single shape ``parser.parse_corpus()`` must yield.

Both the CLI (build_cache.py) and the setup UI (app.py) validate against this,
so the contract is enforced at the boundary instead of crashing mid-build with
a raw ``KeyError`` on ``event['month']``. See docs/data-contract.md for the
prose version.

An event is a dict with at least:

    source   str            label shown on every event (your archive's name)
    year     int | str      four-digit year
    month    "01".."12"     1-2 digit month (used in the MM-DD cache key)
    day      "01".."31"     1-2 digit day   (used in the MM-DD cache key)
    title    str            non-empty headline / document name
    url      str            link to the document (may be "")

Optional but recognized: subjects (list[str]), subject_categories (dict),
description, date_display, thumbnail_url, media_type, images (list[dict]),
score (filled by the scorer), extra (dict of corpus-specific fields).
"""

from __future__ import annotations

REQUIRED_FIELDS = ("source", "year", "month", "day", "title", "url")


def validate_event(event: object) -> list[str]:
    """Return a list of human-readable problems with one event ([] if valid)."""
    if not isinstance(event, dict):
        return [f"event is {type(event).__name__}, expected a dict"]

    problems: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in event:
            problems.append(f"missing required field '{field}'")

    if not str(event.get("title") or "").strip() and "title" in event:
        problems.append("field 'title' is empty")

    # month/day must be 1-2 digit values in range so the MM-DD bucket key is
    # well-formed and actually reachable from the HTML tool's calendar.
    for field, hi in (("month", 12), ("day", 31)):
        if field not in event:
            continue
        raw = event[field]
        s = str(raw).strip()
        if not (s.isdigit() and 1 <= len(s) <= 2 and 1 <= int(s) <= hi):
            problems.append(
                f"field '{field}'={raw!r} is not a valid 1-2 digit {field} (1-{hi})"
            )
    return problems


def validate_events(events: list[dict], *, sample_limit: int = 5) -> dict:
    """Validate a batch. Returns a summary dict:

        {"ok": bool, "invalid": int, "problems": [{"event": str, "problems": [...]}]}

    ``problems`` carries only the first ``sample_limit`` offenders, enough to
    show the adopter what to fix without flooding the UI on a large corpus.
    """
    invalid = 0
    sample: list[dict] = []
    for i, ev in enumerate(events):
        probs = validate_event(ev)
        if probs:
            invalid += 1
            if len(sample) < sample_limit:
                label = (ev.get("title") if isinstance(ev, dict) else None) or f"event #{i}"
                sample.append({"event": str(label)[:60], "problems": probs})
    return {"ok": invalid == 0, "invalid": invalid, "problems": sample}
