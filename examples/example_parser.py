"""
Worked example: a parser over a tiny stub corpus.

This shows the parse_corpus() contract end-to-end on a five-event toy archive
(see sample_data.json in this directory). Copy this file to parser.py at the
template root as a starting point for your own corpus.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

THIS_DIR = Path(__file__).parent


def parse_corpus(source_root: Path) -> Iterable[dict]:
    """
    Read the toy archive from sample_data.json and yield normalized events.

    Real adopters will replace this body with corpus-specific parsing
    (XML walks, PDF text extraction, CSV reads, database queries, etc.).
    """
    data_path = source_root / "sample_data.json"
    raw = json.loads(data_path.read_text(encoding="utf-8"))

    for item in raw:
        # Date split: input "1995-03-15" → year/month/day fields.
        year_s, month_s, day_s = item["date"].split("-")
        yield {
            "source": "Stub Magazine",
            "date_display": item.get("date_display", item["date"]),
            "month": month_s,
            "day": day_s,
            "year": int(year_s),
            "title": item["title"],
            "description": item.get("summary", ""),
            "url": item["url"],
            "subjects": item.get("subjects", []),
            "extra": {
                "author": item.get("author"),
                "department": item.get("department"),
            },
        }


if __name__ == "__main__":
    for event in parse_corpus(THIS_DIR):
        print(event)
