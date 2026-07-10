#!/usr/bin/env python3
"""Build reviewed historical trade detail and source-acquisition queues.

The pilot preserves the categories and units printed in official tables. It
does not force contemporaneous Census categories into the later USGS Data
Series 140 standardized series, and it does not infer partner-country rows.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "history-stack"
DETAIL_OUTPUT = DATA / "trade-details.json"
RESEARCH_OUTPUT = DATA / "trade-research.json"

IMPORT_URL = "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/rare-earth/stats/tbl3.txt"
EXPORT_URL = "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/rare-earth/stats/tbl4.txt"
CENSUS_GUIDE_URL = "https://www2.census.gov/library/publications/economic-census/1982/Guide_to_the_1982_Economic_Censuses.pdf"
CENSUS_REQUEST_URL = "https://www2.census.gov/programs-surveys/trade/reference/products/orderform.html"


IMPORT_ROWS = [
    ("Cerium compounds", 4, "4", 25, "25"),
    ("Mixtures of rare-earth oxides and chlorides", 26, "26", 99, "99"),
    ("Cerium salts", 2, "2", 7, "7"),
    ("Rare-earth oxide excluding cerium oxide", 609, "609", 13671, "13,671"),
    ("Rare-earth alloys", 75, "75", 642, "642"),
    ("Rare-earth metals including scandium and yttrium", 1, "1", 182, "182"),
    ("Other rare-earth metals", None, "Less than 0.5", 14, "14"),
    ("Ferrocerium and other pyrophoric alloys", 105, "105", 1185, "1,185"),
    ("Published total", 822, "822", 15826, "15,826"),
]

EXPORT_ROWS = [
    ("Thorium ore and concentrates", 2684, "2,684"),
    ("Ferrocerium and other pyrophoric alloys", 59, "59"),
    ("Cerium compounds", None, "Not separately available"),
    ("Rare-earth metals including scandium and yttrium", None, "Not separately available"),
    ("Published total", 2743, "2,743"),
]


def measure(value: float | None, display: str, unit: str, status: str = "reported") -> dict:
    return {"value": value, "display": display, "unit": unit, "status": status if value is not None else "not-available"}


def detail_rows(access_date: str) -> list[dict]:
    rows: list[dict] = []
    for index, (category, quantity, quantity_display, value, value_display) in enumerate(IMPORT_ROWS, start=1):
        rows.append({
            "id": f"census-usgs-rare-earth-1983-import-{index}",
            "year": 1983,
            "mineral_id": "rare-earth-elements",
            "direction": "imports",
            "category": category,
            "quantity": measure(quantity, quantity_display, "metric tons"),
            "trade_value": measure(value, value_display, "thousand current U.S. dollars"),
            "is_total": category == "Published total",
            "source_id": "usgs-statistical-compendium",
            "source_origin_agency": "Bureau of the Census",
            "publication_title": "Rare Earths Statistical Compendium",
            "table_or_page": "Table 3, U.S. imports for consumption of rare-earths",
            "source_url": IMPORT_URL,
            "access_date": access_date,
            "transcription_status": "manually-reviewed-published-table",
            "classification_note": "The table preserves the contemporaneous published categories. Quantity totals may not add because of independent rounding.",
            "confidence": "high",
        })
    for index, (category, quantity, quantity_display) in enumerate(EXPORT_ROWS, start=1):
        rows.append({
            "id": f"census-usgs-rare-earth-1983-export-{index}",
            "year": 1983,
            "mineral_id": "rare-earth-elements",
            "direction": "exports",
            "category": category,
            "quantity": measure(quantity, quantity_display, "metric tons"),
            "trade_value": measure(None, "Not published in this table", "thousand current U.S. dollars"),
            "is_total": category == "Published total",
            "source_id": "usgs-statistical-compendium",
            "source_origin_agency": "Bureau of the Census",
            "publication_title": "Rare Earths Statistical Compendium",
            "table_or_page": "Table 4, U.S. exports of rare-earths",
            "source_url": EXPORT_URL,
            "access_date": access_date,
            "transcription_status": "manually-reviewed-published-table",
            "classification_note": "The published export total includes thorium ore and concentrates. It is not equivalent to a modern rare-earth-element product total.",
            "confidence": "high",
        })
    return rows


def research_rows() -> list[dict]:
    return [{
        "id": "census-ft-1983-rare-earth-partners",
        "year": 1983,
        "mineral_id": "rare-earth-elements",
        "title": "Recover the 1983 rare-earth country breakdown",
        "status": "source-acquisition",
        "objective": "Transcribe country-of-origin imports and country-of-destination exports without inferring bilateral flows from national totals.",
        "reports": [
            {
                "series": "FT 246",
                "title": "U.S. Imports for Consumption and General Imports, TSUSA Commodity by Country of Origin",
                "role": "Import quantity and value by contemporaneous TSUSA commodity and country of origin",
                "official_description_url": CENSUS_GUIDE_URL,
            },
            {
                "series": "FT 446",
                "title": "U.S. Exports, Schedule B Commodity by Country",
                "role": "Export quantity and value by contemporaneous Schedule B commodity and country of destination",
                "official_description_url": CENSUS_GUIDE_URL,
            },
        ],
        "control_total_ids": [
            "census-usgs-rare-earth-1983-import-9",
            "census-usgs-rare-earth-1983-export-5",
        ],
        "required_fields": [
            "classification system and code",
            "published commodity description",
            "country code and historical country name",
            "quantity and original unit",
            "customs or f.a.s. value basis",
            "report page or table",
            "human-review status",
        ],
        "classification_notes": [
            "Do not map 1983 TSUSA or Schedule B categories directly to current HS codes without a reviewed concordance.",
            "Reconcile country rows to the corresponding published category total, not to the differently standardized Data Series 140 aggregate.",
            "Do not draw atlas trade-flow lines until the partner rows and their units have been reviewed.",
        ],
        "source_ids": ["census-historical-trade", "usgs-statistical-compendium"],
        "official_request_url": CENSUS_REQUEST_URL,
        "completeness": "research-queue",
    }]


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--access-date", default=date.today().isoformat())
    parser.add_argument("--detail-output", type=Path, default=DETAIL_OUTPUT)
    parser.add_argument("--research-output", type=Path, default=RESEARCH_OUTPUT)
    args = parser.parse_args()
    details = detail_rows(args.access_date)
    research = research_rows()
    write(args.detail_output, details)
    write(args.research_output, research)
    print(f"Wrote {len(details)} trade detail rows and {len(research)} research queue")


if __name__ == "__main__":
    main()
