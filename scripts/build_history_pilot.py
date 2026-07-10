#!/usr/bin/env python3
"""Build the normalized, source-bounded 1861-1992 History Stack pilot.

FRUS discovery records are derived from the checked-in FRUS Subjects index.
Only records explicitly reviewed against HistoryAtState receive document-level
titles, dates, and summaries. All other FRUS rows remain clearly marked
subject-index leads and retain only volume-level navigation context.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from country_brief_data import COUNTRY_BRIEFS, COUNTRY_BRIEF_SOURCES


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "history-stack"
FRUS_INDEX = ROOT / "assets" / "frus-subjects-index.js"


def write(name: str, value: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f"{name}.json").write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def frus_id(volume: str, document: str) -> str:
    volume_id = re.sub(r"[^a-z0-9]+", "-", volume.removeprefix("frus").lower()).strip("-")
    return f"frus-{volume_id}-{document.lower()}"


SOURCES = [
    {
        "id": "frus-history-at-state",
        "label": "Foreign Relations of the United States",
        "agency": "U.S. Department of State, Office of the Historian",
        "source_type": "FRUS",
        "tier": 1,
        "url": "https://history.state.gov/historicaldocuments",
        "scope": "Selected and edited documentary record of major U.S. foreign-policy decisions and activity.",
        "trust_note": "FRUS is the narrative spine, but it is not the complete archival record."
    },
    {
        "id": "frus-subject-index",
        "label": "FRUS Subjects discovery index",
        "agency": "Community-maintained index derived from HistoryAtState metadata",
        "source_type": "discovery-index",
        "tier": 2,
        "url": "https://github.com/therealjameswilson/frus-subjects",
        "scope": "Subject-authority and table-of-contents mappings for FRUS discovery.",
        "trust_note": "A subject assignment is a lead, not proof that a document is centrally about a resource."
    },
    {
        "id": "usgs-ds140",
        "label": "Historical Statistics for Mineral and Material Commodities in the United States, Data Series 140",
        "agency": "U.S. Geological Survey",
        "source_type": "official-statistics",
        "tier": 1,
        "url": "https://www.usgs.gov/centers/national-minerals-information-center/historical-statistics-mineral-commodities-united",
        "scope": "Long-run U.S. mineral production, trade, consumption, stocks, prices, and world-production series.",
        "trust_note": "The pilot reproduces numeric XLSX cells, original USGS units, and worksheet locations; missing values are not converted to zero."
    },
    {
        "id": "usgs-statistical-compendium",
        "label": "Metal Prices in the United States Through 1991 and Statistical Compendium",
        "agency": "U.S. Geological Survey and predecessor Bureau of Mines",
        "source_type": "official-publication",
        "tier": 1,
        "url": "https://www.usgs.gov/centers/national-minerals-information-center/statistical-compendium",
        "scope": "Official commodity chapters and historical statistical context through 1990.",
        "trust_note": "Commodity uses in the pilot are high-level orientation; page-level extraction remains a research task."
    },
    {
        "id": "usgs-circular-1141",
        "label": "Uranium: Its Impact on the National and Global Energy Mix",
        "agency": "U.S. Geological Survey",
        "source_type": "official-publication",
        "tier": 1,
        "url": "https://pubs.usgs.gov/circ/1997/1141/report.pdf",
        "scope": "Official historical context and world uranium production coverage through 1992.",
        "trust_note": "The uranium profile links this publication for context; its tables have not yet been normalized into the portal statistics dataset."
    },
    {
        "id": "nara-catalog-api",
        "label": "National Archives Catalog API",
        "agency": "National Archives and Records Administration",
        "source_type": "archival-catalog",
        "tier": 1,
        "url": "https://catalog.archives.gov/api/v2/",
        "scope": "Archival descriptions and links to digitized records or broader series-level holdings.",
        "trust_note": "Catalog matches require relevance review. The project does not store API response content."
    },
    {
        "id": "govinfo-statutes",
        "label": "United States Code Compilation and Statutes at Large",
        "agency": "U.S. Government Publishing Office",
        "source_type": "law",
        "tier": 1,
        "url": "https://www.govinfo.gov/app/collection/COMPS",
        "scope": "Official compilations and statutory citations for stockpile and production authorities.",
        "trust_note": "The official text controls; project summaries are orientation only."
    },
    {
        "id": "state-treaties",
        "label": "Treaties and Other International Acts Series",
        "agency": "U.S. Department of State",
        "source_type": "treaty-publication",
        "tier": 1,
        "url": "https://www.state.gov/treaties-in-force/",
        "scope": "Official treaty and international-agreement publication context.",
        "trust_note": "Pilot purchasing and negotiation records are not labeled formal treaties unless a treaty citation is verified."
    },
    {
        "id": "census-historical-trade",
        "label": "Historical Foreign Trade Statistics",
        "agency": "U.S. Census Bureau",
        "source_type": "official-statistics",
        "tier": 1,
        "url": "https://www.census.gov/foreign-trade/statistics/historical/",
        "scope": "Historical import and export publications, commodity classifications, and country-partner tables.",
        "trust_note": "The pilot includes reviewed Census-derived national category totals. Country rows remain a source-acquisition queue until the relevant FT reports are obtained and checked."
    },
    {
        "id": "census-statistical-abstract-1948",
        "label": "Statistical Abstract of the United States: 1948, Foreign Commerce tables 1013-1014",
        "agency": "U.S. Department of Commerce, Bureau of the Census",
        "source_type": "official-statistics",
        "tier": 1,
        "url": "https://www2.census.gov/library/publications/1948/compendia/statab/69ed/1948-12.pdf",
        "scope": "Published values and percent distributions of U.S. exports and imports by broad economic class, including crude materials.",
        "trust_note": "The 1861-1900 rows are published multi-year averages for a broad economic class. They are not mineral-specific, bilateral, or annual observations."
    },
    {
        "id": "gsa-stockpile",
        "label": "National Defense Stockpile historical records",
        "agency": "General Services Administration and successor agencies",
        "source_type": "stockpile-record",
        "tier": 1,
        "url": "https://www.dla.mil/Strategic-Materials/",
        "scope": "Official orientation for the stockpile program and its institutional successors.",
        "trust_note": "Historical holdings and goals require report- or statute-level citations; they are not inferred here."
    }
] + COUNTRY_BRIEF_SOURCES


MINERALS = [
    {
        "id": "aluminum", "canonical_name": "Aluminum", "alternate_names": ["aluminium"], "chemical_symbol": "Al",
        "category": "light metal", "historical_scope": {"start": 1900, "end": 1992},
        "strategic_uses": [{"period": "twentieth century", "use": "Transportation, electrical, construction, packaging, and defense applications are documented in official commodity histories.", "source_ids": ["usgs-statistical-compendium"]}],
        "military_uses_by_period": [], "industrial_uses_by_period": [], "substitutes": [],
        "country_ids": ["united-states", "surinam"],
        "frus_document_ids": [frus_id("frus1941v02", "d805"), frus_id("frus1941v02", "d821"), frus_id("frus1950v01", "d95")],
        "agreement_ids": ["surinam-bauxite-protection-1941"], "law_ids": ["defense-production-act-1950"],
        "episode_ids": ["world-war-ii-procurement", "early-cold-war-mobilization"],
        "source_ids": ["frus-history-at-state", "usgs-ds140", "usgs-statistical-compendium"], "completeness": "partial",
        "data_gaps": ["Bauxite-to-alumina-to-aluminum conversion relationships are not yet modeled.", "Stockpile holdings need report-level transcription."]
    },
    {
        "id": "bauxite", "canonical_name": "Bauxite", "alternate_names": ["aluminum ore", "aluminium ore"], "chemical_symbol": None,
        "category": "ore and industrial mineral", "historical_scope": {"start": 1900, "end": 1992},
        "strategic_uses": [{"period": "World War II", "use": "Raw material for alumina and aluminum; FRUS indexes a 1941 chapter on protection of Surinam bauxite mines.", "source_ids": ["frus-history-at-state", "frus-subject-index"]}],
        "military_uses_by_period": [], "industrial_uses_by_period": [], "substitutes": [],
        "country_ids": ["surinam", "united-states"],
        "frus_document_ids": [frus_id("frus1941v02", "d805"), frus_id("frus1941v02", "d821")],
        "agreement_ids": ["surinam-bauxite-protection-1941"], "law_ids": [], "episode_ids": ["world-war-ii-procurement"],
        "source_ids": ["frus-history-at-state", "frus-subject-index", "usgs-ds140"], "completeness": "partial",
        "data_gaps": ["Country production and shipping-route series are not yet transcribed."]
    },
    {
        "id": "chromium", "canonical_name": "Chromium", "alternate_names": ["chrome", "chromite"], "chemical_symbol": "Cr",
        "category": "ferroalloy metal", "historical_scope": {"start": 1900, "end": 1992},
        "strategic_uses": [{"period": "World War II", "use": "FRUS indexes U.S.-British efforts to acquire Turkish chrome and prevent sales to Germany.", "source_ids": ["frus-history-at-state", "frus-subject-index"]}],
        "military_uses_by_period": [], "industrial_uses_by_period": [], "substitutes": [],
        "country_ids": ["turkey", "south-africa", "united-states"],
        "frus_document_ids": [frus_id("frus1941v03", "d1006"), frus_id("frus1941v03", "d1038"), frus_id("frus1947v01", "d395"), frus_id("frus1950v01", "d95"), frus_id("frus1964-68v09", "d344")],
        "agreement_ids": ["turkish-chrome-negotiations-1941", "erp-strategic-materials-provisions-1947", "stockpile-objectives-review-1967"],
        "law_ids": ["stock-piling-act-1946", "defense-production-act-1950", "stock-piling-revision-act-1979"],
        "episode_ids": ["world-war-ii-procurement", "early-cold-war-mobilization", "late-cold-war-resource-policy"],
        "source_ids": ["frus-history-at-state", "frus-subject-index", "usgs-ds140"], "completeness": "partial",
        "data_gaps": ["Historical country-level chromite series and Rhodesian sanctions evidence remain to be added."]
    },
    {
        "id": "cobalt", "canonical_name": "Cobalt", "alternate_names": [], "chemical_symbol": "Co",
        "category": "alloy and battery metal", "historical_scope": {"start": 1900, "end": 1992},
        "strategic_uses": [{"period": "early Cold War", "use": "Reviewed FRUS records identify cobalt among strategic African raw materials and in U.S. stockpile planning.", "source_ids": ["frus-history-at-state"]}],
        "military_uses_by_period": [], "industrial_uses_by_period": [], "substitutes": [],
        "country_ids": ["belgian-congo", "northern-rhodesia", "south-africa", "united-states"],
        "frus_document_ids": [frus_id("frus1942v02", "d3"), frus_id("frus1942v02", "d14"), frus_id("frus1947v01", "d395"), frus_id("frus1952-54v11p1", "d27"), frus_id("frus1964-68v09", "d344")],
        "agreement_ids": ["congo-tripartite-trade-negotiations-1942", "erp-strategic-materials-provisions-1947", "stockpile-objectives-review-1967"],
        "law_ids": ["stock-piling-act-1946", "defense-production-act-1950"],
        "episode_ids": ["world-war-ii-procurement", "early-cold-war-mobilization", "decolonization-and-resource-access"],
        "source_ids": ["frus-history-at-state", "usgs-ds140", "usgs-statistical-compendium"], "completeness": "partial",
        "data_gaps": ["Mine-level ownership, refining routes, and country production remain research queues."]
    },
    {
        "id": "copper", "canonical_name": "Copper", "alternate_names": [], "chemical_symbol": "Cu",
        "category": "base metal", "historical_scope": {"start": 1900, "end": 1992},
        "strategic_uses": [{"period": "twentieth century", "use": "Official commodity histories document broad electrical and industrial uses; FRUS records connect copper to wartime shipments, stockpiles, and African resource assessments.", "source_ids": ["usgs-statistical-compendium", "frus-history-at-state"]}],
        "military_uses_by_period": [], "industrial_uses_by_period": [], "substitutes": [],
        "country_ids": ["bolivia", "chile", "belgian-congo", "northern-rhodesia", "united-states"],
        "frus_document_ids": [frus_id("frus1914Supp", "d423"), frus_id("frus1914Supp", "d427"), frus_id("frus1942v05", "d493"), frus_id("frus1952-54v11p1", "d27"), frus_id("frus1964-68v09", "d344")],
        "agreement_ids": ["copper-shipment-correspondence-1914", "bolivian-strategic-materials-purchase-1942", "stockpile-objectives-review-1967"],
        "law_ids": ["defense-production-act-1950"],
        "episode_ids": ["world-war-i-resource-access", "world-war-ii-procurement", "decolonization-and-resource-access"],
        "source_ids": ["frus-history-at-state", "frus-subject-index", "usgs-ds140", "usgs-statistical-compendium"], "completeness": "partial",
        "data_gaps": ["Chilean nationalization and U.S. import-source series are not yet populated."]
    },
    {
        "id": "manganese", "canonical_name": "Manganese", "alternate_names": ["manganese ore"], "chemical_symbol": "Mn",
        "category": "ferroalloy metal", "historical_scope": {"start": 1900, "end": 1992},
        "strategic_uses": [{"period": "twentieth century", "use": "Reviewed FRUS records list manganese among strategic materials considered in African-resource and stockpile planning.", "source_ids": ["frus-history-at-state"]}],
        "military_uses_by_period": [], "industrial_uses_by_period": [], "substitutes": [],
        "country_ids": ["south-africa", "united-states"],
        "frus_document_ids": [frus_id("frus1947v01", "d395"), frus_id("frus1950v01", "d95"), frus_id("frus1952-54v11p1", "d27"), frus_id("frus1964-68v09", "d344")],
        "agreement_ids": ["erp-strategic-materials-provisions-1947", "nsc68-materials-program-1950", "stockpile-objectives-review-1967"],
        "law_ids": ["stock-piling-act-1946", "defense-production-act-1950"],
        "episode_ids": ["early-cold-war-mobilization", "decolonization-and-resource-access"],
        "source_ids": ["frus-history-at-state", "usgs-ds140"], "completeness": "partial",
        "data_gaps": ["World War I import dependence and supplier-country statistics remain to be added."]
    },
    {
        "id": "rare-earth-elements", "canonical_name": "Rare earth elements", "alternate_names": ["rare earths", "rare-earth elements", "REE", "monazite"], "chemical_symbol": "REE",
        "category": "mineral group", "historical_scope": {"start": 1900, "end": 1992},
        "strategic_uses": [{"period": "twentieth century", "use": "The official USGS historical series provides production, trade, consumption, price, and world-production context in rare-earth-oxide equivalent. No reviewed FRUS document has yet been linked to this profile.", "source_ids": ["usgs-ds140"]}],
        "military_uses_by_period": [], "industrial_uses_by_period": [], "substitutes": [],
        "country_ids": ["united-states"], "frus_document_ids": [], "agreement_ids": [], "law_ids": [], "episode_ids": [],
        "source_ids": ["usgs-ds140"], "completeness": "partial",
        "data_gaps": ["FRUS terminology and document pathways require review; modern rare-earth categories are not projected backward without evidence.", "Country-level extraction, processing, and supplier-share series remain to be added."]
    },
    {
        "id": "tin", "canonical_name": "Tin", "alternate_names": [], "chemical_symbol": "Sn",
        "category": "base and strategic metal", "historical_scope": {"start": 1900, "end": 1992},
        "strategic_uses": [{"period": "World War II", "use": "FRUS indexes strategic-material purchasing from Bolivia and an international tin-control agreement; USGS provides a long-run quantitative series.", "source_ids": ["frus-history-at-state", "frus-subject-index", "usgs-ds140"]}],
        "military_uses_by_period": [], "industrial_uses_by_period": [], "substitutes": [],
        "country_ids": ["bolivia", "belgian-congo", "united-states"],
        "frus_document_ids": [frus_id("frus1942v01", "d440"), frus_id("frus1942v05", "d493"), frus_id("frus1942v05", "d564"), frus_id("frus1947v01", "d395"), frus_id("frus1950v01", "d95"), frus_id("frus1952-54v11p1", "d27"), frus_id("frus1964-68v09", "d344")],
        "agreement_ids": ["international-tin-control-agreement-1942", "bolivian-strategic-materials-purchase-1942", "us-bolivia-economic-cooperation-1942", "stockpile-objectives-review-1967"],
        "law_ids": ["stock-piling-act-1946", "defense-production-act-1950"],
        "episode_ids": ["world-war-ii-procurement", "early-cold-war-mobilization"],
        "source_ids": ["frus-history-at-state", "frus-subject-index", "usgs-ds140", "usgs-statistical-compendium"], "completeness": "verified-pilot",
        "data_gaps": ["Bolivia's share of U.S. imports and route-level shipping data require additional official tables."]
    },
    {
        "id": "tungsten", "canonical_name": "Tungsten", "alternate_names": ["wolfram", "wolframite", "scheelite"], "chemical_symbol": "W",
        "category": "refractory and alloy metal", "historical_scope": {"start": 1900, "end": 1992},
        "strategic_uses": [{"period": "early Cold War", "use": "Reviewed FRUS stockpile records list tungsten among strategic materials assessed for foreign access and reserve requirements.", "source_ids": ["frus-history-at-state"]}],
        "military_uses_by_period": [], "industrial_uses_by_period": [], "substitutes": [],
        "country_ids": ["bolivia", "united-states"],
        "frus_document_ids": [frus_id("frus1942v05", "d493"), frus_id("frus1947v01", "d395"), frus_id("frus1950v01", "d95"), frus_id("frus1964-68v09", "d344")],
        "agreement_ids": ["bolivian-strategic-materials-purchase-1942", "erp-strategic-materials-provisions-1947", "stockpile-objectives-review-1967"],
        "law_ids": ["stock-piling-act-1946", "defense-production-act-1950"],
        "episode_ids": ["world-war-ii-procurement", "early-cold-war-mobilization"],
        "source_ids": ["frus-history-at-state", "usgs-ds140"], "completeness": "partial",
        "data_gaps": ["Supplier-country and price-contract histories remain to be linked."]
    },
    {
        "id": "uranium", "canonical_name": "Uranium", "alternate_names": ["uranium ore", "uranium oxide", "radioactive ores"], "chemical_symbol": "U",
        "category": "nuclear fuel and strategic material", "historical_scope": {"start": 1944, "end": 1992},
        "strategic_uses": [{"period": "World War II and early Cold War", "use": "Reviewed FRUS records document allied control, contracted delivery, mine redevelopment, first-refusal rights, production expansion, technical assistance, and bargaining over Congo uranium.", "source_ids": ["frus-history-at-state"]}],
        "military_uses_by_period": [], "industrial_uses_by_period": [], "substitutes": [],
        "country_ids": ["belgian-congo", "united-states"],
        "frus_document_ids": [frus_id("frus1944v02", "d886"), frus_id("frus1947v01", "d431"), frus_id("frus1949v01", "d204"), frus_id("frus1950v01", "d167"), frus_id("frus1950v01", "d200"), frus_id("frus1951v01", "d242")],
        "agreement_ids": ["us-uk-uranium-acquisition-1944", "tripartite-uranium-control-1944"], "law_ids": [],
        "episode_ids": ["world-war-ii-procurement", "early-cold-war-mobilization"],
        "source_ids": ["frus-history-at-state", "usgs-circular-1141"], "completeness": "verified-pilot",
        "data_gaps": ["Country production, price, contract-delivery, processing, and import-dependence series are not yet normalized.", "Atomic Energy Commission and additional supplier-country records require expansion beyond this Congo-centered pilot."]
    }
]


PILOT_FRUS_KEYS = [
    ("frus1914Supp", "d423"), ("frus1914Supp", "d427"),
    ("frus1925v02", "d327"), ("frus1925v02", "d344"),
    ("frus1939v01", "d934"), ("frus1939v01", "d939"),
    ("frus1941v02", "d805"), ("frus1941v02", "d821"),
    ("frus1941v03", "d1006"), ("frus1941v03", "d1038"),
    ("frus1942v02", "d3"), ("frus1942v02", "d14"),
    ("frus1942v05", "d493"), ("frus1942v01", "d440"),
    ("frus1942v05", "d564"), ("frus1944v02", "d886"),
    ("frus1947v01", "d395"), ("frus1947v01", "d431"),
    ("frus1949v01", "d204"), ("frus1950v01", "d95"),
    ("frus1950v01", "d167"), ("frus1950v01", "d200"),
    ("frus1951v01", "d242"),
    ("frus1952-54v11p1", "d27"), ("frus1964-68v09", "d344"),
    ("frus1969-76v21", "d250"), ("frus1969-76v21", "d256"),
    ("frus1969-76v21", "d261"), ("frus1969-76ve16", "d87"),
    ("frus1964-68v26", "d138"), ("frus1964-68v26", "d142"),
    ("frus1964-68v26", "d148")
]


COUNTRIES = [
    {
        "id": "united-states", "canonical_historical_name": "United States", "present_day_name": "United States",
        "alternate_historical_names": [], "names_by_period": [{"name": "United States", "start": 1861, "end": 1992}],
        "sovereignty_changes": [], "mineral_ids": [item["id"] for item in MINERALS],
        "frus_document_ids": [frus_id(volume, document) for volume, document in PILOT_FRUS_KEYS], "agreement_ids": [], "episode_ids": ["world-war-i-resource-access", "interwar-planning", "world-war-ii-procurement", "early-cold-war-mobilization", "decolonization-and-resource-access", "late-cold-war-resource-policy"],
        "ports": [], "mines": [], "smelters": [], "rail_corridors": [],
        "marker": {"latitude": 38.0, "longitude": -97.0, "precision": "country"},
        "source_ids": ["frus-history-at-state", "usgs-ds140"], "completeness": "partial",
        "data_gaps": ["Map marker is a country centroid, not a facility location."]
    },
    {
        "id": "bolivia", "canonical_historical_name": "Bolivia", "present_day_name": "Bolivia",
        "alternate_historical_names": ["Republic of Bolivia"], "names_by_period": [{"name": "Bolivia", "start": 1861, "end": 1992}],
        "sovereignty_changes": [], "mineral_ids": ["tin", "tungsten", "copper"],
        "frus_document_ids": [frus_id("frus1942v05", "d493"), frus_id("frus1942v05", "d564")],
        "agreement_ids": ["bolivian-strategic-materials-purchase-1942", "us-bolivia-economic-cooperation-1942"], "episode_ids": ["world-war-ii-procurement"],
        "ports": [], "mines": [], "smelters": [], "rail_corridors": [],
        "marker": {"latitude": -16.3, "longitude": -63.6, "precision": "country"},
        "source_ids": ["frus-history-at-state", "frus-subject-index"], "completeness": "verified-pilot",
        "data_gaps": ["Mine, rail, smelter, and port links have not been verified for display.", "Partner objectives require document-level annotation."]
    },
    {
        "id": "chile", "canonical_historical_name": "Chile", "present_day_name": "Chile",
        "alternate_historical_names": ["Republic of Chile"], "names_by_period": [{"name": "Chile", "start": 1861, "end": 1992}],
        "sovereignty_changes": [], "mineral_ids": ["copper"],
        "frus_document_ids": [frus_id("frus1969-76v21", "d250"), frus_id("frus1969-76v21", "d256"), frus_id("frus1969-76v21", "d261"), frus_id("frus1969-76ve16", "d87")],
        "agreement_ids": ["chile-copper-compensation-1971"],
        "episode_ids": ["chile-copper-nationalization-1971", "decolonization-and-resource-access", "late-cold-war-resource-policy"],
        "ports": [], "mines": [], "smelters": [], "rail_corridors": [],
        "marker": {"latitude": -33.4, "longitude": -70.7, "precision": "country"},
        "source_ids": ["frus-history-at-state", "state-country-guide-chile", "usgs-ds140"], "completeness": "verified-pilot",
        "data_gaps": ["Country production, bilateral trade, supplier share, and export-price series remain untranscribed."]
    },
    {
        "id": "belgian-congo", "canonical_historical_name": "Belgian Congo", "present_day_name": "Democratic Republic of the Congo",
        "alternate_historical_names": ["Congo (Leopoldville)", "Republic of the Congo", "Zaire", "Democratic Republic of the Congo"],
        "names_by_period": [{"name": "Belgian Congo", "start": 1908, "end": 1960}, {"name": "Republic of the Congo (Leopoldville)", "start": 1960, "end": 1964}, {"name": "Democratic Republic of the Congo", "start": 1964, "end": 1971}, {"name": "Zaire", "start": 1971, "end": 1992}],
        "sovereignty_changes": [{"year": 1960, "note": "Independence from Belgium; subsequent names are preserved by period."}],
        "mineral_ids": ["cobalt", "copper", "tin", "uranium"],
        "frus_document_ids": [frus_id("frus1942v02", "d3"), frus_id("frus1942v02", "d14"), frus_id("frus1944v02", "d886"), frus_id("frus1947v01", "d431"), frus_id("frus1949v01", "d204"), frus_id("frus1950v01", "d167"), frus_id("frus1950v01", "d200"), frus_id("frus1951v01", "d242"), frus_id("frus1952-54v11p1", "d27")],
        "agreement_ids": ["congo-tripartite-trade-negotiations-1942", "tripartite-uranium-control-1944"],
        "episode_ids": ["world-war-ii-procurement", "early-cold-war-mobilization", "decolonization-and-resource-access"],
        "ports": [], "mines": [], "smelters": [], "rail_corridors": [],
        "marker": {"latitude": -2.9, "longitude": 23.7, "precision": "country"},
        "source_ids": ["frus-history-at-state", "frus-subject-index"], "completeness": "partial",
        "data_gaps": ["Precise mine and transport coordinates are withheld until source verification.", "The 1960-1992 name chronology is simplified for orientation and should be expanded with jurisdiction-level detail."]
    },
    {
        "id": "northern-rhodesia", "canonical_historical_name": "Northern Rhodesia", "present_day_name": "Zambia",
        "alternate_historical_names": ["Zambia"],
        "names_by_period": [{"name": "Northern Rhodesia", "start": 1924, "end": 1964}, {"name": "Zambia", "start": 1964, "end": 1992}],
        "sovereignty_changes": [{"year": 1964, "note": "Independence as Zambia."}], "mineral_ids": ["cobalt", "copper"],
        "frus_document_ids": [frus_id("frus1952-54v11p1", "d27")], "agreement_ids": [], "episode_ids": ["decolonization-and-resource-access"],
        "ports": [], "mines": [], "smelters": [], "rail_corridors": [],
        "marker": {"latitude": -13.1, "longitude": 27.8, "precision": "country"},
        "source_ids": ["frus-history-at-state"], "completeness": "research-queue",
        "data_gaps": ["Copperbelt mines, rail corridors, and country statistics need official-source verification."]
    },
    {
        "id": "south-africa", "canonical_historical_name": "Union of South Africa", "present_day_name": "South Africa",
        "alternate_historical_names": ["Republic of South Africa", "South Africa"],
        "names_by_period": [{"name": "Union of South Africa", "start": 1910, "end": 1961}, {"name": "Republic of South Africa", "start": 1961, "end": 1992}],
        "sovereignty_changes": [{"year": 1961, "note": "The Union became a republic."}], "mineral_ids": ["chromium", "cobalt", "manganese"],
        "frus_document_ids": [frus_id("frus1952-54v11p1", "d27")], "agreement_ids": [],
        "episode_ids": ["early-cold-war-mobilization", "decolonization-and-resource-access", "late-cold-war-resource-policy"],
        "ports": [], "mines": [], "smelters": [], "rail_corridors": [],
        "marker": {"latitude": -30.6, "longitude": 22.9, "precision": "country"},
        "source_ids": ["frus-history-at-state"], "completeness": "research-queue",
        "data_gaps": ["Sanctions, production, transport, and supplier-share evidence require dedicated review."]
    },
    {
        "id": "surinam", "canonical_historical_name": "Surinam", "present_day_name": "Suriname",
        "alternate_historical_names": ["Dutch Guiana", "Suriname"],
        "names_by_period": [{"name": "Surinam (Dutch Guiana)", "start": 1861, "end": 1954}, {"name": "Surinam", "start": 1954, "end": 1975}, {"name": "Suriname", "start": 1975, "end": 1992}],
        "sovereignty_changes": [{"year": 1975, "note": "Independence from the Netherlands as Suriname."}], "mineral_ids": ["bauxite", "aluminum"],
        "frus_document_ids": [frus_id("frus1941v02", "d805"), frus_id("frus1941v02", "d821")],
        "agreement_ids": ["surinam-bauxite-protection-1941"], "episode_ids": ["world-war-ii-procurement"],
        "ports": [], "mines": [], "smelters": [], "rail_corridors": [],
        "marker": {"latitude": 4.1, "longitude": -56.0, "precision": "country"},
        "source_ids": ["frus-history-at-state", "frus-subject-index"], "completeness": "partial",
        "data_gaps": ["Mine and shipping-route data are not yet verified."]
    },
    {
        "id": "turkey", "canonical_historical_name": "Turkey", "present_day_name": "Turkiye",
        "alternate_historical_names": ["Republic of Turkey", "Turkiye"],
        "names_by_period": [{"name": "Ottoman Empire", "start": 1861, "end": 1922}, {"name": "Republic of Turkey", "start": 1923, "end": 1992}],
        "sovereignty_changes": [{"year": 1923, "note": "Republic proclaimed after the end of the Ottoman Empire."}], "mineral_ids": ["chromium"],
        "frus_document_ids": [frus_id("frus1941v03", "d1006"), frus_id("frus1941v03", "d1038")],
        "agreement_ids": ["turkish-chrome-negotiations-1941"], "episode_ids": ["world-war-ii-procurement"],
        "ports": [], "mines": [], "smelters": [], "rail_corridors": [],
        "marker": {"latitude": 39.0, "longitude": 35.2, "precision": "country"},
        "source_ids": ["frus-history-at-state", "frus-subject-index"], "completeness": "partial",
        "data_gaps": ["Mine, contract, and shipment details require document-level review."]
    },
    {
        "id": "indonesia", "canonical_historical_name": "Republic of Indonesia", "present_day_name": "Indonesia",
        "alternate_historical_names": ["Netherlands East Indies", "Republic of the United States of Indonesia", "Indonesia"],
        "names_by_period": [{"name": "Netherlands East Indies", "start": 1861, "end": 1948}, {"name": "Republic of the United States of Indonesia", "start": 1949, "end": 1949}, {"name": "Republic of Indonesia", "start": 1950, "end": 1992}],
        "sovereignty_changes": [{"year": 1949, "note": "The United States recognized Indonesian independence and established diplomatic relations on December 28, 1949."}],
        "mineral_ids": ["tin", "bauxite", "copper"],
        "frus_document_ids": [frus_id("frus1964-68v26", "d138"), frus_id("frus1964-68v26", "d142"), frus_id("frus1964-68v26", "d148")],
        "agreement_ids": [], "episode_ids": ["indonesia-political-crisis-1965"],
        "ports": [], "mines": [], "smelters": [], "rail_corridors": [],
        "marker": {"latitude": -2.5, "longitude": 118.0, "precision": "country"},
        "source_ids": ["frus-history-at-state", "state-country-guide-indonesia", "loc-indonesia-mineral-regulation"], "completeness": "partial",
        "data_gaps": ["The mineral classification is post-1965 context; exact-year production, trade, dependence, reserves, and facility evidence remain unknown."]
    }
]


EPISODES = [
    {
        "id": "world-war-i-resource-access", "title": "World War I resource access", "start": 1914, "end": 1918,
        "summary": "FRUS discovery records expose wartime diplomatic correspondence concerning copper shipments; broader material dependence remains a research queue.",
        "mineral_ids": ["copper"], "country_ids": ["united-states"],
        "frus_document_ids": [frus_id("frus1914Supp", "d423"), frus_id("frus1914Supp", "d427")],
        "agreement_ids": ["copper-shipment-correspondence-1914"], "law_ids": [], "source_ids": ["frus-history-at-state", "frus-subject-index"],
        "outcome": None, "completeness": "research-queue"
    },
    {
        "id": "interwar-planning", "title": "Interwar concessions and stockpile planning", "start": 1925, "end": 1939,
        "summary": "The pilot links FRUS pathways on a rubber concession and on formal planning for strategic-raw-material stockpiles.",
        "mineral_ids": [], "country_ids": ["united-states"],
        "frus_document_ids": [frus_id("frus1925v02", "d327"), frus_id("frus1925v02", "d344"), frus_id("frus1939v01", "d934"), frus_id("frus1939v01", "d939")],
        "agreement_ids": ["firestone-rubber-concession-negotiations-1925", "strategic-stockpile-planning-1939"],
        "law_ids": [], "source_ids": ["frus-history-at-state", "frus-subject-index"], "outcome": None, "completeness": "partial"
    },
    {
        "id": "world-war-ii-procurement", "title": "World War II procurement and access", "start": 1941, "end": 1945,
        "summary": "FRUS pathways connect resource access to purchasing, allied coordination, mine protection, trade control, and uranium agreements.",
        "mineral_ids": ["aluminum", "bauxite", "chromium", "cobalt", "copper", "tin", "tungsten", "uranium"],
        "country_ids": ["bolivia", "belgian-congo", "surinam", "turkey", "united-states"],
        "frus_document_ids": [frus_id("frus1941v02", "d805"), frus_id("frus1941v02", "d821"), frus_id("frus1941v03", "d1006"), frus_id("frus1941v03", "d1038"), frus_id("frus1942v01", "d440"), frus_id("frus1942v02", "d3"), frus_id("frus1942v02", "d14"), frus_id("frus1942v05", "d493"), frus_id("frus1942v05", "d564"), frus_id("frus1944v02", "d886")],
        "agreement_ids": ["surinam-bauxite-protection-1941", "turkish-chrome-negotiations-1941", "international-tin-control-agreement-1942", "congo-tripartite-trade-negotiations-1942", "bolivian-strategic-materials-purchase-1942", "us-bolivia-economic-cooperation-1942", "us-uk-uranium-acquisition-1944", "tripartite-uranium-control-1944"],
        "law_ids": [], "source_ids": ["frus-history-at-state", "frus-subject-index", "usgs-ds140"], "outcome": None, "completeness": "verified-pilot"
    },
    {
        "id": "early-cold-war-mobilization", "title": "Early Cold War mobilization and permanent stockpiling", "start": 1946, "end": 1960,
        "summary": "Reviewed FRUS records connect foreign-source assumptions, economic recovery, African raw materials, uranium diplomacy, and stockpile requirements.",
        "mineral_ids": ["aluminum", "chromium", "cobalt", "copper", "manganese", "tin", "tungsten", "uranium"],
        "country_ids": ["belgian-congo", "northern-rhodesia", "south-africa", "united-states"],
        "frus_document_ids": [frus_id("frus1947v01", "d395"), frus_id("frus1947v01", "d431"), frus_id("frus1949v01", "d204"), frus_id("frus1950v01", "d95"), frus_id("frus1950v01", "d167"), frus_id("frus1950v01", "d200"), frus_id("frus1951v01", "d242"), frus_id("frus1952-54v11p1", "d27")],
        "agreement_ids": ["erp-strategic-materials-provisions-1947", "nsc68-materials-program-1950", "tripartite-uranium-control-1944"],
        "law_ids": ["stock-piling-act-1946", "defense-production-act-1950"], "source_ids": ["frus-history-at-state", "govinfo-statutes"],
        "outcome": None, "completeness": "verified-pilot"
    },
    {
        "id": "decolonization-and-resource-access", "title": "Decolonization and resource access", "start": 1952, "end": 1975,
        "summary": "The pilot begins with a reviewed 1953 FRUS intelligence estimate on Tropical Africa; country-specific political transitions and economic bargaining require expansion.",
        "mineral_ids": ["chromium", "cobalt", "copper", "manganese", "tin"],
        "country_ids": ["belgian-congo", "northern-rhodesia", "south-africa", "chile", "indonesia", "united-states"],
        "frus_document_ids": [frus_id("frus1952-54v11p1", "d27"), frus_id("frus1964-68v09", "d344"), frus_id("frus1964-68v26", "d138"), frus_id("frus1964-68v26", "d142"), frus_id("frus1964-68v26", "d148"), frus_id("frus1969-76v21", "d250"), frus_id("frus1969-76v21", "d256"), frus_id("frus1969-76v21", "d261"), frus_id("frus1969-76ve16", "d87")],
        "agreement_ids": ["stockpile-objectives-review-1967", "chile-copper-compensation-1971"], "law_ids": [], "source_ids": ["frus-history-at-state"],
        "outcome": None, "completeness": "research-queue"
    },
    {
        "id": "chile-copper-nationalization-1971", "title": "Chilean copper nationalization and compensation", "start": 1971, "end": 1971,
        "summary": "Reviewed FRUS documents connect copper nationalization to compensation, diplomatic representations, interagency review, and Chile's access to international credit.",
        "mineral_ids": ["copper"], "country_ids": ["chile"],
        "frus_document_ids": [frus_id("frus1969-76v21", "d250"), frus_id("frus1969-76v21", "d256"), frus_id("frus1969-76v21", "d261"), frus_id("frus1969-76ve16", "d87")],
        "agreement_ids": ["chile-copper-compensation-1971"], "law_ids": [], "source_ids": ["frus-history-at-state"],
        "outcome": None, "completeness": "verified-pilot"
    },
    {
        "id": "indonesia-political-crisis-1965", "title": "Indonesian political crisis and U.S. policy reassessment", "start": 1965, "end": 1966,
        "summary": "Reviewed FRUS documents record strained bilateral relations, concern for American people and property, the October political crisis, and Department guidance to the Embassy. The pilot does not assert that mineral access drove these decisions.",
        "mineral_ids": [], "country_ids": ["indonesia"],
        "frus_document_ids": [frus_id("frus1964-68v26", "d138"), frus_id("frus1964-68v26", "d142"), frus_id("frus1964-68v26", "d148")],
        "agreement_ids": [], "law_ids": [], "source_ids": ["frus-history-at-state"],
        "outcome": None, "completeness": "verified-pilot"
    },
    {
        "id": "late-cold-war-resource-policy", "title": "Late Cold War resource and stockpile policy", "start": 1976, "end": 1992,
        "summary": "The pilot currently represents statutory stockpile revision; commodity, trade, and administration-specific evidence remains incomplete.",
        "mineral_ids": ["chromium", "copper", "manganese"], "country_ids": ["chile", "south-africa", "united-states"],
        "frus_document_ids": [], "agreement_ids": [], "law_ids": ["stock-piling-revision-act-1979"],
        "source_ids": ["govinfo-statutes"], "outcome": None, "completeness": "research-queue"
    }
]


AGREEMENTS = [
    ("copper-shipment-correspondence-1914", "Wartime copper-shipment correspondence", "negotiation-record", ["United States"], None, ["copper"], [], [frus_id("frus1914Supp", "d423"), frus_id("frus1914Supp", "d427")], "https://history.state.gov/historicaldocuments/frus1914Supp/d423", "FRUS chapter context identifies correspondence concerning shipments of copper; formal agreement status is not asserted."),
    ("firestone-rubber-concession-negotiations-1925", "Firestone rubber concession and loan negotiations", "concession", ["Liberia", "Firestone interests"], None, [], [], [frus_id("frus1925v02", "d327"), frus_id("frus1925v02", "d344")], "https://history.state.gov/historicaldocuments/frus1925v02/d327", "FRUS chapter context identifies negotiations concerning a rubber concession and Finance Corporation of America loan."),
    ("strategic-stockpile-planning-1939", "Strategic raw-material stockpile planning record", "other", ["United States"], None, [], ["united-states"], [frus_id("frus1939v01", "d934"), frus_id("frus1939v01", "d939")], "https://history.state.gov/historicaldocuments/frus1939v01/d934", "FRUS chapter context identifies formulation of plans to acquire strategic-raw-material stockpiles; this row is a policy instrument, not a treaty."),
    ("surinam-bauxite-protection-1941", "Arrangements for protection of Surinam bauxite mines", "other", ["United States", "Netherlands"], None, ["bauxite", "aluminum"], ["surinam"], [frus_id("frus1941v02", "d805"), frus_id("frus1941v02", "d821")], "https://history.state.gov/historicaldocuments/frus1941v02/d805", "FRUS chapter context identifies arrangements for American forces to assist in protecting bauxite mines."),
    ("turkish-chrome-negotiations-1941", "U.S.-British negotiations for Turkish chrome", "negotiation-record", ["United States", "United Kingdom", "Turkey"], None, ["chromium"], ["turkey"], [frus_id("frus1941v03", "d1006"), frus_id("frus1941v03", "d1038")], "https://history.state.gov/historicaldocuments/frus1941v03/d1006", "FRUS chapter context identifies efforts to acquire Turkish chrome and prevent its sale to Germany."),
    ("international-tin-control-agreement-1942", "Agreement continuing international control of tin production and export", "commodity-agreement", ["International parties; verification pending"], "1942-09-09", ["tin"], [], [frus_id("frus1942v01", "d440")], "https://history.state.gov/historicaldocuments/frus1942v01/d440", "The FRUS chapter heading states that an agreement was signed September 9, 1942; parties and treaty-series citation remain to be verified."),
    ("congo-tripartite-trade-negotiations-1942", "U.S.-U.K.-Belgium negotiations on Belgian Congo trade", "negotiation-record", ["United States", "United Kingdom", "Belgium"], None, ["cobalt", "copper", "tin"], ["belgian-congo"], [frus_id("frus1942v02", "d3"), frus_id("frus1942v02", "d14")], "https://history.state.gov/historicaldocuments/frus1942v02/d3", "FRUS chapter context identifies negotiations for a tripartite agreement relating to Belgian Congo imports and exports."),
    ("bolivian-strategic-materials-purchase-1942", "Negotiations for U.S. purchase of strategic materials from Bolivia", "purchasing-agreement", ["United States", "Bolivia"], None, ["tin", "tungsten", "copper"], ["bolivia"], [frus_id("frus1942v05", "d493")], "https://history.state.gov/historicaldocuments/frus1942v05/d493", "FRUS chapter context identifies purchase negotiations; exact contract title and terms require document-level review."),
    ("us-bolivia-economic-cooperation-1942", "U.S.-Bolivia economic cooperation program", "negotiation-record", ["United States", "Bolivia"], None, ["tin"], ["bolivia"], [frus_id("frus1942v05", "d564")], "https://history.state.gov/historicaldocuments/frus1942v05/d564", "FRUS chapter context identifies a program of economic cooperation; legal form and implementation consequences remain under review."),
    ("us-uk-uranium-acquisition-1944", "Combined Development Trust Congo uranium purchasing pathway", "purchasing-agreement", ["Combined Development Trust", "African Metals Corporation", "Union Miniere du Haut Katanga"], None, ["uranium"], [], [frus_id("frus1944v02", "d886")], "https://history.state.gov/historicaldocuments/frus1944v02/d886", "The reviewed tripartite agreement states that a separate contract would be entered into between the Combined Development Trust and African Metals Corporation, acting for Union Miniere du Haut Katanga. This pathway does not assert the separate contract's date or full terms."),
    ("tripartite-uranium-control-1944", "U.S.-U.K.-Belgium agreement regarding control of uranium", "executive-agreement", ["United States", "United Kingdom", "Belgium"], "1944-09-26", ["uranium"], ["belgian-congo"], [frus_id("frus1944v02", "d886"), frus_id("frus1947v01", "d431"), frus_id("frus1949v01", "d204"), frus_id("frus1950v01", "d167"), frus_id("frus1950v01", "d200"), frus_id("frus1951v01", "d242")], "https://history.state.gov/historicaldocuments/frus1944v02/d886", "The reviewed FRUS agreement and follow-on records document control, delivery, first-refusal rights, production expansion, technical assistance, and negotiations over commercial and developmental benefits."),
    ("erp-strategic-materials-provisions-1947", "European Recovery Program strategic-materials provisions", "negotiation-record", ["United States", "European Recovery Program participants"], None, ["chromium", "cobalt", "copper", "manganese", "tin", "tungsten"], ["united-states"], [frus_id("frus1947v01", "d395")], "https://history.state.gov/historicaldocuments/frus1947v01/d395", "A reviewed FRUS circular connected recovery planning, overseas production, and U.S. stockpiling; this row does not assert a separate treaty."),
    ("nsc68-materials-program-1950", "NSC-68 materials and stockpile program review", "other", ["United States"], None, ["aluminum", "chromium", "cobalt", "copper", "manganese", "tin", "tungsten"], ["united-states"], [frus_id("frus1950v01", "d95")], "https://history.state.gov/historicaldocuments/frus1950v01/d95", "A reviewed FRUS memorandum discusses strategic stockpile objectives and foreign-source assumptions; this is a policy-process record, not an international agreement."),
    ("stockpile-objectives-review-1967", "Interagency stockpile objectives review", "other", ["United States"], "1967-06-27", ["chromium", "cobalt", "copper", "manganese", "tin", "tungsten"], ["united-states"], [frus_id("frus1964-68v09", "d344")], "https://history.state.gov/historicaldocuments/frus1964-68v09/d344", "A reviewed FRUS memorandum records interagency assessment of politically and economically dependable foreign sources; this is a policy-process record, not a treaty."),
    ("chile-copper-compensation-1971", "Chile copper nationalization and compensation negotiations", "investment-dispute", ["United States", "Chile"], None, ["copper"], ["chile"], [frus_id("frus1969-76v21", "d250"), frus_id("frus1969-76v21", "d256"), frus_id("frus1969-76v21", "d261"), frus_id("frus1969-76ve16", "d87")], "https://history.state.gov/historicaldocuments/frus1969-76v21/d250", "Reviewed FRUS documents describe nationalization, compensation, diplomatic representations, and policy review. This row is a negotiation pathway, not a treaty.")
]


def agreement_rows() -> list[dict]:
    rows = []
    for item in AGREEMENTS:
        identifier, title, record_type, parties, signature, minerals, countries, documents, url, summary = item
        rows.append({
            "id": identifier, "official_title": title, "short_title": title, "record_type": record_type,
            "parties": parties, "signature_date": signature, "entry_into_force_date": None, "termination_date": None,
            "treaty_series_citation": None, "statutes_at_large_citation": None, "tias_number": None,
            "mineral_ids": minerals, "country_ids": countries, "frus_document_ids": documents,
            "official_text_url": url, "summary": summary, "implementation_consequences": [],
            "source_ids": ["frus-history-at-state"] if identifier in {"us-uk-uranium-acquisition-1944", "tripartite-uranium-control-1944", "erp-strategic-materials-provisions-1947", "nsc68-materials-program-1950", "stockpile-objectives-review-1967", "chile-copper-compensation-1971"} else ["frus-history-at-state", "frus-subject-index"],
            "completeness": "verified-pilot" if identifier in {"tripartite-uranium-control-1944", "erp-strategic-materials-provisions-1947", "nsc68-materials-program-1950", "stockpile-objectives-review-1967", "chile-copper-compensation-1971"} else "partial"
        })
    return rows


LAWS = [
    {
        "id": "stock-piling-act-1946", "official_title": "Strategic and Critical Materials Stock Piling Act",
        "public_law_number": "Public Law 79-520", "statutes_at_large_citation": "60 Stat. 596", "enactment_date": "1946-07-23",
        "summary": "Established a statutory basis for acquiring and retaining strategic and critical materials. Consult the official compilation for amendments and current codification.",
        "relevant_provisions": [], "mineral_ids": ["chromium", "cobalt", "manganese", "tin", "tungsten"],
        "frus_document_ids": [frus_id("frus1947v01", "d395"), frus_id("frus1950v01", "d95")],
        "episode_ids": ["early-cold-war-mobilization"], "official_text_url": "https://www.govinfo.gov/app/details/COMPS-674",
        "source_ids": ["govinfo-statutes"], "completeness": "partial"
    },
    {
        "id": "defense-production-act-1950", "official_title": "Defense Production Act of 1950",
        "public_law_number": "Public Law 81-774", "statutes_at_large_citation": "64 Stat. 798", "enactment_date": "1950-09-08",
        "summary": "Authorized measures affecting production capacity and supply for national defense. The official compilation controls for amended text.",
        "relevant_provisions": [], "mineral_ids": ["aluminum", "chromium", "cobalt", "copper", "manganese", "tin", "tungsten"],
        "frus_document_ids": [frus_id("frus1950v01", "d95")], "episode_ids": ["early-cold-war-mobilization"],
        "official_text_url": "https://www.govinfo.gov/app/details/COMPS-8323", "source_ids": ["govinfo-statutes"], "completeness": "partial"
    },
    {
        "id": "stock-piling-revision-act-1979", "official_title": "Strategic and Critical Materials Stock Piling Revision Act of 1979",
        "public_law_number": "Public Law 96-41", "statutes_at_large_citation": "93 Stat. 319", "enactment_date": "1979-07-30",
        "summary": "Revised the national-defense stockpile framework. Project annotations of mineral-specific effects remain a research queue.",
        "relevant_provisions": [], "mineral_ids": ["chromium", "cobalt", "manganese", "tin", "tungsten"],
        "frus_document_ids": [], "episode_ids": ["late-cold-war-resource-policy"],
        "official_text_url": "https://www.govinfo.gov/app/details/STATUTE-93/STATUTE-93-Pg319", "source_ids": ["govinfo-statutes"], "completeness": "partial"
    }
]


ADMINISTRATIONS = [
    {"id": "wilson", "president": "Woodrow Wilson", "start": 1913, "end": 1921, "summary": "Pilot coverage currently centers on FRUS discovery leads concerning wartime copper shipments.", "mineral_ids": ["copper"], "country_ids": ["united-states"], "frus_document_ids": [frus_id("frus1914Supp", "d423"), frus_id("frus1914Supp", "d427")], "agreement_ids": ["copper-shipment-correspondence-1914"], "law_ids": [], "episode_ids": ["world-war-i-resource-access"], "source_ids": ["frus-history-at-state", "frus-subject-index"], "completeness": "research-queue"},
    {"id": "franklin-roosevelt", "president": "Franklin D. Roosevelt", "start": 1933, "end": 1945, "summary": "Pilot FRUS pathways cover stockpile planning, bauxite protection, chrome acquisition, tin purchasing, Congo trade, and uranium agreements.", "mineral_ids": ["aluminum", "bauxite", "chromium", "cobalt", "copper", "tin", "tungsten", "uranium"], "country_ids": ["bolivia", "belgian-congo", "surinam", "turkey", "united-states"], "frus_document_ids": [frus_id("frus1939v01", "d934"), frus_id("frus1939v01", "d939"), frus_id("frus1941v02", "d805"), frus_id("frus1941v02", "d821"), frus_id("frus1941v03", "d1006"), frus_id("frus1941v03", "d1038"), frus_id("frus1942v01", "d440"), frus_id("frus1942v02", "d3"), frus_id("frus1942v02", "d14"), frus_id("frus1942v05", "d493"), frus_id("frus1942v05", "d564"), frus_id("frus1944v02", "d886")], "agreement_ids": [row[0] for row in AGREEMENTS[2:11]], "law_ids": [], "episode_ids": ["interwar-planning", "world-war-ii-procurement"], "source_ids": ["frus-history-at-state", "frus-subject-index"], "completeness": "partial"},
    {"id": "truman", "president": "Harry S. Truman", "start": 1945, "end": 1953, "summary": "Reviewed FRUS records connect recovery planning, stockpile objectives, foreign-source assumptions, African strategic materials, and continuing Congo uranium negotiations.", "mineral_ids": ["aluminum", "chromium", "cobalt", "copper", "manganese", "tin", "tungsten", "uranium"], "country_ids": ["belgian-congo", "northern-rhodesia", "south-africa", "united-states"], "frus_document_ids": [frus_id("frus1947v01", "d395"), frus_id("frus1947v01", "d431"), frus_id("frus1949v01", "d204"), frus_id("frus1950v01", "d95"), frus_id("frus1950v01", "d167"), frus_id("frus1950v01", "d200"), frus_id("frus1951v01", "d242"), frus_id("frus1952-54v11p1", "d27")], "agreement_ids": ["tripartite-uranium-control-1944", "erp-strategic-materials-provisions-1947", "nsc68-materials-program-1950"], "law_ids": ["stock-piling-act-1946", "defense-production-act-1950"], "episode_ids": ["early-cold-war-mobilization"], "source_ids": ["frus-history-at-state", "govinfo-statutes"], "completeness": "verified-pilot"},
    {"id": "johnson", "president": "Lyndon B. Johnson", "start": 1963, "end": 1969, "summary": "Pilot coverage links a reviewed stockpile-objectives memorandum with three documents on the 1965 Indonesian political crisis. The pilot does not assert a mineral-access motive for the Indonesia policy record.", "mineral_ids": ["chromium", "cobalt", "copper", "manganese", "tin", "tungsten"], "country_ids": ["indonesia", "united-states"], "frus_document_ids": [frus_id("frus1964-68v09", "d344"), frus_id("frus1964-68v26", "d138"), frus_id("frus1964-68v26", "d142"), frus_id("frus1964-68v26", "d148")], "agreement_ids": ["stockpile-objectives-review-1967"], "law_ids": [], "episode_ids": ["indonesia-political-crisis-1965", "decolonization-and-resource-access"], "source_ids": ["frus-history-at-state"], "completeness": "partial"},
    {"id": "nixon", "president": "Richard Nixon", "start": 1969, "end": 1974, "summary": "Reviewed FRUS documents connect Chilean copper nationalization to compensation, diplomatic representations, international credit, and interagency policy review.", "mineral_ids": ["copper"], "country_ids": ["chile"], "frus_document_ids": [frus_id("frus1969-76v21", "d250"), frus_id("frus1969-76v21", "d256"), frus_id("frus1969-76v21", "d261"), frus_id("frus1969-76ve16", "d87")], "agreement_ids": ["chile-copper-compensation-1971"], "law_ids": [], "episode_ids": ["chile-copper-nationalization-1971", "decolonization-and-resource-access"], "source_ids": ["frus-history-at-state"], "completeness": "verified-pilot"}
]


STOCKPILE_CASES = [
    {
        "id": "stockpile-planning-1939", "title": "From contingency planning to a strategic raw-materials stockpile", "start": 1939, "end": 1946,
        "summary": "FRUS indexes 1939 planning for strategic raw-material stockpiles; the 1946 Act supplies a statutory endpoint for this pilot pathway.",
        "mineral_ids": [], "frus_document_ids": [frus_id("frus1939v01", "d934"), frus_id("frus1939v01", "d939")],
        "law_ids": ["stock-piling-act-1946"], "acquisitions": [], "disposals": [], "goals": [], "holdings": [],
        "data_gaps": ["Material-level goals and holdings have not been transcribed."], "source_ids": ["frus-history-at-state", "frus-subject-index", "govinfo-statutes"], "completeness": "partial"
    },
    {
        "id": "stockpile-objectives-1950-1967", "title": "Foreign-source assumptions and stockpile objectives", "start": 1950, "end": 1967,
        "summary": "Two reviewed FRUS records show how agencies debated mobilization requirements and the political and economic accessibility of foreign supply.",
        "mineral_ids": ["aluminum", "chromium", "cobalt", "copper", "manganese", "tin", "tungsten"],
        "frus_document_ids": [frus_id("frus1950v01", "d95"), frus_id("frus1964-68v09", "d344")],
        "law_ids": ["stock-piling-act-1946", "defense-production-act-1950"], "acquisitions": [], "disposals": [], "goals": [], "holdings": [],
        "data_gaps": ["Historical planning quantities are not normalized or displayed until their units and definitions are verified."],
        "source_ids": ["frus-history-at-state", "govinfo-statutes"], "completeness": "verified-pilot"
    }
]


VERIFIED_FRUS = {
    ("frus1944v02", "d886"): {
        "title": "The Belgian Minister for Foreign Affairs (Spaak) to the American Ambassador in the United Kingdom (Winant)", "date": "1944-09-26",
        "contextual_summary": "The transmittal and enclosed agreement documented allied control of uranium and thorium ores, contracted Congo uranium delivery, assistance to reopen and develop the mine, and first-refusal rights.",
        "minerals": ["uranium"], "countries": ["belgian-congo"],
        "themes": ["uranium control", "contracted delivery", "mine redevelopment", "first refusal"],
        "agreements": ["us-uk-uranium-acquisition-1944", "tripartite-uranium-control-1944"], "laws": [],
        "nara": ["nara-rg218-congo-uranium", "nara-rg59-congo-uranium-agreement"]
    },
    ("frus1947v01", "d431"): {
        "title": "Memorandum of Conversation, by Mr. Theodore C. Achilles of the Division of Western European Affairs", "date": "1947-10-03",
        "contextual_summary": "Belgian Prime Minister Spaak discussed secrecy surrounding the uranium agreement and Belgium's claim to equitable participation in future industrial uses of atomic energy derived from Congo uranium.",
        "minerals": ["uranium"], "countries": ["belgian-congo"],
        "themes": ["agreement secrecy", "industrial atomic energy", "Belgian participation"],
        "agreements": ["tripartite-uranium-control-1944"], "laws": [],
        "nara": ["nara-rg59-congo-uranium-agreement", "nara-rg84-brussels-uranium"],
        "volume_year_start": 1947, "volume_year_end": 1947,
        "volume_context": "Foreign policy aspects of United States development of atomic energy"
    },
    ("frus1949v01", "d204"): {
        "title": "Memorandum of Conversation, by Mr. R. Gordon Arneson, Special Assistant to the Under Secretary of State (Webb)", "date": "1949-10-05",
        "contextual_summary": "State and the Belgian Ambassador discussed Belgian participation in uranium-allocation consultations and technical cooperation under the 1944 agreement.",
        "minerals": ["uranium"], "countries": ["belgian-congo"],
        "themes": ["uranium allocation", "technical cooperation", "agreement implementation"],
        "agreements": ["tripartite-uranium-control-1944"], "laws": [],
        "nara": ["nara-rg59-congo-uranium-agreement", "nara-rg84-brussels-uranium"],
        "volume_year_start": 1949, "volume_year_end": 1949,
        "volume_context": "Foreign policy aspects of United States development of atomic energy"
    },
    ("frus1950v01", "d167"): {
        "title": "The Secretary of State to the Embassy in Belgium", "date": "1950-02-22",
        "contextual_summary": "The Secretary linked Belgian ore deliveries to U.S. atomic-weapons strength and addressed consultation, technical assistance, and the deferred commercial-use provisions of the 1944 agreement.",
        "minerals": ["uranium"], "countries": ["belgian-congo"],
        "themes": ["collective security", "ore delivery", "technical assistance", "commercial atomic energy"],
        "agreements": ["tripartite-uranium-control-1944"], "laws": [],
        "nara": ["nara-rg59-congo-uranium-agreement", "nara-rg84-brussels-uranium"],
        "volume_year_start": 1950, "volume_year_end": 1950,
        "volume_context": "Foreign policy aspects of United States development of atomic energy"
    },
    ("frus1950v01", "d200"): {
        "title": "Memorandum by Mr. R. Gordon Arneson to the Secretary of State", "date": "1950-12-14",
        "contextual_summary": "The memorandum reviewed Belgian atomic-energy negotiations, an export-tax proposal, a proposed Congo processing plant, and measures intended to accelerate uranium production.",
        "minerals": ["uranium"], "countries": ["belgian-congo"],
        "themes": ["export tax", "processing", "production expansion", "atomic-energy negotiations"],
        "agreements": ["tripartite-uranium-control-1944"], "laws": [],
        "nara": ["nara-rg59-congo-uranium-agreement", "nara-rg84-brussels-uranium"]
    },
    ("frus1951v01", "d242"): {
        "title": "Statement of the Position of the United States and the United Kingdom", "date": "1951-04-05",
        "contextual_summary": "The statement distinguished uranium from other strategic materials while addressing Belgian requests for atomic-energy assistance and broader Congo development and defense programs.",
        "minerals": ["uranium"], "countries": ["belgian-congo"],
        "themes": ["strategic valuation", "technical assistance", "development finance", "agreement implementation"],
        "agreements": ["tripartite-uranium-control-1944"], "laws": [],
        "nara": ["nara-rg59-congo-uranium-agreement", "nara-rg84-brussels-uranium"]
    },
    ("frus1947v01", "d395"): {
        "title": "The Acting Secretary of State to Certain Diplomatic and Consular Offices", "date": "1947-12-22",
        "contextual_summary": "A confidential circular airgram connected European Recovery Program planning to overseas production and U.S. stockpiling of a named list of strategic and critical materials.",
        "minerals": ["chromium", "cobalt", "copper", "manganese", "tin", "tungsten"], "countries": ["united-states"],
        "themes": ["stockpiling", "foreign production", "economic recovery"], "agreements": ["erp-strategic-materials-provisions-1947"], "laws": ["stock-piling-act-1946"],
        "nara": ["nara-rg59-strategic-materials-erp"]
    },
    ("frus1950v01", "d95"): {
        "title": "Memorandum by the National Security Resources Board: Comments on NSC/68 Programs", "date": "1950-05-29",
        "contextual_summary": "The National Security Resources Board described strategic stockpile objectives, foreign-source assumptions, and material requirements in planning connected to NSC-68.",
        "minerals": ["aluminum", "chromium", "cobalt", "copper", "manganese", "tin", "tungsten"], "countries": ["united-states"],
        "themes": ["stockpile objectives", "mobilization requirements", "foreign-source assumptions"], "agreements": ["nsc68-materials-program-1950"], "laws": ["stock-piling-act-1946", "defense-production-act-1950"],
        "nara": ["nara-rg59-nsc68-strategic-materials", "nara-rg353-stockpile-objectives"]
    },
    ("frus1952-54v11p1", "d27"): {
        "title": "National Intelligence Estimate: Conditions and Trends in Tropical Africa", "date": "1953-12-22",
        "contextual_summary": "A National Intelligence Estimate assessed the strategic importance of Tropical Africa, including access to cobalt, copper, chrome, manganese, tin, graphite, and other raw materials.",
        "minerals": ["chromium", "cobalt", "copper", "manganese", "tin"], "countries": ["belgian-congo", "northern-rhodesia", "south-africa"],
        "themes": ["strategic raw materials", "colonial geography", "political access"], "agreements": [], "laws": [],
        "nara": ["nara-rg59-tropical-africa-strategic-materials", "nara-rg218-africa-raw-materials"]
    },
    ("frus1964-68v09", "d344"): {
        "title": "Memorandum on Stockpile Objectives", "date": "1967-06-27",
        "contextual_summary": "A Defense memorandum recorded how State and Defense evaluated the political and economic dependability of accessible foreign sources when calculating strategic-material stockpile needs.",
        "minerals": ["chromium", "cobalt", "copper", "manganese", "tin", "tungsten"], "countries": ["united-states"],
        "themes": ["accessible foreign sources", "stockpile objectives", "interagency assessment"], "agreements": ["stockpile-objectives-review-1967"], "laws": ["stock-piling-act-1946"],
        "nara": ["nara-rg59-accessible-foreign-sources", "nara-rg330-stockpile-objectives"]
    },
    ("frus1969-76v21", "d250"): {
        "title": "Telegram From the Department of State to the Embassy in Chile", "date": "1971-08-18",
        "contextual_summary": "The Department instructed the Embassy to present a formal note concerning Chile's copper nationalization law and compensation for affected U.S. interests.",
        "minerals": ["copper"], "countries": ["chile"],
        "themes": ["copper nationalization", "compensation", "diplomatic representation"], "agreements": ["chile-copper-compensation-1971"], "laws": [],
        "nara": ["nara-rg84-santiago-copper", "nara-rg59-chilean-copper"]
    },
    ("frus1969-76v21", "d256"): {
        "title": "Memorandum From Arnold Nachmanoff of the National Security Council Staff to the President's Assistant for National Security Affairs (Kissinger)", "date": "1971-09-08",
        "contextual_summary": "An NSC staff memorandum framed compensation and international credit as linked issues for interagency review of Chilean copper nationalization.",
        "minerals": ["copper"], "countries": ["chile"],
        "themes": ["copper nationalization", "compensation", "international credit", "interagency review"], "agreements": ["chile-copper-compensation-1971"], "laws": [],
        "nara": ["nara-rg59-chilean-copper"]
    },
    ("frus1969-76v21", "d261"): {
        "title": "Memorandum From Ashley Hewitt of the National Security Council Staff to the President's Assistant for National Security Affairs (Kissinger)", "date": "1971-09-29",
        "contextual_summary": "An NSC staff memorandum reviewed the developing copper compensation dispute and the policy questions it raised for the United States.",
        "minerals": ["copper"], "countries": ["chile"],
        "themes": ["copper nationalization", "compensation", "policy review"], "agreements": ["chile-copper-compensation-1971"], "laws": [],
        "nara": ["nara-rg59-chilean-copper"]
    },
    ("frus1969-76ve16", "d87"): {
        "title": "Intelligence Note Prepared in the Bureau of Intelligence and Research", "date": "1971-10-14",
        "contextual_summary": "A Bureau of Intelligence and Research note assessed copper and domestic politics in Chile after nationalization.",
        "minerals": ["copper"], "countries": ["chile"],
        "themes": ["copper nationalization", "domestic politics", "intelligence assessment"], "agreements": ["chile-copper-compensation-1971"], "laws": [],
        "nara": ["nara-rg59-chilean-copper"]
    },
    ("frus1964-68v26", "d138"): {
        "title": "Telegram From the Embassy in Indonesia to the Department of State", "date": "1965-09-01",
        "contextual_summary": "The Embassy reported a meeting with President Sukarno amid strained bilateral relations and concerns involving American people and property.",
        "minerals": [], "countries": ["indonesia"],
        "themes": ["bilateral relations", "American property", "embassy reporting"], "agreements": [], "laws": [],
        "nara": ["nara-rg59-indonesia-1965"], "volume_year_start": 1964, "volume_year_end": 1968, "volume_context": "Indonesia"
    },
    ("frus1964-68v26", "d142"): {
        "title": "Memorandum for President Johnson", "date": "1965-10-01",
        "contextual_summary": "A memorandum briefed President Johnson on the immediate Indonesian political crisis following the events of September 30.",
        "minerals": [], "countries": ["indonesia"],
        "themes": ["political crisis", "presidential briefing", "policy reassessment"], "agreements": [], "laws": [],
        "nara": ["nara-rg59-indonesia-1965"], "volume_year_start": 1964, "volume_year_end": 1968, "volume_context": "Indonesia"
    },
    ("frus1964-68v26", "d148"): {
        "title": "Telegram From the Department of State to the Embassy in Indonesia", "date": "1965-10-06",
        "contextual_summary": "The Department sent policy guidance to the Embassy during the Indonesian political crisis, including public-information and mission considerations.",
        "minerals": [], "countries": ["indonesia"],
        "themes": ["policy guidance", "public information", "embassy operations"], "agreements": [], "laws": [],
        "nara": ["nara-rg59-indonesia-1965"], "volume_year_start": 1964, "volume_year_end": 1968, "volume_context": "Coup and Counter Reaction: October 1965-March 1966"
    }
}


FRUS_SELECTIONS = [
    ("frus1914Supp", "d423", ["copper"], ["united-states"], ["wartime shipping"], ["copper-shipment-correspondence-1914"]),
    ("frus1914Supp", "d427", ["copper"], ["united-states"], ["wartime shipping"], ["copper-shipment-correspondence-1914"]),
    ("frus1925v02", "d327", [], [], ["concessions", "private finance"], ["firestone-rubber-concession-negotiations-1925"]),
    ("frus1925v02", "d344", [], [], ["concessions", "private finance"], ["firestone-rubber-concession-negotiations-1925"]),
    ("frus1939v01", "d934", [], ["united-states"], ["stockpile planning"], ["strategic-stockpile-planning-1939"]),
    ("frus1939v01", "d939", [], ["united-states"], ["stockpile planning"], ["strategic-stockpile-planning-1939"]),
    ("frus1941v02", "d805", ["bauxite", "aluminum"], ["surinam"], ["mine protection"], ["surinam-bauxite-protection-1941"]),
    ("frus1941v02", "d821", ["bauxite", "aluminum"], ["surinam"], ["mine protection"], ["surinam-bauxite-protection-1941"]),
    ("frus1941v03", "d1006", ["chromium"], ["turkey"], ["allied purchasing", "denial"], ["turkish-chrome-negotiations-1941"]),
    ("frus1941v03", "d1038", ["chromium"], ["turkey"], ["allied purchasing", "denial"], ["turkish-chrome-negotiations-1941"]),
    ("frus1942v02", "d3", ["cobalt", "copper", "tin"], ["belgian-congo"], ["trade coordination"], ["congo-tripartite-trade-negotiations-1942"]),
    ("frus1942v02", "d14", ["cobalt", "copper", "tin"], ["belgian-congo"], ["trade coordination"], ["congo-tripartite-trade-negotiations-1942"]),
    ("frus1942v05", "d493", ["tin", "tungsten", "copper"], ["bolivia"], ["purchasing", "economic diplomacy"], ["bolivian-strategic-materials-purchase-1942"]),
    ("frus1942v01", "d440", ["tin"], [], ["commodity control"], ["international-tin-control-agreement-1942"]),
    ("frus1942v05", "d564", ["tin"], ["bolivia"], ["economic cooperation"], ["us-bolivia-economic-cooperation-1942"]),
    ("frus1944v02", "d886", ["uranium"], ["belgian-congo"], ["uranium control", "allied agreement"], ["us-uk-uranium-acquisition-1944", "tripartite-uranium-control-1944"]),
    ("frus1947v01", "d395", [], [], [], []),
    ("frus1947v01", "d431", [], [], [], []),
    ("frus1949v01", "d204", [], [], [], []),
    ("frus1950v01", "d95", [], [], [], []),
    ("frus1950v01", "d167", [], [], [], []),
    ("frus1950v01", "d200", [], [], [], []),
    ("frus1951v01", "d242", [], [], [], []),
    ("frus1952-54v11p1", "d27", [], [], [], []),
    ("frus1964-68v09", "d344", [], [], [], []),
    ("frus1969-76v21", "d250", [], [], [], []),
    ("frus1969-76v21", "d256", [], [], [], []),
    ("frus1969-76v21", "d261", [], [], [], []),
    ("frus1969-76ve16", "d87", [], [], [], []),
    ("frus1964-68v26", "d138", [], [], [], []),
    ("frus1964-68v26", "d142", [], [], [], []),
    ("frus1964-68v26", "d148", [], [], [], [])
]


def load_frus_index() -> dict:
    text = FRUS_INDEX.read_text(encoding="utf-8")
    return json.loads(text.split("=", 1)[1].rstrip(";\n"))


def build_frus_documents() -> list[dict]:
    index = load_frus_index()
    lookup = {(row[0], row[1]): row for row in index["records"]}
    documents = []
    for volume, document, minerals, countries, themes, agreements in FRUS_SELECTIONS:
        row = lookup.get((volume, document))
        verified = VERIFIED_FRUS.get((volume, document))
        if not row and not verified:
            raise SystemExit(f"FRUS index is missing {volume}/{document}")
        identifier = frus_id(volume, document)
        documents.append({
            "id": identifier,
            "series": "Foreign Relations of the United States",
            "volume": volume,
            "document_number": document.removeprefix("d"),
            "title": verified["title"] if verified else None,
            "date": verified["date"] if verified else None,
            "participants": verified.get("participants", []) if verified else [],
            "country_ids": verified["countries"] if verified else countries,
            "mineral_ids": verified["minerals"] if verified else minerals,
            "policy_themes": verified["themes"] if verified else themes,
            "source_note": None,
            "stable_url": f"https://history.state.gov/historicaldocuments/{volume}/{document}",
            "volume_context": row[5] if row else verified["volume_context"],
            "volume_year_start": row[2] if row else verified["volume_year_start"],
            "volume_year_end": row[3] if row else verified["volume_year_end"],
            "contextual_summary": verified["contextual_summary"] if verified else None,
            "statistic_ids": [
                "usgs-ds140-tin-1942-u-s-primary-production",
                "usgs-ds140-tin-1942-u-s-imports",
                "usgs-ds140-tin-1942-u-s-apparent-consumption",
                "usgs-ds140-tin-1942-unit-value",
                "usgs-ds140-tin-1942-world-production"
            ] if (volume, document) == ("frus1942v05", "d493") else [],
            "agreement_ids": verified["agreements"] if verified else agreements,
            "law_ids": verified["laws"] if verified else [],
            "nara_query_ids": verified["nara"] if verified else [],
            "outcome": None,
            "metadata_status": "verified-document" if verified else "subject-index-lead",
            "source_ids": ["frus-history-at-state"] if verified else ["frus-history-at-state", "frus-subject-index"]
        })
    return documents


NARA_QUERIES = [
    ("nara-rg59-bolivian-tin", "Bolivia tin strategic materials", ["59"], 1941, 1945, ["tin"], ["bolivia"]),
    ("nara-rg59-surinam-bauxite", "Surinam bauxite mines", ["59"], 1940, 1945, ["bauxite", "aluminum"], ["surinam"]),
    ("nara-rg165-strategic-materials", "strategic materials procurement", ["165"], 1917, 1945, [], ["united-states"]),
    ("nara-rg169-bolivia-tin", "Bolivia tin purchasing", ["169"], 1941, 1945, ["tin"], ["bolivia"]),
    ("nara-rg169-turkish-chrome", "Turkey chrome purchasing", ["169"], 1940, 1945, ["chromium"], ["turkey"]),
    ("nara-rg218-congo-uranium", "Belgian Congo uranium", ["218"], 1943, 1955, ["uranium"], ["belgian-congo"]),
    ("nara-rg59-congo-uranium-agreement", "Belgian Congo uranium agreement atomic energy", ["59"], 1944, 1956, ["uranium"], ["belgian-congo"]),
    ("nara-rg84-brussels-uranium", "Belgium Congo uranium atomic energy", ["84"], 1944, 1956, ["uranium"], ["belgian-congo"]),
    ("nara-rg59-rare-earths", "rare earths monazite strategic materials", ["59"], 1945, 1992, ["rare-earth-elements"], ["united-states"]),
    ("nara-rg229-rubber-minerals", "rubber strategic materials Latin America", ["229"], 1940, 1946, [], []),
    ("nara-rg234-strategic-materials", "strategic materials production", ["234"], 1939, 1957, [], ["united-states"]),
    ("nara-rg287-stockpile-reports", "strategic critical materials stockpile", ["287"], 1939, 1992, [], ["united-states"]),
    ("nara-rg330-stockpile-objectives", "stockpile objectives strategic materials", ["330"], 1950, 1970, [], ["united-states"]),
    ("nara-rg353-stockpile-objectives", "stockpile objectives foreign sources", ["353"], 1947, 1970, [], ["united-states"]),
    ("nara-rg59-accessible-foreign-sources", "accessible foreign sources strategic materials", ["59"], 1946, 1970, [], ["united-states"]),
    ("nara-rg59-strategic-materials-erp", "European Recovery Program strategic materials", ["59"], 1947, 1952, [], ["united-states"]),
    ("nara-rg59-nsc68-strategic-materials", "NSC 68 strategic materials stockpile", ["59"], 1949, 1953, [], ["united-states"]),
    ("nara-rg59-tropical-africa-strategic-materials", "Tropical Africa strategic materials", ["59"], 1950, 1960, ["cobalt", "copper", "chromium", "manganese", "tin"], ["belgian-congo", "northern-rhodesia", "south-africa"]),
    ("nara-rg218-africa-raw-materials", "Africa strategic raw materials", ["218"], 1948, 1965, ["cobalt", "copper", "chromium", "manganese"], ["belgian-congo", "northern-rhodesia", "south-africa"]),
    ("nara-rg84-la-paz-tin", "tin strategic materials", ["84"], 1940, 1955, ["tin"], ["bolivia"]),
    ("nara-rg84-santiago-copper", "copper nationalization", ["84"], 1960, 1980, ["copper"], ["chile"]),
    ("nara-rg84-leopoldville-cobalt", "cobalt copper strategic minerals", ["84"], 1945, 1971, ["cobalt", "copper"], ["belgian-congo"]),
    ("nara-rg84-pretoria-strategic-minerals", "chromium manganese strategic minerals", ["84"], 1945, 1992, ["chromium", "manganese"], ["south-africa"]),
    ("nara-rg59-chilean-copper", "Chile copper nationalization", ["59"], 1960, 1980, ["copper"], ["chile"]),
    ("nara-rg59-congo-cobalt", "Congo cobalt strategic materials", ["59"], 1945, 1975, ["cobalt"], ["belgian-congo"]),
    ("nara-rg59-rhodesia-chromium", "Rhodesia chrome chromium sanctions", ["59"], 1965, 1980, ["chromium"], ["northern-rhodesia"]),
    ("nara-rg59-south-africa-minerals", "South Africa strategic minerals", ["59"], 1945, 1992, ["chromium", "manganese"], ["south-africa"]),
    ("nara-rg59-turkish-chrome", "Turkey chrome Germany", ["59"], 1939, 1945, ["chromium"], ["turkey"]),
    ("nara-rg59-indonesia-1965", "Indonesia 1965 political economic relations", ["59"], 1964, 1966, [], ["indonesia"]),
    ("nara-rg84-djakarta-resources", "Indonesia tin petroleum minerals", ["84"], 1958, 1968, ["tin", "bauxite", "copper"], ["indonesia"])
]


def nara_query_rows() -> list[dict]:
    rows = []
    for identifier, query, groups, start, end, minerals, countries in NARA_QUERIES:
        rows.append({
            "id": identifier, "label": query, "query": query, "record_groups": groups,
            "date_start": start, "date_end": end, "available_online": True,
            "mineral_ids": minerals, "country_ids": countries,
            "relevance_method": "Structured discovery query only. Rank returned descriptions as direct, probable, contextual, or broad archival leads after review.",
            "result_status": "live-query-plan", "source_ids": ["nara-catalog-api"]
        })
    return rows


MODERN_CONTEXT = [
    {
        "id": "modern-context-current-usgs-list", "title": "Modern Context",
        "summary": "Current U.S. critical-minerals categories provide a reason to revisit the historical record, but they are not projected backward as if earlier officials used the same category.",
        "source_label": "U.S. Geological Survey, 2025 List of Critical Minerals",
        "source_url": "https://www.usgs.gov/news/science-snippet/interior-department-releases-final-2025-list-critical-minerals",
        "boundary_note": "This panel is outside the 1861-1992 historical dataset."
    }
]


def main() -> None:
    datasets = {
        "sources": SOURCES,
        "minerals": MINERALS,
        "countries": COUNTRIES,
        "episodes": EPISODES,
        "agreements": agreement_rows(),
        "laws": LAWS,
        "administrations": ADMINISTRATIONS,
        "stockpile-cases": STOCKPILE_CASES,
        "frus-documents": build_frus_documents(),
        "nara-queries": nara_query_rows(),
        "country-briefs": COUNTRY_BRIEFS,
        "modern-context": MODERN_CONTEXT
    }
    for name, value in datasets.items():
        write(name, value)
    print("Wrote " + ", ".join(f"{name}={len(value)}" for name, value in datasets.items()))


if __name__ == "__main__":
    main()
