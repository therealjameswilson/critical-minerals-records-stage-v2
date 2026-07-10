#!/usr/bin/env python3
"""Validate the normalized History Stack pilot and its cross-file references."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "history-stack"
HISTORICAL_START = 1861
HISTORICAL_END = 1992

EXPECTED_MINIMUMS = {
    "minerals": 8,
    "countries": 6,
    "episodes": 4,
    "agreements": 12,
    "frus-documents": 20,
    "administrations": 4,
    "laws": 3,
    "stockpile-cases": 2,
}


def load(name: str) -> list[dict]:
    path = DATA / f"{name}.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a JSON array")
    return value


def year_values(node: object, path: str = "") -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else key
            if key in {"year", "start", "end", "volume_year_start", "volume_year_end"} and isinstance(value, int):
                found.append((child_path, value))
            else:
                found.extend(year_values(value, child_path))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(year_values(value, f"{path}[{index}]"))
    return found


def main() -> None:
    errors: list[str] = []
    datasets = {name: load(name) for name in EXPECTED_MINIMUMS}
    datasets["statistics"] = load("statistics")
    datasets["sources"] = load("sources")
    datasets["nara-queries"] = load("nara-queries")

    for name, minimum in EXPECTED_MINIMUMS.items():
        if len(datasets[name]) < minimum:
            errors.append(f"{name}: expected at least {minimum}, found {len(datasets[name])}")

    ids: dict[str, set[str]] = {}
    for name, rows in datasets.items():
        row_ids = [row.get("id") for row in rows]
        if any(not isinstance(row_id, str) or not row_id for row_id in row_ids):
            errors.append(f"{name}: every row must have a nonempty string id")
        if len(row_ids) != len(set(row_ids)):
            errors.append(f"{name}: duplicate ids detected")
        ids[name] = set(row_ids)

    reference_targets = {
        "mineral_ids": "minerals", "country_ids": "countries", "episode_ids": "episodes",
        "agreement_ids": "agreements", "law_ids": "laws", "frus_document_ids": "frus-documents",
        "source_ids": "sources", "nara_query_ids": "nara-queries"
    }
    for dataset_name, rows in datasets.items():
        for row in rows:
            for field, target in reference_targets.items():
                for value in row.get(field, []):
                    if value not in ids[target]:
                        errors.append(f"{dataset_name}/{row.get('id')}: {field} references missing {target} id {value}")

    for name, rows in datasets.items():
        if name == "sources":
            continue
        for row in rows:
            for path, year in year_values(row):
                if not HISTORICAL_START <= year <= HISTORICAL_END:
                    errors.append(f"{name}/{row.get('id')}: {path}={year} outside 1861-1992")

    required_stat_fields = {"metric", "mineral_id", "year", "unit", "value", "publication_title", "table_or_page", "agency", "source_url", "access_date", "original_unit", "displayed_unit", "conversion_methodology", "confidence"}
    for row in datasets["statistics"]:
        missing = sorted(required_stat_fields - set(row))
        if missing:
            errors.append(f"statistics/{row.get('id')}: missing {', '.join(missing)}")
        if row.get("mineral_id") not in ids["minerals"]:
            errors.append(f"statistics/{row.get('id')}: unknown mineral {row.get('mineral_id')}")

    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    if env_example != "NARA_API_KEY=\n":
        errors.append(".env.example must contain only NARA_API_KEY= followed by a newline")

    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, check=True, text=True, capture_output=True).stdout.splitlines()
    quoted_secret = re.compile(r"NARA_API_KEY\s*[:=]\s*['\"]([^'\"]{8,})['\"]")
    env_secret = re.compile(r"(?m)^\s*NARA_API_KEY=([^\s#]+)\s*$")
    for relative in tracked:
        path = ROOT / relative
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".xlsx", ".pdf"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if quoted_secret.search(text) or env_secret.search(text):
            errors.append(f"Potential NARA secret in tracked file {relative}")

    if errors:
        raise SystemExit("History Stack validation failed:\n- " + "\n- ".join(errors))
    print("History Stack validation passed")
    print(", ".join(f"{name}={len(rows)}" for name, rows in datasets.items()))


if __name__ == "__main__":
    main()
