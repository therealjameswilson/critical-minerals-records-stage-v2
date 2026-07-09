"""
State Magazine parser — joins per-issue article JSON with Internet Archive
URLs and emits toolkit events.

This is the kind of code that would live in a hypothetical
`historyatstate/state-magazine` adopter repo. For the POC it sits inside
the toolkit's gitignored `data/` directory; the toolkit's root parser.py
delegates to it via a one-line import.

Inputs:
  - Article JSON files at this directory: articles_<issue-identifier>.json
    (produced by extract_articles.py, or hand-crafted for POC purposes)

For each article it emits an event with:
  source        — 'State Magazine'
  date          — issue month/year (articles share the issue's date;
                  day defaults to '01' since articles aren't day-dated)
  title         — article headline
  url           — IA reader URL deep-linked to the article's start page
  subjects      — topical tags from the article JSON
  thumbnail_url — IA cover thumbnail for the issue (~13 KB)
  extra         — author, page_start, issue_id, issue_number

The URL scheme follows IA's standard: per-item pages live under
  https://archive.org/details/<identifier>/page/n<digital-page-number>
and the small cover thumb is at
  https://archive.org/download/<identifier>/__ia_thumb.jpg
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)


_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Default location of the State Magazine working files. parse_corpus()
# accepts any source_root — this is just the fallback when nothing is
# passed (matches the POC convention of running from the toolkit root).
_DEFAULT_DIR = Path(__file__).resolve().parent


def _parse_identifier(identifier: str) -> dict:
    """Extract month + year + issue number from an IA identifier like
    'sim_state-magazine_1991-05_344'. Tolerant of variant date forms
    like 'june-july-1991_345' that appear in some issues."""
    out = {"identifier": identifier, "year": None, "month": None,
           "issue_number": None, "date_display": None}

    # Try YYYY-MM_NNN form first (the common shape)
    m = re.search(r"_(\d{4})-(\d{1,2})_(\d+)$", identifier)
    if m:
        year, month, issue = int(m.group(1)), int(m.group(2)), m.group(3)
        out.update({
            "year": year, "month": month, "issue_number": issue,
            "date_display": f"{_MONTH_NAMES[month]} {year}",
        })
        return out

    # Fallback: month-month-YYYY_NNN (combined issues)
    m = re.search(r"_([a-z]+(?:-[a-z]+)?)-(\d{4})_(\d+)$", identifier, re.I)
    if m:
        months_str, year, issue = m.group(1), int(m.group(2)), m.group(3)
        # Use the first month of the range as the issue's nominal date
        first_month = months_str.split("-")[0].lower()
        month_num = next(
            (i for i, n in enumerate(_MONTH_NAMES) if n.lower() == first_month),
            None,
        )
        if month_num:
            out.update({
                "year": year, "month": month_num, "issue_number": issue,
                "date_display": f"{months_str.title()} {year}",
            })
    return out


def _article_url(identifier: str, page_start: int) -> str:
    """IA reader deep link for a specific page within an issue. IA uses
    n-prefixed 0-indexed digital page numbers in its reader URLs."""
    page_n = max(0, (page_start or 1) - 1)
    return f"https://archive.org/details/{identifier}/page/n{page_n}"


def _thumbnail_url(identifier: str) -> str:
    """Small (~13 KB) cover thumbnail from IA. Stable URL pattern; doesn't
    require any auth or special headers."""
    return f"https://archive.org/download/{identifier}/__ia_thumb.jpg"


def _parse_subjects(raw) -> tuple[list[str], dict[str, str]]:
    """Accept either the legacy bare-string subject list or the new
    [{name, category}] object form and return (names, name_to_category).
    Older articles_*.json files that predate the category-aware prompt
    yield an empty category map — build_cache.py falls back to "Other"
    for those, keeping them filterable but uncategorized."""
    names: list[str] = []
    cats: dict[str, str] = {}
    for s in raw or []:
        if isinstance(s, dict):
            n = (s.get("name") or "").strip()
            if not n:
                continue
            names.append(n)
            c = (s.get("category") or "").strip()
            if c:
                cats[n] = c
        elif isinstance(s, str):
            n = s.strip()
            if n:
                names.append(n)
    return names, cats


def parse_corpus(source_root: Path = None) -> Iterable[dict]:
    """
    Walk every articles_*.json under `source_root` (or this directory by
    default), join with the issue identifier embedded in the filename,
    and yield one event per article.
    """
    root = Path(source_root) if source_root else _DEFAULT_DIR
    if not root.exists():
        raise FileNotFoundError(f"State Magazine data directory not found: {root}")

    pattern = "articles_*.json"
    files = sorted(root.glob(pattern))
    if not files:
        # Heuristic: did the user point at a raw Internet Archive bundle by
        # mistake? IA bundles always ship *_djvu.txt and *_meta.xml.
        looks_like_ia_bundle = (
            any(root.glob("*_djvu.txt")) and any(root.glob("*_meta.xml"))
        )
        if looks_like_ia_bundle:
            identifier = root.name
            existing = _DEFAULT_DIR / f"articles_{identifier}.json"
            extractor = (_DEFAULT_DIR / "extract_articles.py").resolve()
            hint_lines = [
                f"That folder looks like a raw Internet Archive bundle ({identifier}),",
                "not the articles_*.json files the parser reads.",
                "",
                "State Magazine has a two-step workflow:",
                f"  1. Run extract_articles.py on the bundle (uses Claude; ~$0.20–0.30/issue):",
                f"       python {extractor} {root}",
                f"     → writes articles_{identifier}.json to {_DEFAULT_DIR}",
                f"  2. Point this app at that directory instead of the raw bundle.",
            ]
            if existing.exists():
                hint_lines += [
                    "",
                    f"Good news: articles_{identifier}.json already exists at",
                    f"  {existing}",
                    f"Set 'Where is your archive?' to {_DEFAULT_DIR} and click Read my archive again.",
                ]
            raise FileNotFoundError("\n".join(hint_lines))

        raise FileNotFoundError(
            f"No {pattern} files in {root}. Run extract_articles.py on at "
            "least one issue bundle first (or hand-craft a sample for POC)."
        )

    for json_path in files:
        # Filename: articles_sim_state-magazine_1991-05_344.json
        identifier = json_path.stem.removeprefix("articles_")
        issue_info = _parse_identifier(identifier)

        if not issue_info["year"]:
            log.warning("Couldn't parse date from identifier: %s", identifier)
            continue

        articles = json.loads(json_path.read_text(encoding="utf-8"))
        for article in articles:
            subject_names, subject_cats = _parse_subjects(article.get("subjects", []))
            yield {
                "source": "State Magazine",
                "date_display": issue_info["date_display"],
                "month": f"{issue_info['month']:02d}",
                "day": "01",   # articles share their issue's month; no day-level date
                "year": issue_info["year"],
                "title": article["title"],
                "url": _article_url(identifier, article.get("page_start", 1)),
                "subjects": subject_names,
                "subject_categories": subject_cats,
                "thumbnail_url": _thumbnail_url(identifier),
                "media_type": article.get("media_type", ""),
                # Images carried at top level so downstream tools can slice
                # the corpus by visual content without diving into `extra`.
                "images": article.get("images") or [],
                "extra": {
                    "author": article.get("author", ""),
                    "subheading": article.get("subheading", ""),
                    "page_start": article.get("page_start"),
                    "page_end": article.get("page_end"),
                    "summary": article.get("summary", ""),
                    "text_excerpt": article.get("text_excerpt", ""),
                    "issue_id": identifier,
                    "issue_number": issue_info["issue_number"],
                },
            }


if __name__ == "__main__":
    import sys

    src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    count = 0
    for event in parse_corpus(src):
        count += 1
        if count <= 3:
            print(json.dumps(event, indent=2, ensure_ascii=False))
    print(f"\nParsed {count} events.")
