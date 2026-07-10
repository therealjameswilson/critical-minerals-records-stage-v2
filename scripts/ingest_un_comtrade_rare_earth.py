#!/usr/bin/env python3
"""Build a source-bounded UN Comtrade rare-earth continuity series.

The portal ends in 1992.  This importer therefore uses Comtrade only for the
1962-1992 portion of its annual merchandise-trade coverage and keeps each SITC
revision separate.  It queries U.S.-reported trade with China and the world,
plus China-reported mirror flows where available.  Broad historical commodity
proxies are never merged into the precise 1989-1992 USITC DataWeb layer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "history-stack"
OUTPUT = DATA / "comtrade-rare-earth.json"
MANIFEST_OUTPUT = DATA / "comtrade-query-manifest.json"
API_ROOT = "https://comtradeapi.un.org/public/v1/preview/C/A"
SOURCE_URL = "https://comtradeplus.un.org/"
REFERENCE_ROOT = "https://comtradeapi.un.org/files/v1/app/reference"

REPORTERS = {
    156: {"name": "China", "iso3": "CHN"},
    841: {"name": "USA and Puerto Rico (...1980)", "iso3": "USA"},
    842: {"name": "USA", "iso3": "USA"},
}
PARTNERS = {
    0: {"name": "World", "iso3": None},
    156: {"name": "China", "iso3": "CHN"},
    842: {"name": "USA", "iso3": "USA"},
}
FLOWS = {"M": "Imports", "X": "Exports"}

CLASSIFICATIONS = {
    "S1": {
        "years": range(1962, 1976),
        "label": "SITC Revision 1",
        "codes": {
            "51326": {
                "family": "metals-proxy",
                "confidence": "low",
                "caveat": "Includes alkali and alkaline-earth metals together with rare-earth metals; it is not a rare-earth-only series.",
            },
        },
    },
    "S2": {
        "years": range(1976, 1988),
        "label": "SITC Revision 2",
        "codes": {
            "52217": {
                "family": "metals-proxy",
                "confidence": "low",
                "caveat": "Includes alkali and alkaline-earth metals with rare-earth metals, yttrium, and scandium.",
            },
            "52492": {
                "family": "compounds-proxy",
                "confidence": "low",
                "caveat": "Includes thorium and uranium-depleted compounds with rare-earth, yttrium, and scandium compounds.",
            },
            "77881": {
                "family": "magnet-system-proxy",
                "confidence": "low",
                "caveat": "Includes electromagnets, chucks, clamps, couplings, brakes, and lifting heads; it is not a permanent-magnet or rare-earth-magnet series.",
            },
        },
    },
    "S3": {
        "years": range(1988, 1993),
        "label": "SITC Revision 3",
        "codes": {
            "52229": {
                "family": "metals-proxy",
                "confidence": "low",
                "caveat": "Includes calcium, strontium, and barium with rare-earth metals, scandium, and yttrium.",
            },
            "52595": {
                "family": "compounds",
                "confidence": "high",
                "caveat": "Rare-earth, yttrium, and scandium compounds or mixtures; compare with other revisions only through an explicit concordance.",
            },
            "77881": {
                "family": "magnet-system-proxy",
                "confidence": "low",
                "caveat": "Includes electromagnets and associated holding, coupling, braking, and lifting equipment; it is not rare-earth-magnet trade.",
            },
            "89939": {
                "family": "pyrophoric-alloy-proxy",
                "confidence": "low",
                "caveat": "Includes ferrocerium with other pyrophoric alloys and prepared fuels; it is a downstream basket code.",
            },
        },
    },
}


def classification_for_year(year: int) -> str:
    if year <= 1975:
        return "S1"
    if year <= 1987:
        return "S2"
    return "S3"


def reporter_code(country: str, year: int) -> int:
    if country == "china":
        return 156
    return 841 if year <= 1980 else 842


def query_url(classification: str, year: int, reporter: int, partners: list[int]) -> str:
    codes = CLASSIFICATIONS[classification]["codes"]
    query = urlencode({
        "period": str(year),
        "reporterCode": str(reporter),
        "cmdCode": ",".join(codes),
        "flowCode": "M,X",
        "partnerCode": ",".join(str(value) for value in partners),
        "partner2Code": "0",
        "customsCode": "C00",
        "motCode": "0",
        "maxRecords": "500",
    })
    return f"{API_ROOT}/{classification}?{query}"


def fetch_json(url: str, retries: int = 7) -> dict:
    request = Request(url, headers={"User-Agent": "critical-minerals-records-stage-v2/2.0"})
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=90) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("statusCode") == 429:
                raise HTTPError(url, 429, payload.get("message", "rate limited"), {}, None)
            return payload
        except HTTPError as error:
            if error.code != 429 or attempt == retries - 1:
                raise
            time.sleep(2.5 + attempt)
    raise RuntimeError("UN Comtrade request failed")


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


def quantity_units(cache_dir: Path | None) -> dict[int, dict]:
    cache_path = cache_dir / "reference-quantity-units.json" if cache_dir else None
    if cache_path and cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        payload = fetch_json(f"{REFERENCE_ROOT}/QuantityUnits.json")
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {int(row["qtyCode"]): row for row in payload["results"]}


def query_specifications() -> list[dict]:
    specs = []
    for year in range(1962, 1993):
        classification = classification_for_year(year)
        specs.append({
            "country": "united-states",
            "year": year,
            "classification": classification,
            "reporter": reporter_code("united-states", year),
            "partners": [0, 156],
        })
        if year >= 1984:
            specs.append({
                "country": "china",
                "year": year,
                "classification": classification,
                "reporter": 156,
                "partners": [0, 842],
            })
    return specs


def query_id(spec: dict) -> str:
    return f"comtrade-{spec['classification'].lower()}-{spec['year']}-{spec['country']}"


def load_query(spec: dict, cache_dir: Path | None, throttle: float) -> tuple[dict, str, bool]:
    identifier = query_id(spec)
    url = query_url(spec["classification"], spec["year"], spec["reporter"], spec["partners"])
    cache_path = cache_dir / f"{identifier}.json" if cache_dir else None
    cached = bool(cache_path and cache_path.exists())
    if cached:
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
    return payload, url, cached


def normalize(spec: dict, payload: dict, references: dict[str, dict], units: dict[int, dict], access_date: str) -> list[dict]:
    classification = spec["classification"]
    definition = CLASSIFICATIONS[classification]
    rows = []
    for source in payload.get("data", []):
        code = str(source.get("cmdCode", ""))
        if code not in definition["codes"]:
            continue
        scope = definition["codes"][code]
        reporter = REPORTERS.get(int(source["reporterCode"]), {"name": str(source["reporterCode"]), "iso3": source.get("reporterISO")})
        partner = PARTNERS.get(int(source["partnerCode"]), {"name": str(source["partnerCode"]), "iso3": source.get("partnerISO")})
        flow_code = source["flowCode"]
        qty_unit = units.get(int(source.get("qtyUnitCode", -1)), {})
        primary_value = source.get("primaryValue")
        if primary_value is None:
            continue
        rows.append({
            "id": f"{query_id(spec)}-{flow_code.lower()}-{source['partnerCode']}-{code}",
            "year": int(source["period"]),
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
            "commodity_description": references[code]["text"].split(" - ", 1)[-1],
            "product_family": scope["family"],
            "scope_confidence": scope["confidence"],
            "scope_caveat": scope["caveat"],
            "primary_value": int(round(primary_value)),
            "value_unit": "current U.S. dollars",
            "quantity": source.get("qty"),
            "quantity_unit_code": int(source.get("qtyUnitCode", -1)),
            "quantity_unit": qty_unit.get("qtyAbbr") or qty_unit.get("qtyDescription") or "Not reported",
            "quantity_estimated": bool(source.get("isQtyEstimated")),
            "net_weight_kg": source.get("netWgt"),
            "net_weight_estimated": bool(source.get("isNetWgtEstimated")),
            "valuation_basis": "CIF-type import value" if flow_code == "M" else "FOB-type export value",
            "query_id": query_id(spec),
            "source_id": "un-comtrade",
            "source_url": SOURCE_URL,
            "access_date": access_date,
            "transcription_status": "machine-ingested-un-comtrade-public-preview",
            "confidence": "high for the reported record; commodity scope varies as labeled",
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--access-date", default=date.today().isoformat())
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--throttle", type=float, default=2.2)
    args = parser.parse_args()

    references = {code: reference_rows(code, args.cache_dir) for code in CLASSIFICATIONS}
    units = quantity_units(args.cache_dir)
    rows = []
    manifest = []
    for spec in query_specifications():
        payload, url, _cached = load_query(spec, args.cache_dir, args.throttle)
        normalized = normalize(spec, payload, references[spec["classification"]], units, args.access_date)
        rows.extend(normalized)
        manifest.append({
            "id": query_id(spec),
            "year": spec["year"],
            "reporter": spec["country"],
            "reporter_code": spec["reporter"],
            "partner_codes": spec["partners"],
            "classification_code": spec["classification"],
            "commodity_codes": list(CLASSIFICATIONS[spec["classification"]]["codes"]),
            "flow_codes": ["M", "X"],
            "record_count": len(normalized),
            "query_url": url,
            "query_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
            "source_id": "un-comtrade",
            "access_date": args.access_date,
        })

    rows.sort(key=lambda row: (row["year"], row["classification_code"], row["reporter_code"], row["flow_code"], row["partner_code"], row["commodity_code"]))
    identifiers = [row["id"] for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise RuntimeError("Duplicate UN Comtrade row identifiers")
    OUTPUT.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} UN Comtrade continuity records and {len(manifest)} query records")


if __name__ == "__main__":
    main()
