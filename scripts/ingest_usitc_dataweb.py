#!/usr/bin/env python3
"""Ingest official USITC DataWeb partner trade for 1989-1992.

DataWeb republishes official U.S. merchandise trade statistics from the
Department of Commerce, Census Bureau.  The public query interface begins in
1989, so this module only writes the four years that overlap the portal's
1861-1992 historical boundary.  It does not require or store an API token: the
script initializes the same anonymous XSRF session used by the public browser
query and writes a sanitized static cache for GitHub Pages.

The query uses six-digit Harmonized System headings so import (HTS) and export
(Schedule B) records can be compared at their shared international level.  A
heading remains a commodity proxy, not a claim about mine origin or end use.
"""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.request import HTTPCookieProcessor, Request, build_opener


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "history-stack" / "dataweb-trade.json"
MANIFEST_OUTPUT = ROOT / "data" / "history-stack" / "dataweb-query-manifest.json"
BASE_URL = "https://datawebws.usitc.gov/dataweb"
SOURCE_URL = "https://dataweb.usitc.gov/"
YEARS = [1989, 1990, 1991, 1992]

# Six-digit headings are deliberately broad.  The response-supplied historical
# descriptions are stored on every output row and control over these labels.
COMMODITIES = [
    {"code": "760110", "mineral_id": "aluminum", "stage": "refining", "scope": "Unwrought aluminum, not alloyed"},
    {"code": "760120", "mineral_id": "aluminum", "stage": "refining", "scope": "Unwrought aluminum alloys"},
    {"code": "260600", "mineral_id": "bauxite", "stage": "mining", "scope": "Aluminum ores and concentrates"},
    {"code": "281820", "mineral_id": "bauxite", "stage": "processing", "scope": "Aluminum oxide other than artificial corundum"},
    {"code": "261000", "mineral_id": "chromium", "stage": "mining", "scope": "Chromium ores and concentrates"},
    {"code": "720241", "mineral_id": "chromium", "stage": "processing", "scope": "Ferrochromium containing more than 4 percent carbon"},
    {"code": "720249", "mineral_id": "chromium", "stage": "processing", "scope": "Other ferrochromium"},
    {"code": "260500", "mineral_id": "cobalt", "stage": "mining", "scope": "Cobalt ores and concentrates"},
    {"code": "810520", "mineral_id": "cobalt", "stage": "processing", "scope": "Cobalt mattes and other intermediate products"},
    {"code": "260300", "mineral_id": "copper", "stage": "mining", "scope": "Copper ores and concentrates"},
    {"code": "740311", "mineral_id": "copper", "stage": "refining", "scope": "Refined copper cathodes and sections of cathodes"},
    {"code": "740312", "mineral_id": "copper", "stage": "refining", "scope": "Refined copper wire bars"},
    {"code": "740313", "mineral_id": "copper", "stage": "refining", "scope": "Refined copper billets"},
    {"code": "740319", "mineral_id": "copper", "stage": "refining", "scope": "Other refined copper"},
    {"code": "260200", "mineral_id": "manganese", "stage": "mining", "scope": "Manganese ores and concentrates"},
    {"code": "720211", "mineral_id": "manganese", "stage": "processing", "scope": "Ferromanganese containing more than 2 percent carbon"},
    {"code": "720219", "mineral_id": "manganese", "stage": "processing", "scope": "Other ferromanganese"},
    {"code": "261220", "mineral_id": "rare-earth-elements", "stage": "mining", "scope": "Thorium ores and concentrates; retained because the contemporary rare-earth tables include monazite and thorium categories"},
    {"code": "280530", "mineral_id": "rare-earth-elements", "stage": "refining", "scope": "Rare-earth metals, scandium and yttrium"},
    {"code": "284690", "mineral_id": "rare-earth-elements", "stage": "processing", "scope": "Compounds of rare-earth metals, yttrium or scandium"},
    {"code": "360690", "mineral_id": "rare-earth-elements", "stage": "processing", "scope": "Other combustible preparations including ferrocerium and pyrophoric alloys; broad proxy"},
    {"code": "260900", "mineral_id": "tin", "stage": "mining", "scope": "Tin ores and concentrates"},
    {"code": "800110", "mineral_id": "tin", "stage": "refining", "scope": "Unwrought tin, not alloyed"},
    {"code": "800120", "mineral_id": "tin", "stage": "refining", "scope": "Unwrought tin alloys"},
    {"code": "261100", "mineral_id": "tungsten", "stage": "mining", "scope": "Tungsten ores and concentrates"},
    {"code": "810110", "mineral_id": "tungsten", "stage": "processing", "scope": "Tungsten powders"},
    {"code": "810191", "mineral_id": "tungsten", "stage": "refining", "scope": "Unwrought tungsten, including bars and rods obtained by sintering"},
    {"code": "810192", "mineral_id": "tungsten", "stage": "processing", "scope": "Tungsten bars and rods other than sintered articles"},
    {"code": "261210", "mineral_id": "uranium", "stage": "mining", "scope": "Uranium ores and concentrates"},
    {"code": "284410", "mineral_id": "uranium", "stage": "processing", "scope": "Natural uranium and its compounds"},
    {"code": "284420", "mineral_id": "uranium", "stage": "processing", "scope": "Uranium enriched in U235 and plutonium and their compounds"},
    {"code": "284430", "mineral_id": "uranium", "stage": "processing", "scope": "Uranium depleted in U235 and thorium and their compounds"},
]

