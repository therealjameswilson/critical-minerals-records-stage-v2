"""
Reagan Diaries edition builder for the Records Stage shell.

Produces **`reagan-diaries-stage.html`**: the *standard* Records Stage UI — the
same shell as `records-stage.html` / `founders-online-stage.html` — with Ronald
Reagan's personal presidential diary (Jan 1981 – Jan 1989) spliced in.

That means it inherits, for free, the toolkit's graphic design and layout, the
multi-tweet preset campaign builder, the clearance editor, Word export, and the
shared image-search modal (NARA Catalog + Wikimedia Commons + Library of
Congress).

Mapping into the event contract (see `event_contract.py`):
  * source  = "The Reagan Diaries" for every entry (one source-filter chip; the
              diary is a single homogeneous corpus, unlike Founders' 7 editions).
  * year / month / day  from the entry's `date` attr (`YYYY-MM-DD`); month/day
              are zero-padded so the bucket key matches the shell's
              `String(month).padStart(2,"0")`-style lookup. One entry per real
              calendar date, so "Browse by Date / On This Day" surfaces every
              year that shares an MM-DD (e.g. Jan 20 → 1981 and 1989).
  * title   = the FULL entry text (all <p> paragraphs joined, whitespace
              normalized). In this shell `title` is the ONLY field that search
              scans and the AI drafter reads, so putting the diary prose here is
              what makes the entries searchable and draftable — see
              docs/reagan-diaries-build.md.
  * url     = a per-entry deep link to the Reagan Foundation's published entry,
              reconstructed as .../diary-entry-MMDDYYYY (the original scraped
              source-urls, reaganfoundation.org/xml/*.xml, are all 404 now). A
              small fraction of entries have no published page and will 404;
              that is strictly better than the dead XML links and no worse than
              a static landing page for the ~96% that resolve.
  No score (the shell only badges/min-score-filters FRUS), no subjects (the
  diary carries none) — so the compact event is just {y,t,u,s}.

It does NOT edit the shared shell: the single unknown source renders with the
neutral fallback badge, and the AI drafter / image modal are already
source-agnostic.

Source data: `data/reagan-diaries/diary.xml` (~3.7 MB, gitignored). A 2013
transcription of the Reagan Foundation XML editions of the personal diary.

Usage:
    python build_reagan_stage.py
    python build_reagan_stage.py --no-html-sync
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import event_contract
import html_embed

HERE = Path(__file__).resolve().parent
XML_FILE = HERE / "data" / "reagan-diaries" / "diary.xml"   # the corpus (gitignored)
SHELL_HTML = HERE / "records-stage.html"                    # the cleared, vendored shell
STAGE_TITLE = "The Reagan Diaries — Records Stage"           # <title> + <h1> for this instance
SOURCE_LABEL = "The Reagan Diaries"                          # the single source-filter chip
DEFAULT_JSON_OUT = HERE / "reagan_events_cache.json"
DEFAULT_JS_OUT = HERE / "reagan_events_cache.js"
DEFAULT_HTML = HERE / "reagan-diaries-stage.html"

# Every published entry lives at this stem + MMDDYYYY.
ENTRY_URL_STEM = "https://www.reaganfoundation.org/ronald-reagan/white-house-diaries/diary-entry-"


def _entry_text(entry: ET.Element) -> str:
    """Join all <body>//<p> paragraphs into one whitespace-normalized string.

    The XML indents paragraph text across several lines; ``" ".join(split())``
    collapses those runs, and paragraphs are joined by a single space (the shell
    renders the title in one wrapping div, so paragraph breaks don't survive
    anyway)."""
    parts: list[str] = []
    for p in entry.iter("p"):
        # itertext() picks up any nested inline markup; usually just the text.
        text = " ".join("".join(p.itertext()).split())
        if text:
            parts.append(text)
    return " ".join(parts)


def parse_reagan(xml_path: Path) -> tuple[list[dict], int]:
    """Read the diary XML and emit toolkit event dicts. Returns
    (events, skipped) where skipped counts bad-date or empty-body entries."""
    root = ET.parse(xml_path).getroot()
    events: list[dict] = []
    skipped = 0
    for entry in root.findall("entry"):
        date = (entry.get("date") or "").strip()
        # Need a full YYYY-MM-DD: the On This Day browse and the year axis both
        # require it. The transcription is uniformly full-date, but guard anyway.
        if len(date) != 10 or date[4] != "-" or date[7] != "-":
            skipped += 1
            continue
        y, m, d = date[:4], date[5:7], date[8:10]
        if not (m.isdigit() and d.isdigit() and 1 <= int(m) <= 12 and 1 <= int(d) <= 31):
            skipped += 1
            continue

        title = _entry_text(entry)
        if not title:                       # contract requires a non-empty title
            skipped += 1
            continue

        events.append({
            "source": SOURCE_LABEL,
            "year": int(y),
            "month": m,                     # already zero-padded "01".."12"
            "day": d,                       # already zero-padded "01".."31"
            "title": title,
            "url": f"{ENTRY_URL_STEM}{m}{d}{y}",
        })
    return events, skipped


def _bucket_by_day(events: list[dict]) -> dict[str, list[dict]]:
    by_day: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        by_day[f"{ev['month']}-{ev['day']}"].append(ev)
    # The browser re-sorts each day by year; sort here too for a stable JSON.
    for key in by_day:
        by_day[key].sort(key=lambda e: e.get("year", 0))
    return dict(by_day)


def _build_compact(by_day: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """The diary needs only {y,t,u,s} — no score, doc-type, classification, or
    subjects. Keeping it minimal also keeps the embedded cache small."""
    out: dict[str, list[dict]] = {}
    for day, events in by_day.items():
        out[day] = [
            {"y": ev["year"], "t": ev["title"], "u": ev["url"], "s": ev["source"]}
            for ev in events
        ]
    return out


def _write_compact_js(js_out: Path, compact_by_day: dict) -> None:
    with open(js_out, "w", encoding="utf-8") as f:
        f.write("// Auto-generated by build_reagan_stage.py. Do not edit.\n")
        # The diary carries no subject taxonomy; an empty list keeps the shell's
        # topic filter inert (same as the Founders / Federal Register instances).
        f.write("const SUBJECT_TAXONOMY = [];\n")
        f.write("const EVENTS_CACHE = ")
        f.write(html_embed.js_safe_dumps(compact_by_day))
        f.write(";\n")


def build(json_out: Path, js_out: Path, html_out: Path | None) -> dict:
    if not XML_FILE.exists():
        raise SystemExit(
            f"{XML_FILE} not found. Place the Reagan diary XML there "
            "(see docs/reagan-diaries-build.md)."
        )
    if not SHELL_HTML.exists():
        raise SystemExit(f"{SHELL_HTML.name} (the Records Stage shell) not found.")

    events, skipped = parse_reagan(XML_FILE)

    # Validate against the shared event contract (same gate as every edition).
    summary = event_contract.validate_events(events)
    if not summary["ok"]:
        for p in summary["problems"]:
            print(f"  INVALID: {p['event']}: {p['problems']}")
        raise SystemExit(f"{summary['invalid']} invalid events — aborting.")

    by_day = _bucket_by_day(events)
    json_out.write_text(json.dumps(by_day, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = _build_compact(by_day)
    _write_compact_js(js_out, compact)

    years = sorted({ev["year"] for ev in events})

    html_synced = False
    if html_out:
        # Start every build from the cleared, vendored shell so the result is
        # always the canonical Records Stage UI plus fresh diary data.
        shell = SHELL_HTML.read_text(encoding="utf-8")
        # Customize the title to match the sibling instances' house style
        # (e.g. "Founders Online — Records Stage"). The shell ships the generic
        # "Records Stage"; we rebuild from it each run, so re-apply every time.
        shell = shell.replace("<title>Records Stage</title>",
                              f"<title>{STAGE_TITLE}</title>")
        shell = shell.replace("<h1>Records Stage</h1>", f"<h1>{STAGE_TITLE}</h1>")
        html_out.write_text(shell, encoding="utf-8")
        html_synced = html_embed.sync_html_embed(js_out, html_out)

    return {
        "events": len(events),
        "skipped_bad_or_empty": skipped,
        "days_with_events": len(by_day),
        "year_range": f"{years[0]}–{years[-1]}" if years else "—",
        "json_out": str(json_out),
        "js_out": str(js_out),
        "html": str(html_out) if html_out else None,
        "html_synced": html_synced,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build reagan-diaries-stage.html (Records Stage UI).")
    ap.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    ap.add_argument("--js-out", type=Path, default=DEFAULT_JS_OUT)
    ap.add_argument("--html", type=Path, default=DEFAULT_HTML)
    ap.add_argument("--no-html-sync", action="store_true")
    args = ap.parse_args()

    html = None if args.no_html_sync else args.html
    summary = build(args.json_out, args.js_out, html)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    if html and not summary["html_synced"]:
        print("  NOTE: HTML not spliced (shell missing or markers not found).")
    elif html:
        mb = args.html.stat().st_size / 1024 / 1024
        print(f"  ✓ {args.html.name} written ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
