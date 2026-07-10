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
    "minerals": 10,
    "countries": 9,
    "episodes": 8,
    "agreements": 15,
    "frus-documents": 32,
    "administrations": 5,
    "laws": 3,
    "stockpile-cases": 2,
    "country-briefs": 4,
    "trade": 1400,
    "trade-details": 14,
    "trade-research": 1,
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
            if key in {"year", "start", "end", "default_year", "volume_year_start", "volume_year_end"} and isinstance(value, int):
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
    atlas = json.loads((ROOT / "data" / "atlas" / "atlas.json").read_text(encoding="utf-8"))

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
    def check_references(node: object, owner: str, path: str = "") -> None:
        if isinstance(node, dict):
            for field, value in node.items():
                child_path = f"{path}.{field}" if path else field
                if field in reference_targets and isinstance(value, list):
                    target = reference_targets[field]
                    for reference in value:
                        if reference not in ids[target]:
                            errors.append(f"{owner}: {child_path} references missing {target} id {reference}")
                else:
                    check_references(value, owner, child_path)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                check_references(value, owner, f"{path}[{index}]")

    for dataset_name, rows in datasets.items():
        for row in rows:
            check_references(row, f"{dataset_name}/{row.get('id')}")

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

    required_trade_fields = {
        "year_start", "year_end", "year_label", "temporal_precision", "direction",
        "metric", "material_scope", "value", "unit", "trade_basis", "calendar_basis",
        "agency", "publication_title", "publication_year", "table_or_page", "source_id",
        "source_url", "access_date", "transcription_status", "original_unit",
        "displayed_unit", "conversion_methodology", "notes", "confidence"
    }
    for row in datasets["trade"]:
        owner = f"trade/{row.get('id')}"
        missing = sorted(required_trade_fields - set(row))
        if missing:
            errors.append(f"{owner}: missing {', '.join(missing)}")
        if row.get("direction") not in {"imports", "exports"}:
            errors.append(f"{owner}: invalid direction {row.get('direction')}")
        if row.get("source_id") not in ids["sources"]:
            errors.append(f"{owner}: unknown source_id {row.get('source_id')}")
        start, end = row.get("year_start"), row.get("year_end")
        if not isinstance(start, int) or not isinstance(end, int) or not HISTORICAL_START <= start <= end <= HISTORICAL_END:
            errors.append(f"{owner}: invalid historical range {start}-{end}")
        if row.get("mineral_id") is not None and row.get("mineral_id") not in ids["minerals"]:
            errors.append(f"{owner}: unknown mineral_id {row.get('mineral_id')}")
        if row.get("temporal_precision") == "annual" and row.get("year_start") != row.get("year_end"):
            errors.append(f"{owner}: annual row must have matching start and end years")
        if row.get("material_scope") == "broad-economic-class" and row.get("mineral_id") is not None:
            errors.append(f"{owner}: broad economic-class row must not claim a mineral_id")

    uncovered_trade_years = [
        year for year in range(HISTORICAL_START, HISTORICAL_END + 1)
        if not any(row.get("year_start", 9999) <= year <= row.get("year_end", 0) for row in datasets["trade"])
    ]
    if uncovered_trade_years:
        errors.append(f"trade: no verified record covers years {uncovered_trade_years}")

    required_trade_detail_fields = {
        "year", "mineral_id", "direction", "category", "quantity", "trade_value",
        "is_total", "source_id", "source_origin_agency", "publication_title",
        "table_or_page", "source_url", "access_date", "transcription_status",
        "classification_note", "confidence"
    }
    for row in datasets["trade-details"]:
        owner = f"trade-details/{row.get('id')}"
        missing = sorted(required_trade_detail_fields - set(row))
        if missing:
            errors.append(f"{owner}: missing {', '.join(missing)}")
        if row.get("mineral_id") not in ids["minerals"]:
            errors.append(f"{owner}: unknown mineral_id {row.get('mineral_id')}")
        if row.get("source_id") not in ids["sources"]:
            errors.append(f"{owner}: unknown source_id {row.get('source_id')}")
        if row.get("direction") not in {"imports", "exports"}:
            errors.append(f"{owner}: invalid direction {row.get('direction')}")
        for measure_name in ("quantity", "trade_value"):
            measure = row.get(measure_name, {})
            if not {"value", "display", "unit", "status"} <= set(measure):
                errors.append(f"{owner}: malformed {measure_name}")
            if measure.get("value") is None and measure.get("status") != "not-available":
                errors.append(f"{owner}: null {measure_name} must be not-available")

    detail_ids = ids["trade-details"]
    for row in datasets["trade-research"]:
        owner = f"trade-research/{row.get('id')}"
        if row.get("mineral_id") not in ids["minerals"]:
            errors.append(f"{owner}: unknown mineral_id {row.get('mineral_id')}")
        if row.get("status") != "source-acquisition":
            errors.append(f"{owner}: invalid status {row.get('status')}")
        if len(row.get("reports", [])) < 2:
            errors.append(f"{owner}: expected import and export report plans")
        for reference in row.get("control_total_ids", []):
            if reference not in detail_ids:
                errors.append(f"{owner}: missing control total {reference}")

    fact_statuses = {"verified", "estimated", "unknown"}
    for brief in datasets["country-briefs"]:
        owner = f"country-briefs/{brief.get('id')}"
        if brief.get("country_id") not in ids["countries"]:
            errors.append(f"{owner}: unknown country_id {brief.get('country_id')}")
        fact_groups = [brief.get("baseline_facts", {})]
        fact_groups.extend(row.get("facts", {}) for row in brief.get("profile_periods", []))
        for facts in fact_groups:
            for label, fact in facts.items():
                status = fact.get("status")
                if status not in fact_statuses:
                    errors.append(f"{owner}: {label} has invalid status {status}")
                if status == "unknown" and fact.get("value") is not None:
                    errors.append(f"{owner}: unknown fact {label} must have a null value")
                if status == "verified" and not (fact.get("source_id") or fact.get("frus_document_id")):
                    errors.append(f"{owner}: verified fact {label} needs source_id or frus_document_id")
                if fact.get("source_id") and fact["source_id"] not in ids["sources"]:
                    errors.append(f"{owner}: fact {label} references missing source {fact['source_id']}")
                if fact.get("frus_document_id") and fact["frus_document_id"] not in ids["frus-documents"]:
                    errors.append(f"{owner}: fact {label} references missing FRUS record {fact['frus_document_id']}")

    if atlas.get("meta", {}).get("historical_start") != HISTORICAL_START or atlas.get("meta", {}).get("historical_end") != HISTORICAL_END:
        errors.append("atlas: historical bounds must be 1861-1992")
    atlas_layers = atlas.get("layers", [])
    layer_ids = [row.get("id") for row in atlas_layers]
    if len(layer_ids) != len(set(layer_ids)):
        errors.append("atlas: duplicate layer ids detected")
    for row in atlas_layers:
        if row.get("availability") not in {"supported", "locked"}:
            errors.append(f"atlas/{row.get('id')}: invalid availability")
        if not row.get("source_ids") or not row.get("caveat"):
            errors.append(f"atlas/{row.get('id')}: source_ids and caveat are required")
        if row.get("availability") == "supported" and not row.get("value_semantics"):
            errors.append(f"atlas/{row.get('id')}: supported layer needs value_semantics")
        if row.get("availability") == "locked" and not row.get("required_data"):
            errors.append(f"atlas/{row.get('id')}: locked layer needs required_data")
        for source_id in row.get("source_ids", []):
            if source_id not in ids["sources"]:
                errors.append(f"atlas/{row.get('id')}: missing source id {source_id}")
    for row in atlas.get("countries", []):
        if row.get("id") not in ids["countries"]:
            errors.append(f"atlas: missing country reference {row.get('id')}")
        if not row.get("a3") or len(row.get("coordinates", [])) != 2:
            errors.append(f"atlas/{row.get('id')}: A3 code and country coordinates are required")
    for row in atlas.get("relationships", []):
        if row.get("line_value_semantics") != "linked pilot FRUS records":
            errors.append(f"atlas/{row.get('id')}: access line width must retain documentary semantics")
        if row.get("from_country_id") not in ids["countries"] or row.get("to_country_id") not in ids["countries"]:
            errors.append(f"atlas/{row.get('id')}: relationship country reference is missing")
        for record_id in row.get("frus_document_ids", []):
            if record_id not in ids["frus-documents"]:
                errors.append(f"atlas/{row.get('id')}: missing FRUS reference {record_id}")

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
