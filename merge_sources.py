"""
Incremental cache merger.

If your corpus splits into independent sources (e.g. main archive + an
auxiliary timeline + a milestone list), refresh one source without
rebuilding the whole cache. Saves minutes-to-hours on large corpora.

Usage:
    python merge_sources.py --only "State Magazine"
    python merge_sources.py --only "State Magazine" --only "Milestones"

Algorithm:
    1. Load existing events_cache.json.
    2. Retain events whose ``source`` is NOT being refreshed.
    3. Re-run parser.parse_corpus() and filter to the refreshed source labels.
    4. Validate + score + threshold the fresh events.
    5. Resolve the taxonomy and re-enrich ALL events (retained + fresh) so the
       positional ``subject_indices`` and the emitted SUBJECT_TAXONOMY stay in
       lockstep — exactly as a full build would. (Re-enriching only the fresh
       events used to skew indices and, for free-form-subject corpora, wipe the
       taxonomy entirely.)
    6. Rewrite events_cache.json AND events_cache.js.
    7. Optionally splice the regenerated cache back into records-stage.html.

Adopters with only one source can ignore this module — use build_cache.py.
This produces the same taxonomy/index semantics as build_cache.build by
routing through its shared helpers.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import build_cache
import cache_format
import event_contract
import parser as adopter_parser
import scorer as adopter_scorer
from html_embed import sync_html_embed

log = logging.getLogger(__name__)


def merge(
    cache_json: Path,
    cache_js: Path,
    sources_to_refresh: list[str],
    source_root: Path,
    html_file: Path | None = None,
) -> dict:
    """Refresh ``sources_to_refresh`` in place. Returns a summary dict."""
    if not cache_json.exists():
        raise SystemExit(
            f"{cache_json} not found — run build_cache.py for a full build first."
        )

    by_day: dict[str, list[dict]] = json.loads(cache_json.read_text(encoding="utf-8"))
    refresh_set = set(sources_to_refresh)

    # 1. Split existing events into retained (other sources) vs removed.
    retained: list[dict] = []
    removed = 0
    for events in by_day.values():
        for e in events:
            if e.get("source") in refresh_set:
                removed += 1
            else:
                retained.append(e)

    # 2. Re-parse, filter to refresh_set, validate, score, threshold.
    fresh: list[dict] = []
    invalid = 0
    for event in adopter_parser.parse_corpus(source_root):
        if event.get("source") not in refresh_set:
            continue
        if event_contract.validate_event(event):
            invalid += 1
            continue
        event = dict(event)  # don't mutate the parser's dict
        event["score"] = adopter_scorer.score_event(event)
        if event["score"] >= cache_format.MIN_SCORE:
            fresh.append(event)
    if invalid:
        log.warning("Skipped %d fresh event(s) that don't match the data contract.", invalid)

    # 3. Resolve taxonomy over the COMBINED set and re-enrich everything, so
    #    retained and fresh events index into the same taxonomy ordering.
    combined = retained + fresh
    taxonomy_list = build_cache.resolve_taxonomy(combined)
    combined = build_cache.enrich_with_taxonomy(combined, taxonomy_list)

    # 4. Re-bucket + sort (shared with build_cache).
    by_day = build_cache.bucket_by_day(combined)

    # 5. Rewrite JSON.
    cache_json.write_text(
        json.dumps(by_day, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 6. Rewrite compact JS.
    compact_by_day = build_cache.build_compact(by_day)
    build_cache.write_compact_js(cache_js, compact_by_day, taxonomy_list)

    # 7. Splice into HTML if asked.
    html_synced = False
    if html_file and html_file.exists():
        html_synced = sync_html_embed(cache_js, html_file)

    return {
        "removed_stale": removed,
        "added_fresh": len(fresh),
        "invalid_skipped": invalid,
        "sources_refreshed": sorted(refresh_set),
        "taxonomy_subjects": len(taxonomy_list),
        "days_with_events": sum(1 for v in by_day.values() if v),
        "html_synced": html_synced,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="  %(message)s")
    ap = argparse.ArgumentParser(description="Incremental cache merge.")
    ap.add_argument(
        "--source-root",
        type=Path,
        required=True,
        help="Same path you pass to build_cache.py.",
    )
    ap.add_argument(
        "--only",
        action="append",
        required=True,
        help="Source label (matching event['source']) to refresh. Repeatable.",
    )
    ap.add_argument(
        "--cache-json", type=Path, default=Path(cache_format.DEFAULT_JSON_OUT)
    )
    ap.add_argument("--cache-js", type=Path, default=Path(cache_format.DEFAULT_JS_OUT))
    ap.add_argument(
        "--html",
        type=Path,
        default=Path("records-stage.html"),
        help="If present, splice the new cache into this HTML file in place.",
    )
    ap.add_argument(
        "--no-html-sync",
        action="store_true",
        help="Skip the records-stage.html splice step.",
    )
    args = ap.parse_args()
    html = None if args.no_html_sync else args.html
    summary = merge(args.cache_json, args.cache_js, args.only, args.source_root, html)
    print(summary)


if __name__ == "__main__":
    main()
