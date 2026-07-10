#!/usr/bin/env python3
"""Ingest classification-bounded UN Comtrade context for pilot materials.

The importer queries U.S.-reported annual trade with the world and selected
countries already represented in the atlas. It never converts or splices SITC
revisions and does not infer contained-mineral quantities from product weights.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import yaml

from ingest_un_comtrade_rare_earth import (
    API_ROOT,
    FLOWS,
    REFERENCE_ROOT,
    REPORTERS,
    SOURCE_URL,
    fetch_json,
    quantity_units,
    reporter_code,
)


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "history-stack"
CROSSWALK = ROOT / "data" / "crosswalks" / "comtrade_sitc_mineral_codes.yml"
OUTPUT = DATA / "comtrade-strategic-materials.json"
MANIFEST_OUTPUT = DATA / "comtrade-strategic-query-manifest.json"
UNCCD_DISCOVERY_URL = "https://www.unccd.int/resources/knowledge-sharing-system/united-nations-commodity-trade-statistics-database-un-comtrade"

PARTNERS = {
    0: {"name": "World", "iso3": None},
    68: {"name": "Bolivia", "iso3": "BOL"},
    152: {"name": "Chile", "iso3": "CHL"},
    156: {"name": "China", "iso3": "CHN"},
    180: {"name": "Democratic Republic of the Congo", "iso3": "COD"},
    710: {"name": "South Africa", "iso3": "ZAF"},
    740: {"name": "Suriname", "iso3": "SUR"},
    792: {"name": "Turkey", "iso3": "TUR"},
    894: {"name": "Zambia", "iso3": "ZMB"},
}


def load_crosswalk() -> dict:
    payload = yaml.safe_load(CROSSWALK.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise RuntimeError("Unsupported Comtrade crosswalk schema")
    return payload


def classification_for_year(year: int) -> str:
    if year <= 1975:
        return "S1"
    if year <= 1987:
        return "S2"
    return "S3"


def reference_rows(classification: str, cache_dir: Path | None) -> dict[str, dict]:
    cache_path = cache_dir / f"reference-{classification}.json" if cache_dir else None
    if cache_path and cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        payload = fetch_json(f"{REFERENCE_ROOT}/{classification}.json")
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {str(row["id"]): row for row in payload["results"]}


def query_id(year: int, classification: str) -> str:
    return f"comtrade-strategic-{classification.lower()}-{year}-united-states"


def query_url(year: int, classification: str, codes: dict[str, dict]) -> str:
    query = urlencode({
        "period": str(year),
        "reporterCode": str(reporter_code("united-states", year)),
        "cmdCode": ",".join(codes),
        "flowCode": "M,X",
        "partnerCode": ",".join(str(value) for value in PARTNERS),
        "partner2Code": "0",
        "customsCode": "C00",
        "motCode": "0",
        "maxRecords": "500",
    })
    return f"{API_ROOT}/{classification}?{query}"


def load_query(year: int, classification: str, codes: dict[str, dict], cache_dir: Path | None, throttle: float) -> tuple[dict, str]:
    identifier = query_id(year, classification)
    url = query_url(year, classification, codes)
    cache_path = cache_dir / f"{identifier}.json" if cache_dir else None
    if cache_path and cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        payload = fetch_json(url)
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        if throttle:
            time.sleep(throttle)
    if payload.get("error"):
        raise RuntimeError(f"{identifier}: {payload['error']}")
    if payload.get("count", 0) >= 500:
        raise RuntimeError(f"{identifier}: response may be truncated at 500 rows")
    return payload, url


def validate_codes(crosswalk: dict, references: dict[str, dict]) -> None:
    for classification, definition in crosswalk["classifications"].items():
        for code in definition["codes"]:
            reference = references[classification].get(code)
            if not reference or reference.get("isLeaf") != "1":
                raise RuntimeError(f"{classification} {code}: missing official leaf reference")


def normalize(
    year: int,
    classification: str,
    payload: dict,
    crosswalk: dict,
    references: dict[str, dict],
    units: dict[int, dict],
    access_date: str,
) -> list[dict]:
    definition = crosswalk["classifications"][classification]
    codes = definition["codes"]
    rows = []
    for source in payload.get("data", []):
        code = str(source.get("cmdCode", ""))
        if code not in codes or source.get("primaryValue") is None:
            continue
        scope = codes[code]
        reporter = REPORTERS.get(int(source["reporterCode"]), {"name": str(source["reporterCode"]), "iso3": source.get("reporterISO")})
        partner = PARTNERS.get(int(source["partnerCode"]), {"name": str(source["partnerCode"]), "iso3": source.get("partnerISO")})
        flow_code = source["flowCode"]
        qty_unit = units.get(int(source.get("qtyUnitCode", -1)), {})
        rows.append({
            "id": f"{query_id(year, classification)}-{flow_code.lower()}-{source['partnerCode']}-{code}",
            "year": year,
            "mineral_id": scope["mineral_id"],
            "supply_chain_stage": scope["stage"],
            "reporter_code": int(source["reporterCode"]),
            "reporter_name": reporter["name"],
            "reporter_iso3": reporter["iso3"],
            "partner_code": int(source["partnerCode"]),
            "partner_name": partner["name"],
            "partner_iso3": partner["iso3"],
            "flow_code": flow_code,
            "flow": FLOWS[flow_code],
            "classification_code": classification,
            "classification_label": definition["label"],
            "is_original_classification": bool(source.get("isOriginalClassification")),
            "commodity_code": code,
            "commodity_description": references[classification][code]["text"].split(" - ", 1)[-1],
            "scope_confidence": scope["confidence"],
            "scope_caveat": scope["caveat"],
            "primary_value": int(round(source["primaryValue"])),
            "value_unit": "current U.S. dollars",
            "quantity": source.get("qty"),
            "quantity_unit_code": int(source.get("qtyUnitCode", -1)),
            "quantity_unit": qty_unit.get("qtyAbbr") or qty_unit.get("qtyDescription") or "Not reported",
            "quantity_estimated": bool(source.get("isQtyEstimated")),
            "net_weight_kg": source.get("netWgt"),
            "net_weight_estimated": bool(source.get("isNetWgtEstimated")),
            "valuation_basis": "CIF-type import value" if flow_code == "M" else "FOB-type export value",
            "query_id": query_id(year, classification),
            "source_id": "un-comtrade",
            "source_url": SOURCE_URL,
            "discovery_url": UNCCD_DISCOVERY_URL,
            "access_date": access_date,
            "transcription_status": "machine-ingested-un-comtrade-public-preview",
            "confidence": "high for the reported record; commodity scope varies as labeled",
        })
    return rows


def write_compact_rows(path: Path, rows: list[dict]) -> None:
    payload = "[\n" + ",\n".join(
        f"  {json.dumps(row, ensure_ascii=True, separators=(',', ':'))}" for row in rows
    ) + "\n]\n"
    path.write_text(payload, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--access-date", default=date.today().isoformat())
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--throttle", type=float, default=2.2)
    args = parser.parse_args()

    crosswalk = load_crosswalk()
    references = {code: reference_rows(code, args.cache_dir) for code in crosswalk["classifications"]}
    validate_codes(crosswalk, references)
    units = quantity_units(args.cache_dir)
    registry_hash = hashlib.sha256(CROSSWALK.read_bytes()).hexdigest()
    rows = []
    manifest = []

    for year in range(1962, 1993):
        classification = classification_for_year(year)
        codes = crosswalk["classifications"][classification]["codes"]
        payload, url = load_query(year, classification, codes, args.cache_dir, args.throttle)
        normalized = normalize(year, classification, payload, crosswalk, references, units, args.access_date)
        rows.extend(normalized)
        manifest.append({
            "id": query_id(year, classification),
            "year": year,
            "reporter": "united-states",
            "reporter_code": reporter_code("united-states", year),
            "partner_codes": list(PARTNERS),
            "classification_code": classification,
            "commodity_codes": list(codes),
            "mineral_ids": sorted({row["mineral_id"] for row in codes.values()}),
            "flow_codes": ["M", "X"],
            "record_count": len(normalized),
            "query_url": url,
            "query_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
            "code_registry_sha256": registry_hash,
            "source_id": "un-comtrade",
            "discovery_url": UNCCD_DISCOVERY_URL,
            "access_date": args.access_date,
        })

    rows.sort(key=lambda row: (row["year"], row["mineral_id"], row["flow_code"], row["partner_code"], row["commodity_code"]))
    identifiers = [row["id"] for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise RuntimeError("Duplicate strategic-material Comtrade row identifiers")
    write_compact_rows(OUTPUT, rows)
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} strategic-material Comtrade records and {len(manifest)} query records")


if __name__ == "__main__":
    main()
