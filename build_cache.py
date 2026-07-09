"""
Generic cache builder.

Walks the adopter's corpus via ``parser.parse_corpus()``, validates each event
against the contract, scores it via ``scorer.score_event()``, optionally
enriches with a subject taxonomy, and writes both ``events_cache.json`` (full)
and ``events_cache.js`` (compact, embedded in the HTML tool).

The seams are:
  - parser.parse_corpus     (adopter)
  - scorer.score_event      (adopter)
  - taxonomy.load_taxonomy  (adopter, optional)
  - cache_format constants  (adopter tuning)

The taxonomy-resolution and compact-writing helpers are public so that
merge_sources.py reuses the exact same logic — the full build and the
incremental merge must produce identical taxonomy + index semantics.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path

import cache_format
import event_contract
import html_embed
import parser as adopter_parser
import scorer as adopter_scorer

log = logging.getLogger(__name__)


def build(source_root: Path, json_out: Path, js_out: Path) -> dict:
    """Build the cache end-to-end. Returns a summary dict."""
    # 1. Parse
    raw_events = list(adopter_parser.parse_corpus(source_root))

    # 2. Validate at the boundary, then score + threshold-filter in a single
    #    pass. Invalid events are dropped (and surfaced) rather than crashing
    #    the build with a raw KeyError mid-bucket.
    scored: list[dict] = []
    dropped_below_threshold = 0
    invalid_count = 0
    invalid_sample: list[dict] = []
    min_score = _resolve_min_score()
    for i, event in enumerate(raw_events):
        problems = event_contract.validate_event(event)
        if problems:
            invalid_count += 1
            if len(invalid_sample) < 5:
                label = (event.get("title") if isinstance(event, dict) else None) or f"event #{i}"
                invalid_sample.append({"event": str(label)[:60], "problems": problems})
            continue
        event = dict(event)  # don't mutate the parser's dict
        event["score"] = adopter_scorer.score_event(event)
        if event["score"] >= min_score:
            scored.append(event)
        else:
            dropped_below_threshold += 1

    if invalid_count:
        log.warning(
            "Dropped %d event(s) that don't match the data contract; "
            "first offenders: %s",
            invalid_count,
            "; ".join(f"{p['event']}: {', '.join(p['problems'])}" for p in invalid_sample),
        )

    # 3. Resolve + apply taxonomy (shared with merge_sources).
    taxonomy_list = resolve_taxonomy(scored)
    scored = enrich_with_taxonomy(scored, taxonomy_list)

    # 4. Bucket by MM-DD, sort by score within day
    by_day_dict = bucket_by_day(scored)

    # 5. Write full JSON
    json_out.write_text(
        json.dumps(by_day_dict, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 6. Write compact JS
    compact = build_compact(by_day_dict)
    write_compact_js(js_out, compact, taxonomy_list)

    return {
        "raw_events": len(raw_events),
        "invalid_dropped": invalid_count,
        "invalid_sample": invalid_sample,
        "scored_events": len(scored),
        "dropped_below_threshold": dropped_below_threshold,
        "days_with_events": len(by_day_dict),
        "taxonomy_subjects": len(taxonomy_list),
        "json_out": str(json_out),
        "js_out": str(js_out),
    }


# --------------------------------------------------------------------------
# Shared pipeline helpers (also used by merge_sources.py)
# --------------------------------------------------------------------------


def _resolve_min_score() -> int:
    """The score floor for cache inclusion.

    Prefers the adopter scorer's own threshold (e.g. the config-driven
    ``axis_scorer`` surfaces it via ``scorer.threshold()``, which the Tune
    scoring tab writes), but never drops below ``cache_format.MIN_SCORE`` — that
    stays a hard floor an adopter can raise. Taking the max means the editorial
    threshold set in the UI governs while the static floor still applies.
    """
    floor = int(cache_format.MIN_SCORE)
    try:
        import scorer as adopter_scorer_mod

        thr = getattr(adopter_scorer_mod, "threshold", None)
        if callable(thr):
            return max(floor, int(thr()))
    except Exception:
        pass
    return floor


def resolve_taxonomy(events: list[dict]) -> list[dict]:
    """Resolve the subject taxonomy for a set of events.

    Precedence:
      1. The adopter's ``load_taxonomy()`` (a controlled vocabulary).
      2. If they opted out but events carry free-form subjects, synthesize a
         flat taxonomy from the unique subject strings, grouped by
         ``subject_categories`` when the parser supplies them (else "Other").
      3. Otherwise ``[]`` — the subject filter UI hides itself.

    Sharing this between the full build and the incremental merge is what keeps
    both paths producing the same taxonomy and the same positional indices.
    """
    taxonomy_list = _load_taxonomy_optional()
    if taxonomy_list:
        return taxonomy_list

    if not any(e.get("subjects") for e in events):
        return []

    cat_for_subj: dict[str, str] = {}
    for e in events:
        sc = e.get("subject_categories") or {}
        for name in e.get("subjects", []):
            if name not in cat_for_subj and sc.get(name):
                cat_for_subj[name] = sc[name]
    unique = sorted({s for e in events for s in (e.get("subjects") or [])})
    return [
        {"name": s, "category": cat_for_subj.get(s, "Other"), "subcategory": "All"}
        for s in unique
    ]


def enrich_with_taxonomy(events: list[dict], taxonomy_list: list[dict]) -> list[dict]:
    """Populate ``subject_indices`` on every event against ``taxonomy_list``.
    No-op when the taxonomy is empty."""
    if not taxonomy_list:
        return events
    import taxonomy as adopter_taxonomy

    return adopter_taxonomy.enrich(events, taxonomy_list)


def bucket_by_day(events: list[dict]) -> dict[str, list[dict]]:
    """Group events into MM-DD buckets, each sorted by score descending."""
    by_day: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        by_day[f"{event['month']}-{event['day']}"].append(event)
    for key in by_day:
        by_day[key].sort(key=lambda e: -e.get("score", 0))
    return dict(by_day)


def _load_taxonomy_optional() -> list[dict]:
    """Try to load the adopter taxonomy. Return [] only when they opted out
    (NotImplementedError) or the module is absent. A taxonomy source that was
    configured but failed to load raises and aborts the build, rather than
    silently shipping a tool with the subject filter missing."""
    try:
        import taxonomy as adopter_taxonomy

        return adopter_taxonomy.load_taxonomy()
    except (ImportError, NotImplementedError):
        return []


def _slim_image(img: dict) -> dict:
    """Compact representation of one image entry.

    The full event["images"] list carries five fields per image, including
    a long-form description Claude generated during extraction. The
    publishing tool only needs a few of them to render the gallery, so we
    keep the compact cache lean by dropping `description`. Adopters that
    need the full descriptions in-browser (e.g. for AI tweet drafts that
    reason about image content) can grow this map."""
    return {
        "p": img.get("page"),                       # PDF page (1-indexed)
        "t": img.get("type", ""),                   # photograph | illustration | …
        "c": img.get("caption", ""),                # caption as printed
        "a": img.get("alt_text_suggestion", ""),    # short alt text
    }


def build_compact(by_day: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Convert full events to compact form per cache_format mappings.

    The mapping is an allow-list: only fields in COMPACT_FIELD_MAP /
    COMPACT_EXTRA_FIELDS survive, so body text, descriptions, month/day, etc.
    are dropped automatically without a separate deny-list to keep in sync.
    """
    out: dict[str, list[dict]] = {}
    for day, events in by_day.items():
        compact_events = []
        for ev in events:
            ce: dict = {}
            for full_key, short_key in cache_format.COMPACT_FIELD_MAP.items():
                if full_key not in ev:
                    continue
                val = ev[full_key]
                if full_key == "images" and isinstance(val, list):
                    val = [_slim_image(i) for i in val if isinstance(i, dict)]
                    if not val:
                        continue
                ce[short_key] = val
            extra = ev.get("extra") or {}
            for full_key, short_key in cache_format.COMPACT_EXTRA_FIELDS.items():
                if full_key in extra and extra[full_key] not in (None, ""):
                    ce[short_key] = extra[full_key]
            compact_events.append(ce)
        out[day] = compact_events
    return out


