#!/usr/bin/env python3
"""Build one source-bounded atlas evidence ledger for every year, 1861-1992."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "history-stack"
ATLAS_PATH = ROOT / "data" / "atlas" / "atlas.json"
OUTPUT = DATA / "annual-snapshots.json"
START_YEAR = 1861
END_YEAR = 1992


def load(name: str) -> list[dict]:
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def active_span(row: dict, year: int, start: str = "start", end: str = "end") -> bool:
    return row.get(start, 9999) <= year <= row.get(end, 0)


def mineral_match(row: dict, mineral_id: str | None, empty_matches: bool = False) -> bool:
    if mineral_id is None:
        return True
    ids = row.get("mineral_ids") or []
    return mineral_id in ids if ids else empty_matches


def coverage_status(counts: dict[str, int]) -> str:
    has_frus = counts["frus_documents"] > 0
    has_context = (
        counts["official_statistics"]
        + counts["commodity_trade_rows"]
        + counts["broad_trade_context_rows"]
    ) > 0
    if has_frus and has_context:
        return "document-plus-context"
    if has_frus:
        return "documentary-only"
    if has_context:
        return "context-only"
    return "sparse"


def main() -> None:
    atlas = json.loads(ATLAS_PATH.read_text(encoding="utf-8"))
    minerals = load("minerals")
    countries = load("countries")
    frus = load("frus-documents")
    episodes = load("episodes")
    laws = load("laws")
    stockpile = load("stockpile-cases")
    nara = load("nara-queries")
    statistics = load("statistics")
    trade = load("trade")
    trade_details = load("trade-details")
    dataweb = load("dataweb-trade")
    comtrade = load("comtrade-rare-earth")
    strategic_comtrade = load("comtrade-strategic-materials")

    country_by_a3 = {row["a3"]: row["id"] for row in atlas["countries"]}
    country_ids = {row["id"] for row in countries}
    mineral_ids = [row["id"] for row in minerals]
    profile_countries = {
        row["id"]: sorted(country_id for country_id in row.get("country_ids", []) if country_id in country_ids)
        for row in minerals
    }

    def build_slice(year: int, mineral_id: str | None) -> dict:
        year_frus = [
            row for row in frus
            if row["volume_year_start"] <= year <= row["volume_year_end"]
            and mineral_match(row, mineral_id)
        ]
        year_episodes = [
            row for row in episodes
            if active_span(row, year) and mineral_match(row, mineral_id, True)
        ]
        year_relationships = [
            row for row in atlas["relationships"]
            if row["year"] == year and mineral_match(row, mineral_id, True)
        ]
        year_instruments = [
            row for row in atlas["instruments"]
            if row["year"] == year and mineral_match(row, mineral_id, True)
        ]
        year_laws = [
            row for row in laws
            if row.get("enactment_date") and int(row["enactment_date"][:4]) == year
            and mineral_match(row, mineral_id, True)
        ]
        year_stockpile = [
            row for row in stockpile
            if active_span(row, year) and mineral_match(row, mineral_id, True)
        ]
        year_nara = [
            row for row in nara
            if row["date_start"] <= year <= row["date_end"]
            and mineral_match(row, mineral_id, True)
        ]
        year_statistics = [
            row for row in statistics
            if row["year"] == year and (mineral_id is None or row["mineral_id"] == mineral_id)
        ]
        broad_trade = [
            row for row in trade
            if row["year_start"] <= year <= row["year_end"] and row.get("mineral_id") is None
        ]
        mineral_trade = [
            row for row in trade
            if row["year_start"] <= year <= row["year_end"]
            and row.get("mineral_id") is not None
            and (mineral_id is None or row["mineral_id"] == mineral_id)
        ]
        year_trade_details = [
            row for row in trade_details
            if row["year"] == year and (mineral_id is None or row["mineral_id"] == mineral_id)
        ]
        year_dataweb = [
            row for row in dataweb
            if row["year"] == year and (mineral_id is None or row["mineral_id"] == mineral_id)
        ]
        year_comtrade = [
            row for row in comtrade
            if row["year"] == year and (mineral_id in {None, "rare-earth-elements"})
        ]
        year_strategic_comtrade = [
            row for row in strategic_comtrade
            if row["year"] == year and (mineral_id is None or row["mineral_id"] == mineral_id)
        ]

        evidence = defaultdict(set)

        def add(country_id: str | None, token: str) -> None:
            if country_id in country_ids:
                evidence[country_id].add(token)

        for row in year_frus:
            for country_id in row.get("country_ids", []):
                add(country_id, f"frus:{row['id']}")
        for row in year_episodes:
            for country_id in row.get("country_ids", []):
                add(country_id, f"episode:{row['id']}")
        for row in year_relationships:
            add(row.get("country_id") or row.get("from_country_id"), f"relationship:{row['id']}")
        for row in year_instruments:
            add(row.get("country_id"), f"instrument:{row['id']}")
        for row in year_nara:
            for country_id in row.get("country_ids", []):
                add(country_id, f"nara:{row['id']}")
        for row in year_statistics:
            add(row.get("country_id"), f"statistic:{row['id']}")
        for row in year_dataweb:
            add(country_by_a3.get(row.get("partner_iso3")), f"dataweb:{row['id']}")
        for row in year_comtrade:
            add(country_by_a3.get(row.get("reporter_iso3")), f"comtrade:{row['id']}")
            add(country_by_a3.get(row.get("partner_iso3")), f"comtrade:{row['id']}")
        for row in year_strategic_comtrade:
            add(country_by_a3.get(row.get("reporter_iso3")), f"comtrade:{row['id']}")
            add(country_by_a3.get(row.get("partner_iso3")), f"comtrade:{row['id']}")

        counts = {
            "frus_documents": len(year_frus),
            "reviewed_frus_documents": sum(row.get("metadata_status") == "verified-document" for row in year_frus),
            "frus_discovery_leads": sum(row.get("metadata_status") != "verified-document" for row in year_frus),
            "year_linked_geographies": len(evidence),
            "active_episodes": len(year_episodes),
            "documented_access_links": len(year_relationships),
            "dated_instruments": len(year_instruments),
            "laws_enacted": len(year_laws),
            "stockpile_pathways": len(year_stockpile),
            "nara_query_plans": len(year_nara),
            "official_statistics": len(year_statistics),
            "broad_trade_context_rows": len(broad_trade),
            "commodity_trade_rows": len(mineral_trade) + len(year_trade_details) + len(year_dataweb) + len(year_comtrade) + len(year_strategic_comtrade),
            "dataweb_partner_rows": len(year_dataweb),
            "comtrade_context_rows": len(year_comtrade) + len(year_strategic_comtrade),
        }

        if mineral_id is None:
            contextual = sorted({country_id for ids in profile_countries.values() for country_id in ids})
        else:
            contextual = profile_countries[mineral_id]

        missing_lanes = []
        if counts["frus_documents"] == 0:
            missing_lanes.append("frus")
        if counts["year_linked_geographies"] == 0:
            missing_lanes.append("geography")
        if counts["official_statistics"] + counts["commodity_trade_rows"] == 0:
            missing_lanes.append("statistics")
        if counts["dated_instruments"] + counts["laws_enacted"] + counts["stockpile_pathways"] == 0:
            missing_lanes.append("policy")
        if counts["nara_query_plans"] == 0:
            missing_lanes.append("archives")

        return {
            "coverage_status": coverage_status(counts),
            "counts": counts,
            "country_evidence_counts": {key: len(value) for key, value in sorted(evidence.items())},
            "profile_context_country_ids": contextual,
            "missing_lanes": missing_lanes,
        }

    snapshots = []
    for year in range(START_YEAR, END_YEAR + 1):
        snapshots.append({
            "id": f"annual-{year}",
            "year": year,
            "schema_version": "1.0",
            "overall": build_slice(year, None),
            "materials": {mineral_id: build_slice(year, mineral_id) for mineral_id in mineral_ids},
        })

    payload = "[\n" + ",\n".join(
        f"  {json.dumps(row, ensure_ascii=True, separators=(',', ':'))}" for row in snapshots
    ) + "\n]\n"
    OUTPUT.write_text(payload, encoding="utf-8")
    print(f"Wrote {len(snapshots)} annual snapshots to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
