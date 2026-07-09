"""
Annex builder — combines several already-built Records Stage caches into one
**`records-stage-annex.html`**: a companion "appendix" instance that gathers
secondary / supplementary source collections behind the main OH Records Stage.

Out of the box it merges the three sibling instances:

  * Founders Online   (founders_events_cache.js — 7 founder editions)
  * Federal Register  (fr_events_cache.js       — State Dept + Presidential Docs)
  * The Reagan Diaries (reagan_events_cache.js   — the personal diary)

...but it is deliberately a *gathering*: add another collection by building its
own `*_events_cache.js` (any existing builder) and appending it to `SOURCES`
below (or `--cache`). No re-parsing of source corpora happens here — this reads
the compact caches those builders already produced and unions them.

How the merge stays correct
---------------------------
Each cache declares two JS globals: `SUBJECT_TAXONOMY` and `EVENTS_CACHE`
(compact, keyed by MM-DD). Merging is:

  * EVENTS_CACHE — union the day buckets (concatenate each MM-DD's event list).
  * SUBJECT_TAXONOMY — concatenate every source's taxonomy, and shift each
    source's per-event subject indices (`sb`) by the offset where that source's
    taxonomy lands in the combined list. So a source with its own taxonomy (the
    Federal Register has 646 subjects) keeps valid indices even when merged
    beside untagged collections (Founders / Reagan carry no taxonomy and no
    `sb`). This is what makes the annex extensible to future tagged sources.

It does NOT edit the shared shell: every source label auto-discovers into a
filter chip (unknown labels get the neutral `badge-generic`), so the 10 chips —
7 founder editions + Reagan + State Dept + Presidential Documents — appear with
no shell change.

Usage:
    python build_annex_stage.py
    python build_annex_stage.py --cache founders_events_cache.js --cache fr_events_cache.js
    python build_annex_stage.py --no-html-sync
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import html_embed

HERE = Path(__file__).resolve().parent
SHELL_HTML = HERE / "records-stage.html"          # the cleared, vendored shell
STAGE_TITLE = "Records Stage — Annex"              # <title> + <h1> for this instance

# The source caches gathered by default, in display order. Extend this list (or
# pass --cache) to add another collection to the annex.
SOURCES = [
    HERE / "founders_events_cache.js",
    HERE / "fr_events_cache.js",
    HERE / "reagan_events_cache.js",
]

DEFAULT_JSON_OUT = HERE / "annex_events_cache.json"
DEFAULT_JS_OUT = HERE / "annex_events_cache.js"
DEFAULT_HTML = HERE / "records-stage-annex.html"


def _load_cache(js_path: Path) -> tuple[list, dict]:
    """Extract (SUBJECT_TAXONOMY, EVENTS_CACHE) from a compact `*_events_cache.js`.

    The `\\uXXXX` escapes the writers emit (js_safe_dumps) are valid JSON string
    escapes, so `json.loads` decodes them directly — no un-escaping needed."""
    text = js_path.read_text(encoding="utf-8")
    tax_m = html_embed.TAX_RE.search(text)
    cache_m = html_embed.CACHE_RE.search(text)
    if not tax_m or not cache_m:
        raise SystemExit(
            f"{js_path.name}: could not find SUBJECT_TAXONOMY / EVENTS_CACHE. "
            "Is it a compact cache built by one of the build_*_stage.py scripts?"
        )
    tax = json.loads(tax_m.group(0)[len("const SUBJECT_TAXONOMY = "):-1])
    cache = json.loads(cache_m.group(0)[len("const EVENTS_CACHE = "):-1])
    return tax, cache


def merge_caches(cache_paths: list[Path]) -> tuple[dict, list, dict]:
    """Union the caches. Returns (compact_by_day, combined_taxonomy, per_source_counts).

    Subject indices (`sb`) are shifted per source so they stay valid against the
    concatenated taxonomy."""
    combined_tax: list = []
    by_day: dict[str, list] = defaultdict(list)
    per_source: dict[str, int] = defaultdict(int)

    for path in cache_paths:
        if not path.exists():
            raise SystemExit(
                f"{path.name} not found. Build it first with its own "
                "build_*_stage.py (e.g. `python build_reagan_stage.py`)."
            )
        tax, cache = _load_cache(path)
        offset = len(combined_tax)          # where this source's subjects will land
        combined_tax.extend(tax)

        for day, events in cache.items():
            for ev in events:
                if offset and "sb" in ev:   # remap indices into the combined taxonomy
                    ev = {**ev, "sb": [i + offset for i in ev["sb"]]}
                by_day[day].append(ev)
                per_source[ev.get("s") or ev.get("source") or "(unknown)"] += 1

    # The browser re-sorts each day by year; sort here too for a stable cache.
    for day in by_day:
        by_day[day].sort(key=lambda e: e.get("y", e.get("year", 0)))

    return dict(by_day), combined_tax, dict(per_source)


def _write_compact_js(js_out: Path, taxonomy: list, compact_by_day: dict) -> None:
    with open(js_out, "w", encoding="utf-8") as f:
        f.write("// Auto-generated by build_annex_stage.py. Do not edit.\n")
        f.write("const SUBJECT_TAXONOMY = ")
        f.write(html_embed.js_safe_dumps(taxonomy))
        f.write(";\n")
        f.write("const EVENTS_CACHE = ")
        f.write(html_embed.js_safe_dumps(compact_by_day))
        f.write(";\n")


def build(cache_paths: list[Path], json_out: Path, js_out: Path, html_out: Path | None) -> dict:
    if not SHELL_HTML.exists():
        raise SystemExit(f"{SHELL_HTML.name} (the Records Stage shell) not found.")

    by_day, taxonomy, per_source = merge_caches(cache_paths)

    json_out.write_text(json.dumps(by_day, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_compact_js(js_out, taxonomy, by_day)

    html_synced = False
    if html_out:
        # Start from the cleared, vendored shell so the result is always the
        # canonical Records Stage UI plus the merged data; retitle each run.
        shell = SHELL_HTML.read_text(encoding="utf-8")
        shell = shell.replace("<title>Records Stage</title>", f"<title>{STAGE_TITLE}</title>")
        shell = shell.replace("<h1>Records Stage</h1>", f"<h1>{STAGE_TITLE}</h1>")
        html_out.write_text(shell, encoding="utf-8")
        html_synced = html_embed.sync_html_embed(js_out, html_out)

    total = sum(len(v) for v in by_day.values())
    return {
        "sources_merged": [p.name for p in cache_paths],
        "events": total,
        "source_chips": len(per_source),
        "events_by_source": dict(sorted(per_source.items(), key=lambda kv: -kv[1])),
        "days_with_events": len(by_day),
        "taxonomy_subjects": len(taxonomy),
        "json_out": str(json_out),
        "js_out": str(js_out),
        "html": str(html_out) if html_out else None,
        "html_synced": html_synced,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build records-stage-annex.html (merged Records Stage UI).")
    ap.add_argument("--cache", action="append", type=Path,
                    help="A *_events_cache.js to merge (repeatable). Defaults to the 3 siblings.")
    ap.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    ap.add_argument("--js-out", type=Path, default=DEFAULT_JS_OUT)
    ap.add_argument("--html", type=Path, default=DEFAULT_HTML)
    ap.add_argument("--no-html-sync", action="store_true")
    args = ap.parse_args()

    cache_paths = args.cache if args.cache else SOURCES
    html = None if args.no_html_sync else args.html
    summary = build(cache_paths, args.json_out, args.js_out, html)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    if html and not summary["html_synced"]:
        print("  NOTE: HTML not spliced (shell missing or markers not found).")
    elif html:
        mb = args.html.stat().st_size / 1024 / 1024
        print(f"  ✓ {args.html.name} written ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