def write_compact_js(
    js_out: Path, compact_by_day: dict, taxonomy_list: list
) -> None:
    """Write events_cache.js with EVENTS_CACHE + SUBJECT_TAXONOMY globals.

    Both declarations are emitted on a single line via
    ``html_embed.js_safe_dumps`` so the splice readers (merge_sources, app)
    can match them robustly and the embedded data can't break out of the
    HTML <script> context.
    """
    compact_taxonomy = [
        {
            "n": t.get("name", t.get("n", "")),
            "c": t.get("category", t.get("c", "")),
            "sc": t.get("subcategory", t.get("sc", "")),
        }
        for t in taxonomy_list
    ]
    with open(js_out, "w", encoding="utf-8") as f:
        f.write("// Auto-generated by build_cache.py. Do not edit.\n")
        f.write("const SUBJECT_TAXONOMY = ")
        f.write(html_embed.js_safe_dumps(compact_taxonomy))
        f.write(";\n")
        f.write("const EVENTS_CACHE = ")
        f.write(html_embed.js_safe_dumps(compact_by_day))
        f.write(";\n")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="  %(message)s")
    ap = argparse.ArgumentParser(description="Build the events cache.")
    ap.add_argument(
        "--source-root",
        type=Path,
        required=True,
        help="Path to the corpus root that parser.parse_corpus() expects.",
    )
    ap.add_argument(
        "--json-out", type=Path, default=Path(cache_format.DEFAULT_JSON_OUT)
    )
    ap.add_argument("--js-out", type=Path, default=Path(cache_format.DEFAULT_JS_OUT))
    ap.add_argument(
        "--html-out",
        type=Path,
        default=Path("records-stage.html"),
        help="Records Stage HTML file to sync with the compact cache.",
    )
    ap.add_argument(
        "--skip-html-sync",
        action="store_true",
        help="Write JSON/JS only; do not embed the compact cache in records-stage.html.",
    )
    args = ap.parse_args()
    summary = build(args.source_root, args.json_out, args.js_out)
    if not args.skip_html_sync and args.html_out.exists():
        summary["html_synced"] = html_embed.sync_html_embed(args.js_out, args.html_out)
        summary["html_out"] = str(args.html_out)
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
