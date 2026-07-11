#!/usr/bin/env python3
"""Validate the normalized History Stack pilot and its cross-file references."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "history-stack"
DS140_DATA = ROOT / "data" / "usgs-ds140"
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
    "trade-details": 294,
    "trade-research": 21,
    "dataweb-trade": 3600,
    "dataweb-query-manifest": 2,
    "comtrade-rare-earth": 170,
    "comtrade-query-manifest": 40,
    "comtrade-strategic-materials": 2000,
    "comtrade-strategic-query-manifest": 31,
    "annual-snapshots": 132,
    "supply-chain": 1700,
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
    ds140_catalog = json.loads((DS140_DATA / "catalog.json").read_text(encoding="utf-8"))

    if ds140_catalog.get("commodity_count") != 92 or ds140_catalog.get("review_queue_count") != 0:
        errors.append("usgs-ds140: expected 92 extracted commodities and an empty review queue")
    observed_ds140 = 0
    observed_series = 0
    observed_measures = 0
    commodity_ids: set[str] = set()
    for entry in ds140_catalog.get("commodities", []):
        commodity_id = entry.get("id")
        if not commodity_id or commodity_id in commodity_ids:
            errors.append(f"usgs-ds140: invalid or duplicate commodity id {commodity_id}")
            continue
        commodity_ids.add(commodity_id)
        path = DS140_DATA / "commodities" / f"{commodity_id}.json"
        if not path.exists():
            errors.append(f"usgs-ds140/{commodity_id}: missing commodity payload")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("commodity", {}).get("id") != commodity_id:
            errors.append(f"usgs-ds140/{commodity_id}: payload id mismatch")
        observed_series += len(payload.get("series", []))
        for series in payload.get("series", []):
            observed_measures += len(series.get("measures", []))
            for measure in series.get("measures", []):
                observations = measure.get("observations", [])
                observed_ds140 += len(observations)
                for observation in observations:
                    if len(observation) != 3 or not HISTORICAL_START <= observation[0] <= HISTORICAL_END:
                        errors.append(f"usgs-ds140/{commodity_id}/{series.get('id')}/{measure.get('id')}: invalid observation")
                        break
                    if not isinstance(observation[1], (int, float)) or not isinstance(observation[2], int):
                        errors.append(f"usgs-ds140/{commodity_id}/{series.get('id')}/{measure.get('id')}: value and row must be numeric")
                        break
    if observed_ds140 != ds140_catalog.get("observation_count"):
        errors.append("usgs-ds140: observation count does not match catalog")
    if observed_series != ds140_catalog.get("series_count") or observed_measures != ds140_catalog.get("measure_count"):
        errors.append("usgs-ds140: series or measure count does not match catalog")

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

    required_supply_fields = {
        "record_type", "year", "mineral_id", "stage", "source_country_name",
        "country_iso3", "mapping_basis", "component", "metric", "value", "unit",
        "status", "estimated", "agency", "publication_title", "table_or_page",
        "source_id", "source_url", "catalog_url", "access_date",
        "geographic_precision", "caveat"
    }
    for row in datasets["supply-chain"]:
        owner = f"supply-chain/{row.get('id')}"
        missing = sorted(required_supply_fields - set(row))
        if missing:
            errors.append(f"{owner}: missing {', '.join(missing)}")
        if row.get("record_type") not in {"production", "us-import"}:
            errors.append(f"{owner}: invalid record type {row.get('record_type')}")
        if row.get("mineral_id") not in ids["minerals"]:
            errors.append(f"{owner}: unknown mineral {row.get('mineral_id')}")
        if not isinstance(row.get("year"), int) or not HISTORICAL_START <= row.get("year", 0) <= HISTORICAL_END:
            errors.append(f"{owner}: year outside 1861-1992")
        if not isinstance(row.get("value"), (int, float)) or row.get("value", 0) < 0 or not row.get("unit"):
            errors.append(f"{owner}: invalid value or unit")
        if not re.fullmatch(r"[A-Z]{3}", str(row.get("country_iso3", ""))):
            errors.append(f"{owner}: expected orientation ISO3 code")
        if row.get("source_id") != "usgs-statistical-compendium":
            errors.append(f"{owner}: unexpected source id {row.get('source_id')}")
        if not str(row.get("source_url", "")).startswith("https://d9-wret.s3.us-west-2.amazonaws.com/"):
            errors.append(f"{owner}: unexpected official table URL")

    production_stages = {row.get("stage") for row in datasets["supply-chain"] if row.get("record_type") == "production"}
    if production_stages != {"mining", "smelting", "refining"}:
        errors.append(f"supply-chain: expected mining, smelting, and refining stages, found {sorted(production_stages)}")
    if not any(row.get("record_type") == "us-import" and row.get("mineral_id") == "cobalt" for row in datasets["supply-chain"]):
        errors.append("supply-chain: expected Census-derived cobalt import rows")

    annual = datasets["annual-snapshots"]
    if {row.get("year") for row in annual} != set(range(HISTORICAL_START, HISTORICAL_END + 1)):
        errors.append("annual-snapshots: expected exactly one record for every year 1861-1992")
    annual_count_fields = {
        "frus_documents", "reviewed_frus_documents", "frus_discovery_leads",
        "year_linked_geographies", "active_episodes", "documented_access_links",
        "dated_instruments", "laws_enacted", "stockpile_pathways", "nara_query_plans",
        "official_statistics", "broad_trade_context_rows", "commodity_trade_rows",
        "dataweb_partner_rows", "comtrade_context_rows"
    }
    valid_coverage = {"document-plus-context", "documentary-only", "context-only", "sparse"}
    valid_gaps = {"frus", "geography", "statistics", "policy", "archives"}
    for row in annual:
        owner = f"annual-snapshots/{row.get('id')}"
        if set(row.get("materials", {})) != ids["minerals"]:
            errors.append(f"{owner}: material slices do not match the mineral registry")
        for label, snapshot in [("overall", row.get("overall", {})), *row.get("materials", {}).items()]:
            counts = snapshot.get("counts", {})
            if set(counts) != annual_count_fields or any(not isinstance(value, int) or value < 0 for value in counts.values()):
                errors.append(f"{owner}/{label}: invalid annual count contract")
            if snapshot.get("coverage_status") not in valid_coverage:
                errors.append(f"{owner}/{label}: invalid coverage status")
            if not set(snapshot.get("missing_lanes", [])).issubset(valid_gaps):
                errors.append(f"{owner}/{label}: invalid missing lane")
            if not set(snapshot.get("country_evidence_counts", {})).issubset(ids["countries"]):
                errors.append(f"{owner}/{label}: unknown year-linked country")
            if not set(snapshot.get("profile_context_country_ids", [])).issubset(ids["countries"]):
                errors.append(f"{owner}/{label}: unknown profile-context country")

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
        "year", "mineral_id", "direction", "category", "source_category_label", "quantity", "trade_value",
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
            if not {"value", "display", "unit", "status", "source_symbol"} <= set(measure):
                errors.append(f"{owner}: malformed {measure_name}")
            if measure.get("status") not in {"reported", "not-available", "published-dash", "less-than", "not-published"}:
                errors.append(f"{owner}: invalid {measure_name} status {measure.get('status')}")
            if measure.get("value") is None and measure.get("status") == "reported":
                errors.append(f"{owner}: reported {measure_name} must have a value")
            if measure.get("value") is not None and measure.get("status") != "reported":
                errors.append(f"{owner}: numeric {measure_name} must be reported")

    detail_ids = ids["trade-details"]
    detail_years = {row.get("year") for row in datasets["trade-details"]}
    if detail_years != set(range(1970, 1991)):
        errors.append(f"trade-details: expected annual coverage 1970-1990, found {sorted(detail_years)}")
    for year in range(1970, 1991):
        year_rows = [row for row in datasets["trade-details"] if row.get("year") == year]
        if len(year_rows) != 14:
            errors.append(f"trade-details: {year} expected 14 category rows, found {len(year_rows)}")

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
    research_years = {row.get("year") for row in datasets["trade-research"]}
    if research_years != set(range(1970, 1991)):
        errors.append(f"trade-research: expected annual queues 1970-1990, found {sorted(research_years)}")

    required_dataweb_fields = {
        "year", "mineral_id", "direction", "trade_flow", "classification_system",
        "classification_level", "commodity_code", "commodity_description", "commodity_scope_note",
        "supply_chain_stage", "source_partner_name", "partner_code", "partner_iso2", "partner_iso3",
        "trade_value", "quantity", "source_id", "source_origin_agency", "publication_title",
        "table_or_page", "source_url", "access_date", "transcription_status", "confidence", "caveat"
    }
    for row in datasets["dataweb-trade"]:
        owner = f"dataweb-trade/{row.get('id')}"
        missing = sorted(required_dataweb_fields - set(row))
        if missing:
            errors.append(f"{owner}: missing {', '.join(missing)}")
        if row.get("year") not in {1989, 1990, 1991, 1992}:
            errors.append(f"{owner}: DataWeb year must be 1989-1992")
        if row.get("mineral_id") not in ids["minerals"]:
            errors.append(f"{owner}: unknown mineral_id {row.get('mineral_id')}")
        if row.get("source_id") != "usitc-dataweb":
            errors.append(f"{owner}: source_id must be usitc-dataweb")
        if row.get("direction") not in {"imports", "exports"}:
            errors.append(f"{owner}: invalid direction {row.get('direction')}")
        if row.get("classification_level") != "HS6" or not re.fullmatch(r"\d{6}", str(row.get("commodity_code", ""))):
            errors.append(f"{owner}: expected a six-digit HS heading")
        if not re.fullmatch(r"[A-Z]{3}", str(row.get("partner_iso3", ""))):
            errors.append(f"{owner}: expected partner ISO3 code")
        measures = [row.get("trade_value", {}), row.get("quantity", {})]
        for measure in measures:
            if not {"value", "display", "unit", "status"} <= set(measure):
                errors.append(f"{owner}: malformed DataWeb measurement")
            if measure.get("status") not in {"reported", "not-reported"}:
                errors.append(f"{owner}: invalid measurement status {measure.get('status')}")
        if not any(measure.get("value", 0) and measure.get("value", 0) > 0 for measure in measures):
            errors.append(f"{owner}: retained DataWeb row must contain a positive reported value or quantity")

    dataweb_minerals = {row.get("mineral_id") for row in datasets["dataweb-trade"]}
    if dataweb_minerals != ids["minerals"]:
        errors.append(f"dataweb-trade: expected all pilot minerals, found {sorted(dataweb_minerals)}")
    for query in datasets["dataweb-query-manifest"]:
        owner = f"dataweb-query-manifest/{query.get('id')}"
        if query.get("direction") not in {"imports", "exports"}:
            errors.append(f"{owner}: invalid direction")
        if query.get("years") != [1989, 1990, 1991, 1992]:
            errors.append(f"{owner}: expected 1989-1992 query years")
        expected_count = sum(row["direction"] == query.get("direction") for row in datasets["dataweb-trade"])
        if query.get("record_count") != expected_count:
            errors.append(f"{owner}: record count does not match cached rows")
        if not re.fullmatch(r"[0-9a-f]{64}", str(query.get("query_sha256", ""))):
            errors.append(f"{owner}: malformed query hash")

    required_comtrade_fields = {
        "year", "reporter_code", "reporter_name", "reporter_iso3", "partner_code", "partner_name",
        "partner_iso3", "flow_code", "flow", "classification_code", "classification_label",
        "is_original_classification", "commodity_code", "commodity_description", "product_family",
        "scope_confidence", "scope_caveat", "primary_value", "value_unit", "quantity",
        "quantity_unit_code", "quantity_unit", "quantity_estimated", "net_weight_kg",
        "net_weight_estimated", "valuation_basis", "query_id", "source_id", "source_url",
        "access_date", "transcription_status", "confidence"
    }
    for row in datasets["comtrade-rare-earth"]:
        owner = f"comtrade-rare-earth/{row.get('id')}"
        missing = sorted(required_comtrade_fields - set(row))
        if missing:
            errors.append(f"{owner}: missing {', '.join(missing)}")
        year = row.get("year")
        if not isinstance(year, int) or not 1962 <= year <= 1992:
            errors.append(f"{owner}: invalid Comtrade year {year}")
        expected_class = "S1" if year <= 1975 else "S2" if year <= 1987 else "S3"
        if row.get("classification_code") != expected_class:
            errors.append(f"{owner}: expected {expected_class} for {year}")
        if row.get("reporter_code") not in {156, 841, 842} or row.get("partner_code") not in {0, 156, 842}:
            errors.append(f"{owner}: unexpected reporter or partner code")
        if row.get("flow_code") not in {"M", "X"}:
            errors.append(f"{owner}: invalid flow")
        if row.get("scope_confidence") not in {"high", "low"} or not row.get("scope_caveat"):
            errors.append(f"{owner}: missing scope qualification")
        if not isinstance(row.get("is_original_classification"), bool):
            errors.append(f"{owner}: classification status must be boolean")
        if not isinstance(row.get("primary_value"), int) or row.get("primary_value") < 0:
            errors.append(f"{owner}: primary value must be a nonnegative integer")
        if row.get("source_id") != "un-comtrade":
            errors.append(f"{owner}: source_id must be un-comtrade")
        if row.get("query_id") not in ids["comtrade-query-manifest"]:
            errors.append(f"{owner}: missing query manifest {row.get('query_id')}")

    manifests = datasets["comtrade-query-manifest"]
    if len([row for row in manifests if row.get("reporter") == "united-states"]) != 31:
        errors.append("comtrade-query-manifest: expected one U.S. query for every year 1962-1992")
    if len([row for row in manifests if row.get("reporter") == "china"]) != 9:
        errors.append("comtrade-query-manifest: expected China query plans for 1984-1992")
    if sum(row.get("record_count", 0) for row in manifests) != len(datasets["comtrade-rare-earth"]):
        errors.append("comtrade-query-manifest: record counts do not reconcile to the static cache")
    for query in manifests:
        owner = f"comtrade-query-manifest/{query.get('id')}"
        if not str(query.get("query_url", "")).startswith("https://comtradeapi.un.org/public/v1/preview/"):
            errors.append(f"{owner}: unexpected query URL")
        if not re.fullmatch(r"[0-9a-f]{64}", str(query.get("query_sha256", ""))):
            errors.append(f"{owner}: malformed query hash")

    required_strategic_comtrade_fields = {
        "year", "mineral_id", "supply_chain_stage", "reporter_code", "reporter_name",
        "reporter_iso3", "partner_code", "partner_name", "partner_iso3", "flow_code", "flow",
        "classification_code", "classification_label", "is_original_classification",
        "commodity_code", "commodity_description", "scope_confidence", "scope_caveat",
        "primary_value", "value_unit", "quantity", "quantity_unit_code", "quantity_unit",
        "quantity_estimated", "net_weight_kg", "net_weight_estimated", "valuation_basis",
        "query_id", "source_id", "source_url", "discovery_url", "access_date",
        "transcription_status", "confidence"
    }
    strategic_rows = datasets["comtrade-strategic-materials"]
    strategic_manifest = datasets["comtrade-strategic-query-manifest"]
    for row in strategic_rows:
        owner = f"comtrade-strategic-materials/{row.get('id')}"
        missing = sorted(required_strategic_comtrade_fields - set(row))
        if missing:
            errors.append(f"{owner}: missing {', '.join(missing)}")
        year = row.get("year")
        expected_class = "S1" if year <= 1975 else "S2" if year <= 1987 else "S3"
        if not isinstance(year, int) or not 1962 <= year <= 1992 or row.get("classification_code") != expected_class:
            errors.append(f"{owner}: invalid year or classification")
        if row.get("mineral_id") not in ids["minerals"] or row.get("mineral_id") == "rare-earth-elements":
            errors.append(f"{owner}: unexpected mineral {row.get('mineral_id')}")
        if row.get("reporter_code") not in {841, 842} or row.get("partner_code") not in {0, 68, 152, 156, 180, 710, 740, 792, 894}:
            errors.append(f"{owner}: unexpected reporter or partner code")
        if row.get("scope_confidence") not in {"high", "medium", "low"} or not row.get("scope_caveat"):
            errors.append(f"{owner}: missing scope qualification")
        if row.get("source_id") != "un-comtrade" or row.get("query_id") not in ids["comtrade-strategic-query-manifest"]:
            errors.append(f"{owner}: invalid source or query reference")
        if not isinstance(row.get("primary_value"), int) or row.get("primary_value") < 0:
            errors.append(f"{owner}: primary value must be a nonnegative integer")

    expected_strategic_minerals = ids["minerals"] - {"rare-earth-elements"}
    if {row.get("mineral_id") for row in strategic_rows} != expected_strategic_minerals:
        errors.append("comtrade-strategic-materials: expected all nine non-rare-earth pilot materials")
    if {row.get("year") for row in strategic_manifest} != set(range(1962, 1993)):
        errors.append("comtrade-strategic-query-manifest: expected one query for every year 1962-1992")
    if sum(row.get("record_count", 0) for row in strategic_manifest) != len(strategic_rows):
        errors.append("comtrade-strategic-query-manifest: record counts do not reconcile to the static cache")
    for query in strategic_manifest:
        owner = f"comtrade-strategic-query-manifest/{query.get('id')}"
        if not str(query.get("query_url", "")).startswith("https://comtradeapi.un.org/public/v1/preview/"):
            errors.append(f"{owner}: unexpected query URL")
        for field in ["query_sha256", "code_registry_sha256"]:
            if not re.fullmatch(r"[0-9a-f]{64}", str(query.get(field, ""))):
                errors.append(f"{owner}: malformed {field}")

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
    print(f"usgs-ds140 commodities={len(commodity_ids)}, series={observed_series}, measures={observed_measures}, observations={observed_ds140}")


if __name__ == "__main__":
    main()
