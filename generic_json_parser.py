"""
Generic JSON adapter — the no-code path for adopters whose archive is
already a clean JSON file (or directory of JSON files).

Carol at Treasury, for example, can export press releases as JSON, point
the toolkit at the file, map her fields to the toolkit's fields via
dropdowns in the Streamlit app, and never write a line of Python.

`parse_corpus_with_config(source_root, config)` reads:
  - a single .json file containing a JSON array of records, OR
  - a directory containing one or more such files

and yields one toolkit event per record, transformed per `config`.

Config schema (see parser_config.json — written by the Streamlit UI):

    {
      "source_label": "Treasury Press Releases",
      "array_key": null,           # If JSON is {"records": [...]}, set "records"
      "field_map": {
        "title":       "headline",          # required
        "url":         "link",              # required (warns if absent)
        "date":        "publication_date",  # one parseable date string
        # ── OR three separate fields ──
        "year":        null,
        "month":       null,
        "day":         null,
        # ── optional ──
        "subjects":    "tags",              # list, or comma-separated string
        "description": "summary"
      }
    }

If your data outgrows this adapter (you need URL construction, date
inference from filenames, multi-source merging, etc.), replace
`parser.py` with a hand-written `parse_corpus()` implementation.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

# --- Date parsing ---------------------------------------------------------

# Formats whose month/day order is unambiguous from the separators or month
# names. These are tried first regardless of locale.
_DATE_FORMATS_UNAMBIGUOUS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%b %d %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%B %Y",
    "%b %Y",
    "%Y",
]

# The numeric slash forms are genuinely ambiguous (03/04/2020 is March 4 in the
# US, 3 April elsewhere). Order them per the adopter's `date_day_first` flag
# instead of silently guessing US-first.
_DATE_FORMATS_MONTH_FIRST = ["%m/%d/%Y"]
_DATE_FORMATS_DAY_FIRST = ["%d/%m/%Y"]


def _parse_date_string(raw, day_first: bool = False) -> tuple[int, int, int, str] | None:
    """Return (year, month, day, display) or None if unparseable. When the
    format doesn't include a day (e.g. "March 2010"), day defaults to 1.

    ``day_first`` controls how ambiguous numeric dates like ``03/04/2020`` are
    read: False → month-first (US, the default), True → day-first.
    """
    if raw is None or raw == "":
        return None
    s = str(raw).strip()
    ambiguous = _DATE_FORMATS_DAY_FIRST + _DATE_FORMATS_MONTH_FIRST if day_first \
        else _DATE_FORMATS_MONTH_FIRST + _DATE_FORMATS_DAY_FIRST
    for fmt in _DATE_FORMATS_UNAMBIGUOUS + ambiguous:
        try:
            dt = datetime.strptime(s, fmt)
            return (dt.year, dt.month, dt.day, s)
        except ValueError:
            continue
    # Last resort: find a four-digit year anywhere in the string.
    m = re.search(r"\b(\d{4})\b", s)
    if m:
        y = int(m.group(1))
        if 1700 <= y <= 2100:
            return (y, 1, 1, s)
    return None


# --- Record discovery -----------------------------------------------------

def _load_records(source_root: Path, array_key: str | None) -> list[dict]:
    """Read records from a JSON file or directory of JSON files."""
    root = Path(source_root)
    if root.is_file():
        files = [root]
    elif root.is_dir():
        files = sorted(root.glob("*.json"))
        if not files:
            raise FileNotFoundError(
                f"No .json files in {root}. Point at a single .json file or "
                f"a directory containing one."
            )
    else:
        raise FileNotFoundError(f"Not a file or directory: {root}")

    records: list[dict] = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Couldn't parse {path}: {e}") from e
        if array_key:
            if not isinstance(data, dict) or array_key not in data:
                raise ValueError(
                    f"{path}: expected a top-level object with key "
                    f"{array_key!r}, but didn't find it."
                )
            data = data[array_key]
        if not isinstance(data, list):
            raise ValueError(
                f"{path}: expected a JSON array of records, got "
                f"{type(data).__name__}. If your records are nested under a "
                f"key, set `array_key` in parser_config.json."
            )
        records.extend(r for r in data if isinstance(r, dict))
    return records


# --- Field auto-detection -------------------------------------------------

# Common candidate names for each target field, in order of preference.
_AUTODETECT = {
    "title":       ["title", "headline", "name", "subject"],
    "url":         ["url", "link", "href", "permalink", "uri"],
    "date":        ["date", "publication_date", "published", "published_at",
                    "release_date", "issue_date", "created", "created_at"],
    "year":        ["year", "yr"],
    "month":       ["month", "mo"],
    "day":         ["day"],
    "subjects":    ["subjects", "tags", "topics", "categories", "keywords"],
    "description": ["description", "summary", "abstract", "excerpt", "body"],
}


def autodetect_field_map(sample_record: dict) -> dict[str, str | None]:
    """Best-guess field mapping from a single sample record. Returns a dict
    keyed by toolkit field name; values are field names in the sample (or
    None if no candidate matched). The Streamlit UI uses this to pre-fill
    the dropdowns so Carol just confirms rather than starting from scratch."""
    keys_lc = {k.lower(): k for k in sample_record}
    out: dict[str, str | None] = {}
    for target, candidates in _AUTODETECT.items():
        out[target] = next(
            (keys_lc[c] for c in candidates if c in keys_lc), None,
        )
    return out


# --- Subjects coercion ----------------------------------------------------

def _coerce_subjects(raw) -> list[str]:
    """Accept either a list of strings or a comma/semicolon-separated
    string. Treasury exports vary; this swallows the common shapes."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if str(s).strip()]
    if isinstance(raw, str):
        parts = re.split(r"[,;|]", raw)
        return [p.strip() for p in parts if p.strip()]
    return [str(raw)]