FLOW_CONFIG = {
    "imports": {
        "trade_type": "Import",
        "classification": "HTS",
        "measures": ["CONS_CUSTOMS_VALUE", "CONS_FIR_UNIT_QUANT"],
        "flow_label": "Imports for consumption",
        "value_basis": "Customs value",
    },
    "exports": {
        "trade_type": "TotExp",
        "classification": "HTS",
        "measures": ["FAS_VALUE", "FIRST_UNIT_QUANTITY"],
        "flow_label": "Total exports",
        "value_basis": "F.A.S. value",
    },
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def integer(value: Any) -> int | None:
    text = str(value or "").strip().replace(",", "")
    if not text or text in {"--", "N/A", "NA"}:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def unit_from_description(value: str) -> str:
    text = str(value or "").strip()
    for prefix in ("Value for: ", "Quantity for: "):
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text or "Source unit not reported"


def session_opener():
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    opener.open(BASE_URL + "/api/v2/query/getGlobalVars", timeout=60).read()
    token = next((cookie.value for cookie in jar if cookie.name == "XSRF-TOKEN"), None)
    if not token:
        raise RuntimeError("DataWeb did not issue an anonymous XSRF token")
    return opener, token


def country_directory(opener) -> dict[str, dict]:
    response = opener.open(BASE_URL + "/api/v2/country/getAllCountries", timeout=60)
    payload = json.loads(response.read().decode("utf-8"))
    rows = payload.get("options", payload if isinstance(payload, list) else [])
    directory = {}
    for row in rows:
        label = str(row.get("name", "")).strip()
        if not label:
            continue
        directory[label.casefold()] = row
        source_name = re.sub(r"\s+-\s+[A-Z]{2}\s+-\s+[A-Z]{3}$", "", label)
        directory[source_name.casefold()] = row
    return directory


def request_payload(direction: str) -> dict:
    flow = FLOW_CONFIG[direction]
    codes = [row["code"] for row in COMMODITIES]
    commodity_rows = [{"name": row["scope"].upper(), "value": row["code"]} for row in COMMODITIES]
    column = "HTS6 & DESCRIPTION"
    return {
        "savedQueryType": "", "savedQueryID": "", "savedQueryName": "", "savedQueryDesc": "",
        "isOwner": False, "runMonthly": False, "unitConversion": "0", "manualConversions": [],
        "reportOptions": {"tradeType": flow["trade_type"], "classificationSystem": flow["classification"]},
        "searchOptions": {
            "MiscGroup": {
                "districts": {"aggregation": "Aggregate District", "districtGroups": {"userGroups": []}, "districts": [], "districtsExpanded": [], "districtsSelectType": "all"},
                "importPrograms": {"aggregation": None, "importPrograms": [], "programsSelectType": "all"},
                "extImportPrograms": {"aggregation": "Aggregate CSC", "extImportPrograms": [], "extImportProgramsExpanded": [], "programsSelectType": "all"},
                "provisionCodes": {"aggregation": "Aggregate RPCODE", "provisionCodesSelectType": "all", "rateProvisionCodes": [], "rateProvisionCodesExpanded": [], "rateProvisionGroups": {"systemGroups": []}},
            },
            "commodities": {
                "aggregation": "Break Out Commodities", "codeDisplayFormat": "YES", "commodities": codes,
                "commoditiesExpanded": commodity_rows, "commoditiesManual": ",".join(codes),
                "commodityGroups": {"systemGroups": [], "userGroups": []}, "commoditySelectType": "list",
                "granularity": "6", "groupGranularity": None, "searchGranularity": None, "showHTSValidDetails": True,
            },
            "componentSettings": {
                "dataToReport": flow["measures"], "scale": "1", "timeframeSelectType": "fullYears",
                "years": [str(year) for year in YEARS], "startDate": None, "endDate": None,
                "startMonth": None, "endMonth": None, "yearsTimeline": "Annual",
            },
            "countries": {
                "aggregation": "Break Out Countries", "countries": [], "countriesExpanded": [],
                "countriesSelectType": "all", "countryGroups": {"systemGroups": [], "userGroups": []},
            },
        },
        "sortingAndDataFormat": {
            "DataSort": {
                "columnOrder": ["COUNTRY", column],
                "fullColumnOrder": [
                    {"checked": False, "disabled": False, "hasChildren": False, "name": "COUNTRY", "value": "COUNTRY", "classificationSystem": "", "groupUUID": "", "items": [], "tradeType": ""},
                    {"checked": False, "disabled": False, "hasChildren": False, "name": column, "value": column, "classificationSystem": "", "groupUUID": "", "items": [], "tradeType": ""},
                ],
                "sortOrder": [
                    {"sortData": "COUNTRY", "orderBy": "asc", "year": "0"},
                    {"sortData": column, "orderBy": "asc", "year": "0"},
                ],
            },
            "reportCustomizations": {"exportCombineTables": False, "totalRecords": "20000", "exportRawData": False},
        },
        "deletedCountryUserGroups": [], "deletedCommodityUserGroups": [], "deletedDistrictUserGroups": [],
    }


def run_report(opener, token: str, payload: dict) -> dict:
    request = Request(
        BASE_URL + "/api/v2/report2/runReport",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json", "Accept": "application/json, text/plain, */*",
            "Origin": SOURCE_URL.rstrip("/"), "Referer": SOURCE_URL, "X-XSRF-TOKEN": token,
            "User-Agent": "critical-minerals-records-stage-v2/2.0",
        },
        method="POST",
    )
    with opener.open(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def table_rows(table: dict) -> dict[tuple[str, str, int], dict]:
    columns = []
    for group in table.get("column_groups", []):
        columns.extend(column.get("label") for column in group.get("columns", []))
    rows: dict[tuple[str, str, int], dict] = {}
    for source_row in table.get("row_groups", [{}])[0].get("rowsNew", []):
        values = [entry.get("value") for entry in source_row.get("rowEntries", [])]
        record = dict(zip(columns, values))
        country = str(record.get("Country", "")).strip()
        code = str(record.get("HTS Number", record.get("Schedule B Number", ""))).strip()
        if not country or not code:
            continue
        for year in YEARS:
            rows[(country, code, year)] = {
                "country": country,
                "code": code,
                "description": str(record.get("Description", "")).strip(),
                "unit_description": str(record.get("Quantity Description", "")).strip(),
                "value": integer(record.get(str(year))),
            }
    return rows


def normalize_report(direction: str, response: dict, countries: dict[str, dict], access_date: str) -> list[dict]:
    tables = response.get("dto", {}).get("tables", [])
    if len(tables) < 2:
        raise RuntimeError(f"DataWeb {direction} response did not include value and quantity tables")
    values = table_rows(tables[0])
    quantities = table_rows(tables[1])
    commodity_by_code = {row["code"]: row for row in COMMODITIES}
    flow = FLOW_CONFIG[direction]
    rows = []
    for key in sorted(set(values) | set(quantities), key=lambda item: (item[2], item[1], item[0])):
        value_row = values.get(key, {})
        quantity_row = quantities.get(key, {})
        trade_value = value_row.get("value")
        quantity = quantity_row.get("value")
        if not (trade_value and trade_value > 0) and not (quantity and quantity > 0):
            continue
        country_name, code, year = key
        commodity = commodity_by_code.get(code)
        if not commodity:
            continue
        partner = countries.get(country_name.casefold(), {})
        description = value_row.get("description") or quantity_row.get("description") or commodity["scope"]
        quantity_unit = unit_from_description(quantity_row.get("unit_description") or value_row.get("unit_description"))
        rows.append({
            "id": f"usitc-dataweb-{year}-{direction}-{code}-{slug(country_name)}",
            "year": year,
            "mineral_id": commodity["mineral_id"],
            "direction": direction,
            "trade_flow": flow["flow_label"],
            "classification_system": "HTS" if direction == "imports" else "Schedule B at shared HS6 level",
            "classification_level": "HS6",
            "commodity_code": code,
            "commodity_description": description,
            "commodity_scope_note": commodity["scope"],
            "supply_chain_stage": commodity["stage"],
            "source_partner_name": country_name,
            "partner_code": partner.get("value"),
            "partner_iso2": partner.get("iso2"),
            "partner_iso3": partner.get("iso3"),
            "trade_value": {
                "value": trade_value,
                "display": f"${trade_value:,}" if trade_value is not None else "Not reported",
                "unit": "current U.S. dollars",
                "status": "reported" if trade_value is not None else "not-reported",
                "valuation_basis": flow["value_basis"],
            },
            "quantity": {
                "value": quantity,
                "display": f"{quantity:,}" if quantity is not None else "Not reported",
                "unit": quantity_unit,
                "status": "reported" if quantity is not None else "not-reported",
            },
            "source_id": "usitc-dataweb",
            "source_origin_agency": "U.S. Department of Commerce, Census Bureau",
            "publication_title": "USITC DataWeb official U.S. merchandise trade statistics",
            "table_or_page": f"Anonymous DataWeb query; {flow['flow_label']}; {code}; country breakout; annual {year}",
            "source_url": SOURCE_URL,
            "access_date": access_date,
            "transcription_status": "machine-ingested-public-dataweb-query",
            "confidence": "high",
            "caveat": "Partner country is the reported origin or destination, not proof of mine origin, ownership, routing, end use, or strategic importance. The HS6 heading may include products outside the portal's narrower mineral concept.",
        })
    return rows


def manifest(rows: list[dict], access_date: str, payloads: dict[str, dict]) -> list[dict]:
    result = []
    for direction, payload in payloads.items():
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        direction_rows = [row for row in rows if row["direction"] == direction]
        result.append({
            "id": f"usitc-dataweb-{direction}-1989-1992-hs6",
            "direction": direction,
            "years": YEARS,
            "classification_system": "HTS imports; Schedule B exports at shared HS6 level",
            "commodity_codes": [row["code"] for row in COMMODITIES],
            "query_sha256": hashlib.sha256(canonical).hexdigest(),
            "record_count": len(direction_rows),
            "positive_value_filter": "Rows are retained when reported customs/F.A.S. value or first quantity is greater than zero. Missing and suppressed values are not converted to zero.",
            "source_id": "usitc-dataweb",
            "source_url": SOURCE_URL,
            "access_date": access_date,
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--access-date", default=date.today().isoformat())
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()

    opener, token = session_opener()
    countries = country_directory(opener)
    payloads = {direction: request_payload(direction) for direction in FLOW_CONFIG}
    rows = []
    for direction, payload in payloads.items():
        cache_path = args.cache_dir / f"dataweb-{direction}-1989-1992.json" if args.cache_dir else None
        if cache_path and cache_path.exists():
            response = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            response = run_report(opener, token, payload)
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(response, indent=2) + "\n", encoding="utf-8")
        rows.extend(normalize_report(direction, response, countries, args.access_date))

    rows.sort(key=lambda row: (row["year"], row["mineral_id"], row["direction"], row["commodity_code"], row["source_partner_name"]))
    identifiers = [row["id"] for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise RuntimeError("Duplicate DataWeb trade identifiers")
    OUTPUT.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    MANIFEST_OUTPUT.write_text(json.dumps(manifest(rows, args.access_date, payloads), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} DataWeb partner trade records to {OUTPUT}")


if __name__ == "__main__":
    main()
