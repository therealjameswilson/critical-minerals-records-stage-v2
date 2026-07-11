#!/usr/bin/env python3
"""Build the source-bounded Historical Geostrategic Atlas pilot.

The atlas derives documentary overlays from the normalized History Stack data.
It does not infer production, route volume, alliance membership, facility
coordinates, or strategic risk. DataWeb partner trade is supported only for
1989-1992 and remains visually distinct from FRUS documentary relationships.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history-stack"
ATLAS = ROOT / "data" / "atlas"
NATURAL_EARTH_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_110m_admin_0_countries.geojson"
)

COUNTRY_A3 = {
    "united-states": "USA",
    "bolivia": "BOL",
    "chile": "CHL",
    "belgian-congo": "COD",
    "northern-rhodesia": "ZMB",
    "south-africa": "ZAF",
    "surinam": "SUR",
    "turkey": "TUR",
    "indonesia": "IDN",
}

LAYER_REGISTRY = [
    {
        "id": "frus-activity",
        "title": "FRUS activity",
        "short_title": "FRUS",
        "availability": "supported",
        "geometry": "country-fill",
        "value_semantics": "Linked pilot FRUS records whose volume span includes the selected year.",
        "source_ids": ["frus-history-at-state", "frus-subject-index"],
        "caveat": "Record count measures indexed documentary coverage, not diplomatic importance or policy intensity.",
    },
    {
        "id": "access-relationships",
        "title": "Documented access relationships",
        "short_title": "Access",
        "availability": "supported",
        "geometry": "relationship-lines",
        "value_semantics": "Lines connect the United States to a country named in a linked negotiation, agreement, or FRUS pathway.",
        "source_ids": ["frus-history-at-state", "frus-subject-index"],
        "caveat": "Line width represents linked pilot records, not shipment volume, import dependence, or strategic importance.",
    },
    {
        "id": "agreements",
        "title": "Treaties and policy instruments",
        "short_title": "Instruments",
        "availability": "supported",
        "geometry": "country-markers",
        "value_semantics": "Dated or FRUS-volume-dated pilot agreements and policy instruments linked to a country.",
        "source_ids": ["frus-history-at-state", "frus-subject-index", "state-treaties"],
        "caveat": "A marker does not imply that the record is a formal treaty. Record type and date precision remain visible.",
    },
    {
        "id": "stockpile-policy",
        "title": "Strategic stockpile policy",
        "short_title": "Stockpile",
        "availability": "supported",
        "geometry": "policy-markers",
        "value_semantics": "Pilot stockpile planning episodes and statutory pathways located at country-level U.S. geography.",
        "source_ids": ["frus-history-at-state", "govinfo-statutes", "gsa-stockpile"],
        "caveat": "Markers represent policy geography, not storage sites, holdings, acquisitions, or releases.",
    },
    {
        "id": "historical-events",
        "title": "Historical episodes",
        "short_title": "Episodes",
        "availability": "supported",
        "geometry": "country-outline",
        "value_semantics": "Countries linked to a pilot historical episode during its documented date range.",
        "source_ids": ["frus-history-at-state", "frus-subject-index", "govinfo-statutes"],
        "caveat": "Episode coverage is selective and does not define the full geography of a war or crisis.",
    },
    {
        "id": "nara-discovery",
        "title": "NARA archival discovery",
        "short_title": "NARA",
        "availability": "supported",
        "geometry": "country-markers",
        "value_semantics": "Structured NARA Catalog query plans that include the selected country, mineral, and year.",
        "source_ids": ["nara-catalog-api"],
        "caveat": "Query plans are archival leads. They are not reviewed catalog results and the site stores no API response content.",
    },
    {
        "id": "resource-geography",
        "title": "Resource geography",
        "short_title": "Resources",
        "availability": "supported",
        "geometry": "country-markers",
        "value_semantics": "Profile context shows a curated country-mineral association; year-linked evidence counts checked-in records connected to the exact selected year.",
        "source_ids": ["frus-history-at-state", "usgs-statistical-compendium"],
        "caveat": "An association is a discovery aid, not proof of production, reserves, mines, supplier rank, or policy importance.",
    },
    {
        "id": "mineral-production",
        "title": "Mineral production",
        "short_title": "Production",
        "availability": "supported",
        "geometry": "country-fill",
        "value_semantics": "Country shading represents published country production for the selected material, year, and supply-chain stage.",
        "source_ids": ["usgs-statistical-compendium"],
        "caveat": "Available for supported 1986-1990 Compendium tables. Production is not a shipment route, U.S. supplier share, ownership record, reserve estimate, or measure of political accessibility.",
    },
    {
        "id": "import-dependence",
        "title": "U.S. import supplier share",
        "short_title": "Import share",
        "availability": "locked",
        "geometry": "country-fill",
        "required_data": "Country, mineral, year, import definition, quantity or value, denominator, unit, classification, and official citation.",
        "source_ids": ["census-historical-trade"],
        "caveat": "No country-supplier share is calculated from the current aggregate import series.",
    },
    {
        "id": "quantitative-trade-flows",
        "title": "Reported U.S. partner trade, 1962-1992",
        "short_title": "Partner trade",
        "availability": "supported",
        "geometry": "country-fill-and-lines",
        "value_semantics": "Country shading and line width represent reported U.S. partner trade within the checked commodity classifications. Coverage uses UN Comtrade for 1962-1992 and USITC DataWeb for 1989-1992.",
        "source_ids": ["un-comtrade", "usitc-dataweb"],
        "caveat": "Partner means the published trade geography, not necessarily mine origin, processing location, ownership, physical route, end use, import dependence, or strategic importance. Country positions are generalized centroids.",
    },
    {
        "id": "supply-chain-evidence",
        "title": "Supply-chain evidence",
        "short_title": "Supply chain",
        "availability": "supported",
        "geometry": "country-fill-and-lines",
        "value_semantics": "USGS country production supplies the stage-specific geography; separately styled lines show reported U.S. imports or partner trade where an exact-year series exists.",
        "source_ids": ["usgs-statistical-compendium", "un-comtrade", "usitc-dataweb"],
        "caveat": "The overlay joins distinct official series without claiming that production moved directly to the United States. It does not infer mine origin, ownership, route, access, or import dependence.",
    },
    {
        "id": "infrastructure",
        "title": "Mines, smelters, ports, and routes",
        "short_title": "Infrastructure",
        "availability": "locked",
        "geometry": "site-and-line-features",
        "required_data": "Feature name, type, active dates, coordinates or geometry, precision, ownership/status where relevant, and official citation.",
        "source_ids": ["nara-catalog-api", "usgs-statistical-compendium"],
        "caveat": "Country centroids are never presented as facility or route coordinates.",
    },
    {
        "id": "alliances-boundaries",
        "title": "Alliances and historical boundaries",
        "short_title": "Alliances",
        "availability": "locked",
        "geometry": "dated-polygons",
        "required_data": "Year-bounded membership and historically reviewed boundary geometry with source and territorial-status notes.",
        "source_ids": ["frus-history-at-state"],
        "caveat": "The orientation basemap uses modern generalized geometry and is not evidence for historical borders or alliance membership.",
    },
    {
        "id": "strategic-risk",
        "title": "Strategic risk",
        "short_title": "Risk",
        "availability": "locked",
        "geometry": "country-fill",
        "required_data": "Published methodology plus sourced supplier concentration, import dependence, substitution, stockpile, and disruption variables for a common year.",
        "source_ids": ["usgs-ds140", "census-historical-trade", "gsa-stockpile"],
        "caveat": "The portal does not convert record counts or editorial judgments into a quantitative vulnerability score.",
    },
]


def load(name: str) -> list[dict]:
    return json.loads((HISTORY / f"{name}.json").read_text(encoding="utf-8"))


def derived_year(record: dict, frus_by_id: dict[str, dict]) -> tuple[int, str]:
    for field in ("signature_date", "entry_into_force_date"):
        if record.get(field):
            return int(record[field][:4]), "document-date"
    spans = [
        frus_by_id[record_id]["volume_year_start"]
        for record_id in record.get("frus_document_ids", [])
        if record_id in frus_by_id
    ]
    if spans:
        return min(spans), "FRUS-volume-context"
    return 1861, "undated-research-queue"


def build_atlas() -> dict:
    countries = load("countries")
    agreements = load("agreements")
    episodes = load("episodes")
    frus = load("frus-documents")
    stockpile = load("stockpile-cases")
    nara = load("nara-queries")
    frus_by_id = {row["id"]: row for row in frus}

    country_features = []
    for country in countries:
        country_features.append(
            {
                "id": country["id"],
                "a3": COUNTRY_A3[country["id"]],
                "coordinates": [country["marker"]["longitude"], country["marker"]["latitude"]],
                "precision": country["marker"]["precision"],
                "names_by_period": country["names_by_period"],
                "mineral_ids": country.get("mineral_ids", []),
                "frus_document_ids": country.get("frus_document_ids", []),
                "agreement_ids": country.get("agreement_ids", []),
                "episode_ids": country.get("episode_ids", []),
                "source_ids": country.get("source_ids", []),
            }
        )

    relationships = []
    instruments = []
    for agreement in agreements:
        year, date_precision = derived_year(agreement, frus_by_id)
        for country_id in agreement.get("country_ids", []):
            if country_id == "united-states":
                continue
            base = {
                "id": f"atlas-{agreement['id']}-{country_id}",
                "title": agreement["official_title"],
                "year": year,
                "date_precision": date_precision,
                "country_id": country_id,
                "mineral_ids": agreement.get("mineral_ids", []),
                "agreement_id": agreement["id"],
                "record_type": agreement["record_type"],
                "frus_document_ids": agreement.get("frus_document_ids", []),
                "source_ids": agreement.get("source_ids", []),
                "completeness": agreement.get("completeness", "research-queue"),
            }
            instruments.append(base)
            relationships.append(
                {
                    **base,
                    "from_country_id": country_id,
                    "to_country_id": "united-states",
                    "line_value": max(1, len(agreement.get("frus_document_ids", []))),
                    "line_value_semantics": "linked pilot FRUS records",
                }
            )

    event_links = []
    for episode in episodes:
        for country_id in episode.get("country_ids", []):
            event_links.append(
                {
                    "id": f"atlas-{episode['id']}-{country_id}",
                    "episode_id": episode["id"],
                    "title": episode["title"],
                    "start": episode["start"],
                    "end": episode["end"],
                    "country_id": country_id,
                    "mineral_ids": episode.get("mineral_ids", []),
                    "frus_document_ids": episode.get("frus_document_ids", []),
                    "source_ids": episode.get("source_ids", []),
                    "completeness": episode.get("completeness", "research-queue"),
                }
            )

    stockpile_links = [
        {
            "id": f"atlas-{row['id']}",
            "stockpile_case_id": row["id"],
            "title": row["title"],
            "start": row["start"],
            "end": row["end"],
            "country_id": "united-states",
            "mineral_ids": row.get("mineral_ids", []),
            "frus_document_ids": row.get("frus_document_ids", []),
            "law_ids": row.get("law_ids", []),
            "source_ids": row.get("source_ids", []),
            "precision": "country-policy",
            "completeness": row.get("completeness", "research-queue"),
        }
        for row in stockpile
    ]

    archival_plans = [
        {
            "id": row["id"],
            "title": row["label"],
            "query": row["query"],
            "record_groups": row["record_groups"],
            "start": row["date_start"],
            "end": row["date_end"],
            "country_ids": row.get("country_ids", []),
            "mineral_ids": row.get("mineral_ids", []),
            "source_ids": row.get("source_ids", []),
            "result_status": row["result_status"],
        }
        for row in nara
    ]

    return {
        "meta": {
            "title": "Historical Geostrategic Atlas pilot",
            "historical_start": 1861,
            "historical_end": 1992,
            "default_year": 1942,
            "default_mineral": "tin",
            "orientation_geometry": "Natural Earth 1:110m modern generalized country geometry",
            "orientation_url": "https://www.naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/",
            "orientation_license": "Public domain",
            "orientation_caveat": "Modern generalized geometry is used only for spatial orientation. Historical names and status come from dated project records; historical borders are not yet reconstructed.",
        },
        "layers": LAYER_REGISTRY,
        "countries": country_features,
        "relationships": relationships,
        "instruments": instruments,
        "events": event_links,
        "stockpile_policy": stockpile_links,
        "archival_plans": archival_plans,
    }


def build_orientation_geometry() -> None:
    request = urllib.request.Request(NATURAL_EARTH_URL, headers={"User-Agent": "critical-minerals-atlas-builder/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    compact = {
        "type": "FeatureCollection",
        "name": "Natural Earth 1:110m modern orientation geometry",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    key: feature.get("properties", {}).get(key)
                    for key in ("ADMIN", "ADM0_A3", "SOVEREIGNT", "TYPE", "NAME_LONG")
                },
                "geometry": feature["geometry"],
            }
            for feature in payload["features"]
        ],
    }
    (ATLAS / "world-orientation.geojson").write_text(
        json.dumps(compact, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-basemap", action="store_true", help="Keep the existing checked-in orientation geometry")
    args = parser.parse_args()
    ATLAS.mkdir(parents=True, exist_ok=True)
    (ATLAS / "atlas.json").write_text(
        json.dumps(build_atlas(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if not args.skip_basemap:
        build_orientation_geometry()
    print(f"Wrote {ATLAS / 'atlas.json'}")
    if not args.skip_basemap:
        print(f"Wrote {ATLAS / 'world-orientation.geojson'}")


if __name__ == "__main__":
    main()
