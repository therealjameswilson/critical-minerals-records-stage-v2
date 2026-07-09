"""Parse critical-minerals JSON/CSV metadata into Records Toolkit events.

The parser intentionally emits metadata, summaries, source URLs, and citation
fields only. It does not fetch or cache document body text.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

import event_contract


LIST_FIELDS = {
    "minerals",
    "countries",
    "agencies",
    "supply_chain_stage",
    "fso_use_case",
    "hs_codes",
    "subjects",
}

EXTRA_FIELDS = [
    "minerals",
    "countries",
    "agencies",
    "source_type",
    "evidence_type",
    "supply_chain_stage",
    "fso_use_case",
    "hs_codes",
    "record_id",
    "retrieved_at",
    "citation_url",
    "caveat",
    "confidence",
]

SOURCE_TYPE_BY_SOURCE = {
    "FRUS / HistoryAtState": "FRUS",
    "NARA Catalog": "NARA",
    "U.S. Census Bureau": "Census",
    "USGS": "USGS",
    "DOE": "DOE",
    "DLA Strategic Materials": "DLA",
    "Federal Register": "Federal Register",
    "State Department": "State",
}


def parse_corpus(source_root: Path | str) -> Iterable[dict]:
    """Yield Records Toolkit event dictionaries from a JSON/CSV source root.

    ``source_root`` may be a directory containing ``*.json`` / ``*.csv`` files
    or a single JSON/CSV file. JSON may be either a list of records or an object
    with a top-level ``records`` list. CSV column names match the sample JSON
    keys; list fields may be JSON arrays or semicolon/comma-delimited strings.
    """

    root = Path(source_root)
    for item in _iter_raw_records(root):
        event = normalize_record(item)
        problems = event_contract.validate_event(event)
        if problems:
            label = item.get("record_id") or item.get("title") or "unnamed record"
            raise ValueError(f"Invalid critical-minerals record {label!r}: {problems}")
        yield event


def normalize_record(item: dict) -> dict:
    """Normalize one raw critical-minerals metadata record into event shape."""

    year, month, day = _normalize_date(item)
    extra_in = item.get("extra") if isinstance(item.get("extra"), dict) else {}

    def pick(key: str, default=None):
        if key in item and item[key] not in (None, ""):
            return item[key]
        return extra_in.get(key, default)

    source = str(pick("source", "")).strip()
    record_id = str(pick("record_id", "")).strip() or _fallback_record_id(item)
    retrieved_at = str(pick("retrieved_at", "")).strip() or _today_utc()
    citation_url = str(pick("citation_url", "")).strip() or str(pick("url", "")).strip()
    source_type = str(pick("source_type", "")).strip() or SOURCE_TYPE_BY_SOURCE.get(source, "Other USG")

    extra: dict = {}
    for key in EXTRA_FIELDS:
        if key in LIST_FIELDS:
            extra[key] = _as_list(pick(key, []))
        elif key == "record_id":
            extra[key] = record_id
        elif key == "retrieved_at":
            extra[key] = retrieved_at
        elif key == "citation_url":
            extra[key] = citation_url
        elif key == "source_type":
            extra[key] = source_type
        elif key == "confidence":
            extra[key] = _normalize_confidence(str(pick(key, "medium")))
        else:
            value = pick(key, "")
            extra[key] = "" if value is None else str(value).strip()

    subjects = _as_list(pick("subjects", []))
    event = {
        "source": source,
        "year": int(year),
        "month": month,
        "day": day,
        "date_display": str(pick("date_display", item.get("date", ""))).strip(),
        "title": str(pick("title", "")).strip(),
        "url": str(pick("url", "")).strip(),
        "description": str(pick("description", item.get("summary", ""))).strip(),
        "subjects": subjects,
        "extra": extra,
    }

    return event


def _iter_raw_records(root: Path) -> Iterator[dict]:
    paths: list[Path]
    if root.is_file():
        paths = [root]
    else:
        preferred = root / "critical_minerals_sample.json"
        if preferred.exists():
            paths = [preferred]
        else:
            paths = sorted(
                p for p in root.iterdir()
                if p.suffix.lower() in {".json", ".csv"} and not p.name.startswith("events_cache")
            )

    if not paths:
        raise FileNotFoundError(f"No JSON or CSV records found under {root}")

    for path in paths:
        if path.suffix.lower() == ".json":
            yield from _read_json_records(path)
        elif path.suffix.lower() == ".csv":
            yield from _read_csv_records(path)


def _read_json_records(path: Path) -> Iterator[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("records", [])
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a list or an object with records: []")
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f"{path} contains a non-object record: {item!r}")
        yield item


def _read_csv_records(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            yield {k: _coerce_csv_value(v) for k, v in row.items() if k}


def _coerce_csv_value(value: str | None):
    if value is None:
        return ""
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _normalize_date(item: dict) -> tuple[int, str, str]:
    if all(k in item and item[k] not in (None, "") for k in ("year", "month", "day")):
        return int(item["year"]), str(int(item["month"])).zfill(2), str(int(item["day"])).zfill(2)

    raw = str(item.get("date") or item.get("date_display") or "").strip()
    match = re.search(r"\b(1[5-9]\d{2}|20\d{2})(?:-(\d{1,2})(?:-(\d{1,2}))?)?", raw)
    if not match:
        raise ValueError(f"Could not normalize date for {item.get('record_id') or item.get('title')!r}")

    year = int(match.group(1))
    month = int(match.group(2) or 1)
    day = int(match.group(3) or 1)
    return year, str(month).zfill(2), str(day).zfill(2)


def _as_list(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_as_list(item))
        return _dedupe(out)
    if isinstance(value, tuple) or isinstance(value, set):
        return _dedupe(str(v).strip() for v in value if str(v).strip())
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            return _as_list(parsed)
        except json.JSONDecodeError:
            pass
    parts = re.split(r"\s*[;,|]\s*", text)
    return _dedupe(p for p in parts if p)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        clean = str(value).strip()
        if not clean:
            continue
        key = clean.casefold()
        if key not in seen:
            seen.add(key)
            out.append(clean)
    return out


def _normalize_confidence(value: str) -> str:
    clean = value.strip().lower()
    return clean if clean in {"high", "medium", "low"} else "medium"


def _fallback_record_id(item: dict) -> str:
    base = str(item.get("url") or item.get("title") or "critical-minerals-record").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return slug[:80] or "critical-minerals-record"


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


if __name__ == "__main__":
    for event in parse_corpus(Path("examples/critical_minerals_sample")):
        print(json.dumps(event, indent=2))