# --- Main entry point -----------------------------------------------------

def parse_corpus_with_config(source_root, config: dict) -> Iterable[dict]:
    """Read `source_root` per `config` and yield toolkit events.

    Raises a clear error early on if required mappings are missing or the
    sample's date field can't be parsed — better to fail loudly than to
    emit hundreds of malformed events.
    """
    fmap = config.get("field_map", {})
    source_label = config.get("source_label", "Untitled Archive")
    array_key = config.get("array_key")
    day_first = bool(config.get("date_day_first", False))

    title_field = fmap.get("title")
    url_field = fmap.get("url")
    if not title_field:
        raise ValueError(
            "Field mapping is incomplete: pick which field holds the document "
            "title (in the Connect Corpus tab)."
        )

    use_split_date = bool(fmap.get("year"))
    date_field = fmap.get("date")
    if not use_split_date and not date_field:
        raise ValueError(
            "Field mapping is incomplete: pick which field holds the "
            "publication date (or pick separate year/month/day fields)."
        )

    records = _load_records(Path(source_root), array_key)
    if not records:
        return

    skipped_no_date = 0
    skipped_bad_range = 0
    for rec in records:
        title = (rec.get(title_field) or "").strip() if title_field else ""
        if not title:
            continue  # records without a title aren't tweetable

        if use_split_date:
            try:
                year = int(rec.get(fmap["year"]))
                month = int(rec.get(fmap.get("month") or "") or 1)
                day = int(rec.get(fmap.get("day") or "") or 1)
                date_display = f"{year}-{month:02d}-{day:02d}"
            except (TypeError, ValueError):
                skipped_no_date += 1
                continue
        else:
            parsed = _parse_date_string(rec.get(date_field), day_first=day_first)
            if not parsed:
                skipped_no_date += 1
                continue
            year, month, day, date_display = parsed

        # Reject out-of-range month/day rather than emitting an unreachable
        # MM-DD bucket like "13-45" that the HTML calendar can never surface.
        if not (1 <= month <= 12 and 1 <= day <= 31):
            skipped_bad_range += 1
            continue

        url = (rec.get(url_field) or "").strip() if url_field else ""
        subjects = _coerce_subjects(rec.get(fmap.get("subjects") or ""))
        description = ""
        if fmap.get("description"):
            description = str(rec.get(fmap["description"]) or "").strip()

        yield {
            "source": source_label,
            "date_display": date_display,
            "month": f"{month:02d}",
            "day": f"{day:02d}",
            "year": year,
            "title": title,
            "url": url,
            "subjects": subjects,
            "description": description,
        }

    # Logged (not printed) so the Streamlit wrapper can capture and surface
    # these in the browser; a partial run is still useful, so this isn't fatal.
    if skipped_no_date:
        log.warning("Skipped %d record(s) with unparseable dates.", skipped_no_date)
    if skipped_bad_range:
        log.warning(
            "Skipped %d record(s) whose month/day were out of range.",
            skipped_bad_range,
        )


# --- CLI for quick smoke-testing -----------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python generic_json_parser.py <source_root> <parser_config.json>")
        sys.exit(2)

    src = Path(sys.argv[1])
    cfg = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    count = 0
    for event in parse_corpus_with_config(src, cfg):
        count += 1
        if count <= 3:
            print(json.dumps(event, indent=2, ensure_ascii=False))
    print(f"\nParsed {count} events.")
