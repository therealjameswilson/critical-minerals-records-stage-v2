import json
import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from connectors.nara import normalize_nara_hit, search_nara


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "history-stack"


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def walk_years(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"year", "start", "end", "volume_year_start", "volume_year_end"} and isinstance(value, int):
                yield value
            else:
                yield from walk_years(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_years(value)


def test_pilot_meets_minimum_entity_counts():
    expected = {
        "minerals": 10,
        "countries": 9,
        "episodes": 8,
        "agreements": 15,
        "frus-documents": 32,
        "administrations": 5,
        "laws": 3,
        "stockpile-cases": 2,
        "nara-queries": 30,
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
    }
    for name, minimum in expected.items():
        assert len(load(name)) >= minimum


def test_all_historical_data_stays_between_1861_and_1992():
    for path in DATA.glob("*.json"):
        if path.name in {"sources.json", "modern-context.json"}:
            continue
        values = list(walk_years(json.loads(path.read_text(encoding="utf-8"))))
        assert all(1861 <= year <= 1992 for year in values), path.name


def test_statistics_have_units_dates_and_provenance():
    rows = load("statistics")
    assert len(rows) >= 1000
    required = {
        "metric", "mineral_id", "year", "unit", "value", "publication_title",
        "publication_year", "table_or_page", "agency", "source_url",
        "access_date", "transcription_status", "original_unit",
        "displayed_unit", "conversion_methodology", "confidence"
    }
    assert all(required <= set(row) for row in rows)
    assert all(row["unit"] and row["table_or_page"] and row["source_url"] for row in rows)
    assert all(row["transcription_status"] == "machine-extracted-xlsx" for row in rows)


def test_policy_in_numbers_uses_expected_official_tin_values():
    rows = {
        row["metric"]: row
        for row in load("statistics")
        if row["mineral_id"] == "tin" and row["year"] == 1942
    }
    assert rows["U.S. primary production"]["value"] == 16400
    assert rows["U.S. imports"]["value"] == 27200
    assert rows["U.S. apparent consumption"]["value"] == 96400
    assert rows["World production"]["value"] == 124000
    assert rows["Unit value"]["price_basis"] == "nominal"


def test_uranium_and_rare_earth_profiles_preserve_different_evidence_depth():
    minerals = {row["id"]: row for row in load("minerals")}
    documents = {row["id"]: row for row in load("frus-documents")}
    statistics = load("statistics")

    uranium = minerals["uranium"]
    rare_earths = minerals["rare-earth-elements"]
    assert len(uranium["frus_document_ids"]) == 6
    assert all(documents[identifier]["metadata_status"] == "verified-document" for identifier in uranium["frus_document_ids"])
    assert rare_earths["frus_document_ids"] == []
    assert any(row["mineral_id"] == "rare-earth-elements" and row["year"] == 1900 for row in statistics)
    assert any("FRUS" in gap for gap in rare_earths["data_gaps"])


def test_trade_records_cover_every_selectable_year_without_interpolation():
    rows = load("trade")
    for year in range(1861, 1993):
        assert any(row["year_start"] <= year <= row["year_end"] for row in rows), year
    annual = [row for row in rows if row["temporal_precision"] == "annual"]
    assert all(row["year_start"] == row["year_end"] for row in annual)
    assert all(row["transcription_status"] == "machine-extracted-xlsx" for row in annual)


def test_census_trade_bridge_preserves_published_scope_and_values():
    rows = {
        (row["direction"], row["metric"].rsplit(" ", 1)[-1]): row
        for row in load("trade")
        if row["year_start"] == 1861 and row["year_end"] == 1865
    }
    assert rows[("exports", "value")]["value"] == 33990
    assert rows[("exports", "share")]["value"] == 19.97
    assert rows[("imports", "value")]["value"] == 36064
    assert rows[("imports", "share")]["value"] == 14.12
    assert all(row["material_scope"] == "broad-economic-class" for row in rows.values())
    assert all(row["mineral_id"] is None for row in rows.values())
    assert all("multi-year average" in row["conversion_methodology"] for row in rows.values())


def test_usgs_trade_rows_preserve_exact_year_units_and_provenance():
    rows = [row for row in load("trade") if row["mineral_id"] == "tin" and row["year_start"] == 1942]
    by_direction = {row["direction"]: row for row in rows}
    assert by_direction["imports"]["value"] == 27200
    assert by_direction["imports"]["unit"] == "metric tons (t) tin content"
    assert by_direction["exports"]["table_or_page"].startswith("Tin worksheet")
    assert all(row["source_id"] == "usgs-ds140" for row in rows)


def test_rare_earth_census_recovery_covers_every_published_year():
    rows = [row for row in load("trade-details") if row["mineral_id"] == "rare-earth-elements"]
    assert len(rows) == 294
    assert {row["year"] for row in rows} == set(range(1970, 1991))
    assert all(sum(row["year"] == year for row in rows) == 14 for year in range(1970, 1991))
    assert all(row["transcription_status"] == "machine-parsed-reviewed-official-table" for row in rows)


def test_1983_rare_earth_census_recovery_preserves_published_categories():
    rows = [row for row in load("trade-details") if row["year"] == 1983 and row["mineral_id"] == "rare-earth-elements"]
    totals = {(row["direction"], row["category"]): row for row in rows}
    imports = totals[("imports", "Published total")]
    exports = totals[("exports", "Published total")]
    assert imports["quantity"]["value"] == 822
    assert imports["trade_value"]["value"] == 15826
    assert exports["quantity"]["value"] == 2743
    thorium = totals[("exports", "Thorium ore and concentrates")]
    assert thorium["quantity"]["value"] == 2684
    assert all(row["source_origin_agency"] == "Bureau of the Census" for row in rows)


def test_rare_earth_importer_preserves_missing_symbols_and_hts_break():
    rows = {(row["year"], row["direction"], row["category"]): row for row in load("trade-details")}
    assert rows[(1970, "imports", "Cerium salts")]["quantity"]["status"] == "published-dash"
    assert rows[(1970, "exports", "Cerium compounds")]["quantity"]["status"] == "not-available"
    assert rows[(1975, "imports", "Other rare-earth metals")]["quantity"]["status"] == "less-than"
    assert "Harmonized Tariff System" in rows[(1989, "imports", "Published total")]["classification_note"]
    assert rows[(1990, "imports", "Published total")]["quantity"]["value"] == 7155
    assert rows[(1990, "imports", "Published total")]["trade_value"]["value"] == 64741


def test_rare_earth_partner_rows_remain_year_specific_acquisition_queues():
    queues = load("trade-research")
    assert len(queues) == 21
    assert {queue["year"] for queue in queues} == set(range(1970, 1991))
    assert all(queue["status"] == "source-acquisition" for queue in queues)
    assert all({row["series"] for row in queue["reports"]} == {"FT 246", "FT 446"} for queue in queues)
    assert all(len(queue["control_total_ids"]) == 2 for queue in queues)
    assert all(any("Do not draw atlas trade-flow lines" in note for note in queue["classification_notes"]) for queue in queues)


def test_dataweb_partner_trade_covers_the_full_portal_overlap():
    rows = load("dataweb-trade")
    assert len(rows) >= 3600
    assert {row["year"] for row in rows} == {1989, 1990, 1991, 1992}
    assert {row["mineral_id"] for row in rows} == {row["id"] for row in load("minerals")}
    assert all(row["source_id"] == "usitc-dataweb" for row in rows)
    assert all(row["classification_level"] == "HS6" and re.fullmatch(r"\d{6}", row["commodity_code"]) for row in rows)
    assert all(re.fullmatch(r"[A-Z]{3}", row["partner_iso3"]) for row in rows)
    assert all((row["trade_value"]["value"] or 0) > 0 or (row["quantity"]["value"] or 0) > 0 for row in rows)


def test_dataweb_preserves_representative_rare_earth_and_uranium_rows():
    rows = {
        (row["year"], row["direction"], row["commodity_code"], row["source_partner_name"]): row
        for row in load("dataweb-trade")
    }
    rare_earth = rows[(1989, "imports", "280530", "China")]
    assert rare_earth["trade_value"]["value"] == 754063
    assert rare_earth["quantity"]["unit"] == "kilograms"
    uranium = rows[(1989, "imports", "284410", "Canada")]
    assert uranium["trade_value"]["value"] == 373623125
    assert uranium["commodity_description"].startswith("NATURAL URANIUM")
    assert all("mine origin" in row["caveat"] for row in (rare_earth, uranium))


def test_dataweb_query_manifest_reconciles_to_static_cache():
    rows = load("dataweb-trade")
    manifests = load("dataweb-query-manifest")
    assert {row["direction"] for row in manifests} == {"imports", "exports"}
    for manifest in manifests:
        assert manifest["years"] == [1989, 1990, 1991, 1992]
        assert manifest["record_count"] == sum(row["direction"] == manifest["direction"] for row in rows)
        assert re.fullmatch(r"[0-9a-f]{64}", manifest["query_sha256"])


def test_dataweb_ingestion_uses_anonymous_public_session_without_secret():
    script = (ROOT / "scripts" / "ingest_usitc_dataweb.py").read_text(encoding="utf-8")
    assert "XSRF-TOKEN" in script
    assert "DATAWEB_API_TOKEN" not in script
    assert "Authorization" not in script


def test_comtrade_continuity_series_preserves_classification_vintages():
    rows = load("comtrade-rare-earth")
    assert len(rows) >= 170
    assert min(row["year"] for row in rows) == 1966
    assert max(row["year"] for row in rows) == 1992
    for row in rows:
        expected = "S1" if row["year"] <= 1975 else "S2" if row["year"] <= 1987 else "S3"
        assert row["classification_code"] == expected
        assert row["source_id"] == "un-comtrade"
        assert row["scope_confidence"] in {"high", "low"}
        assert row["scope_caveat"]


def test_comtrade_preserves_reporter_mirror_values_without_merging_them():
    rows = {
        (row["year"], row["reporter_iso3"], row["flow_code"], row["partner_iso3"], row["commodity_code"]): row
        for row in load("comtrade-rare-earth")
    }
    assert rows[(1970, "USA", "M", None, "51326")]["primary_value"] == 564080
    assert rows[(1985, "USA", "M", None, "52217")]["net_weight_kg"] == 645996
    us_report = rows[(1992, "USA", "M", "CHN", "52595")]
    china_report = rows[(1992, "CHN", "X", "USA", "52595")]
    assert us_report["primary_value"] == 8154255
    assert china_report["primary_value"] == 7959606
    assert us_report["id"] != china_report["id"]
    assert not us_report["is_original_classification"]
    assert not china_report["is_original_classification"]


def test_comtrade_manifest_covers_queries_including_zero_result_years():
    rows = load("comtrade-rare-earth")
    manifests = load("comtrade-query-manifest")
    assert len(manifests) == 40
    assert len([row for row in manifests if row["reporter"] == "united-states"]) == 31
    assert len([row for row in manifests if row["reporter"] == "china"]) == 9
    assert sum(row["record_count"] for row in manifests) == len(rows)
    assert any(row["year"] == 1962 and row["record_count"] == 0 for row in manifests)
    assert all(re.fullmatch(r"[0-9a-f]{64}", row["query_sha256"]) for row in manifests)


def test_comtrade_importer_uses_public_preview_without_secret():
    script = (ROOT / "scripts" / "ingest_un_comtrade_rare_earth.py").read_text(encoding="utf-8")
    assert "public/v1/preview" in script
    assert "COMTRADE_API_KEY" not in script
    assert "Authorization" not in script


def test_strategic_comtrade_covers_nine_materials_and_all_31_years():
    rows = load("comtrade-strategic-materials")
    manifests = load("comtrade-strategic-query-manifest")
    assert len(rows) >= 2000
    assert {row["year"] for row in manifests} == set(range(1962, 1993))
    assert sum(row["record_count"] for row in manifests) == len(rows)
    assert {row["mineral_id"] for row in rows} == {
        "aluminum", "bauxite", "chromium", "cobalt", "copper",
        "manganese", "tin", "tungsten", "uranium"
    }
    for row in rows:
        expected = "S1" if row["year"] <= 1975 else "S2" if row["year"] <= 1987 else "S3"
        assert row["classification_code"] == expected
        assert row["scope_confidence"] in {"high", "medium", "low"}
        assert row["scope_caveat"]
        assert row["source_id"] == "un-comtrade"


def test_strategic_comtrade_retains_reported_partner_values_and_product_stages():
    rows = {
        (row["year"], row["mineral_id"], row["flow_code"], row["partner_iso3"], row["commodity_code"]): row
        for row in load("comtrade-strategic-materials")
    }
    chile_refined = rows[(1983, "copper", "M", "CHL", "68212")]
    congo_refined = rows[(1983, "copper", "M", "COD", "68212")]
    assert chile_refined["primary_value"] == 428190784
    assert chile_refined["net_weight_kg"] == 270717888
    assert chile_refined["supply_chain_stage"] == "refined-metal"
    assert congo_refined["primary_value"] == 46755712


def test_strategic_comtrade_crosswalk_is_revision_bounded_and_auditable():
    crosswalk = yaml.safe_load((ROOT / "data" / "crosswalks" / "comtrade_sitc_mineral_codes.yml").read_text(encoding="utf-8"))
    assert set(crosswalk["classifications"]) == {"S1", "S2", "S3"}
    assert crosswalk["classifications"]["S1"]["years"] == [1962, 1975]
    assert crosswalk["classifications"]["S2"]["years"] == [1976, 1987]
    assert crosswalk["classifications"]["S3"]["years"] == [1988, 1992]
    for definition in crosswalk["classifications"].values():
        assert definition["codes"]
        assert all({"mineral_id", "stage", "confidence", "caveat"} <= set(row) for row in definition["codes"].values())
    script = (ROOT / "scripts" / "ingest_un_comtrade_strategic_materials.py").read_text(encoding="utf-8")
    assert "public/v1/preview" not in script  # shared official client supplies the endpoint
    assert "COMTRADE_API_KEY" not in script
    assert "Authorization" not in script


def test_atlas_renders_census_recovery_pilot_separately_from_standardized_trade():
    atlas = (ROOT / "assets" / "atlas.js").read_text(encoding="utf-8")
    portal = (ROOT / "assets" / "portal.js").read_text(encoding="utf-8")
    assert "renderTradeDetailPilot" in atlas
    assert "Census recovery pilot" in atlas
    assert "They are displayed side by side and are not merged" in atlas
    assert 'data.trade.length + data["trade-details"].length' in portal


def test_atlas_exposes_reported_trade_as_context_not_the_default_spine():
    atlas_script = (ROOT / "assets" / "atlas.js").read_text(encoding="utf-8")
    atlas_data = json.loads((ROOT / "data" / "atlas" / "atlas.json").read_text(encoding="utf-8"))
    layer = next(row for row in atlas_data["layers"] if row["id"] == "quantitative-trade-flows")
    assert layer["availability"] == "supported"
    assert layer["source_ids"] == ["un-comtrade", "usitc-dataweb"]
    assert "FRUS remains the documentary spine" in atlas_script
    assert "Map reported import value" in atlas_script
    assert 'H.loadJson("dataweb-trade")' in atlas_script
    assert 'H.loadJson("comtrade-rare-earth")' in atlas_script
    assert 'H.loadJson("comtrade-strategic-materials")' in atlas_script
    assert layer["title"] == "Partner trade, 1962-1992"
    assert "Broad proxy families are not summed" in atlas_script
    assert 'mode: LENS_IDS.includes(options.state.mode) ? options.state.mode : "frus-activity"' in atlas_script


def test_annual_atlas_has_one_source_bounded_view_for_every_year_and_material():
    snapshots = load("annual-snapshots")
    mineral_ids = {row["id"] for row in load("minerals")}
    assert [row["year"] for row in snapshots] == list(range(1861, 1993))
    assert all(set(row["materials"]) == mineral_ids for row in snapshots)
    assert all(row["schema_version"] == "1.0" for row in snapshots)
    valid_statuses = {"document-plus-context", "documentary-only", "context-only", "sparse"}
    for row in snapshots:
        for snapshot in [row["overall"], *row["materials"].values()]:
            assert snapshot["coverage_status"] in valid_statuses
            assert all(isinstance(value, int) and value >= 0 for value in snapshot["counts"].values())
            assert set(snapshot["missing_lanes"]) <= {"frus", "geography", "statistics", "policy", "archives"}


def test_annual_atlas_distinguishes_documentary_evidence_from_context():
    snapshots = {row["year"]: row for row in load("annual-snapshots")}
    assert snapshots[1942]["overall"]["counts"]["frus_documents"] == 5
    assert snapshots[1942]["overall"]["counts"]["documented_access_links"] == 3
    rare_earth_1983 = snapshots[1983]["materials"]["rare-earth-elements"]
    assert rare_earth_1983["coverage_status"] == "context-only"
    assert rare_earth_1983["counts"]["frus_documents"] == 0
    assert rare_earth_1983["counts"]["comtrade_context_rows"] > 0
    assert "frus" in rare_earth_1983["missing_lanes"]


def test_atlas_labels_profile_context_separately_from_year_linked_evidence():
    atlas_script = (ROOT / "assets" / "atlas.js").read_text(encoding="utf-8")
    atlas_data = json.loads((ROOT / "data" / "atlas" / "atlas.json").read_text(encoding="utf-8"))
    resource_layer = next(row for row in atlas_data["layers"] if row["id"] == "resource-geography")
    assert 'H.loadJson("annual-snapshots")' in atlas_script
    assert "Annual evidence ledger" in atlas_script
    assert "Profile context only" in atlas_script
    assert "year-linked evidence" in resource_layer["value_semantics"]
    assert "not proof" in resource_layer["caveat"]


def test_history_stack_page_exposes_all_layers():
    html = (ROOT / "history-stack.html").read_text(encoding="utf-8")
    script = (ROOT / "assets" / "history-stack.js").read_text(encoding="utf-8")
    for layer in [
        "frus-layer", "country-brief-layer", "timeline-layer", "statistics-layer", "agreements-layer",
        "geography-layer", "law-layer", "stockpile-layer", "archives-layer",
        "decisions-layer", "outcome-layer", "provenance-layer", "modern-layer"
    ]:
        assert f'#{layer}' in html
        assert f'"{layer}"' in script
    assert "Evidence not yet linked" in script
    assert "No mine, port, railway, or smelter coordinate is invented" in script


def test_nara_integration_keeps_secret_out_of_public_files():
    assert (ROOT / ".env.example").read_text(encoding="utf-8") == "NARA_API_KEY=\n"
    runtime = (ROOT / "assets" / "runtime-config.js").read_text(encoding="utf-8")
    worker = (ROOT / "nara_proxy_worker.js").read_text(encoding="utf-8")
    assert "NARA_API_KEY" not in runtime
    assert "env.NARA_API_KEY" in worker
    assert '"Cache-Control": "no-store"' in worker
    assert "do not cache or store" in (ROOT / "docs" / "nara-integration.md").read_text(encoding="utf-8")


def test_nara_query_plans_are_not_cached_api_records():
    plans = load("nara-queries")
    assert len(plans) >= 27
    assert all(row["result_status"] == "live-query-plan" for row in plans)
    assert all("naid" not in row and "hits" not in row for row in plans)
    assert all(1861 <= row["date_start"] <= row["date_end"] <= 1992 for row in plans)


def test_country_intelligence_pilots_are_source_bounded():
    briefs = {row["country_id"]: row for row in load("country-briefs")}
    expected = {
        "bolivia": 1942,
        "chile": 1971,
        "belgian-congo": 1953,
        "indonesia": 1965,
    }
    assert {country: briefs[country]["default_year"] for country in expected} == expected
    for country, year in expected.items():
        brief = briefs[country]
        assert any(row["start"] <= year <= row["end"] for row in brief["relationship_periods"])
        assert brief["frus_document_ids"]
        assert brief["source_ids"]
        assert brief["data_gaps"]


def test_country_brief_facts_preserve_verified_and_unknown_status():
    briefs = load("country-briefs")
    for brief in briefs:
        fact_groups = [brief["baseline_facts"]] + [row.get("facts", {}) for row in brief["profile_periods"]]
        for facts in fact_groups:
            for fact in facts.values():
                assert fact["status"] in {"verified", "estimated", "unknown"}
                if fact["status"] == "unknown":
                    assert fact["value"] is None
                if fact["status"] == "verified":
                    assert fact.get("source_id") or fact.get("frus_document_id")


def test_country_interface_has_shareable_year_controls_and_explicit_unknowns():
    html = (ROOT / "history-stack.html").read_text(encoding="utf-8")
    script = (ROOT / "assets" / "history-stack.js").read_text(encoding="utf-8")
    assert 'id="countryBriefNav"' in html
    for control in ["countryYearRange", "countryYearNumber", "previousCountryYear", "nextCountryYear"]:
        assert control in script
    assert 'url.searchParams.set("year"' in script
    assert "Country production" in script
    assert "Share of U.S. imports" in script
    assert "Unknown, not estimated" in script
    assert "They are not statistics for" in script
    assert 'class="stack-layer collapsible-layer"' in script


def test_chile_and_indonesia_country_briefs_link_reviewed_frus_records():
    documents = {row["id"]: row for row in load("frus-documents")}
    briefs = {row["country_id"]: row for row in load("country-briefs")}
    assert set(briefs["chile"]["frus_document_ids"]) == {
        "frus-1969-76v21-d250", "frus-1969-76v21-d256",
        "frus-1969-76v21-d261", "frus-1969-76ve16-d87",
    }
    assert set(briefs["indonesia"]["frus_document_ids"]) == {
        "frus-1964-68v26-d138", "frus-1964-68v26-d142", "frus-1964-68v26-d148",
    }
    for identifier in briefs["chile"]["frus_document_ids"] + briefs["indonesia"]["frus_document_ids"]:
        assert documents[identifier]["metadata_status"] == "verified-document"
        assert documents[identifier]["stable_url"].startswith("https://history.state.gov/")


def test_nara_normalizer_returns_metadata_only_shape():
    hit = {
        "_id": "12345",
        "_source": {"record": {
            "title": "Strategic materials files",
            "levelOfDescription": "series",
            "recordGroupNumber": "59",
            "inclusiveStartDate": {"logicalDate": "1942-01-01"},
            "scopeAndContentNote": "Catalog description only",
            "extractedText": "This must not be retained",
        }}
    }
    row = normalize_nara_hit(hit, "2026-07-10T00:00:00+00:00")
    assert row["naid"] == "12345"
    assert row["catalog_url"] == "https://catalog.archives.gov/id/12345"
    assert row["date"] == "1942-01-01"
    assert "extractedText" not in row
    assert row["relevance"] == "unreviewed archival lead"


def test_nara_connector_requires_environment_secret_without_network_call():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="NARA_API_KEY"):
            search_nara("Bolivia tin")


def test_no_post_1992_event_cache_is_embedded_in_homepage():
    html = (ROOT / "records-stage.html").read_text(encoding="utf-8")
    assert "EVENTS_CACHE" not in html
    assert "2026 Critical Minerals Ministerial" not in html
    assert "ministerial follow-up" not in html.lower()


def test_frontend_has_accessible_visualization_alternatives():
    html = (ROOT / "records-stage.html").read_text(encoding="utf-8")
    script = (ROOT / "assets" / "history-stack.js").read_text(encoding="utf-8")
    assert "Open accessible atlas table" in html
    assert "role=\"img\"" in script
    assert "A table follows the chart" in script
    assert "prefers-reduced-motion" in (ROOT / "assets" / "portal.css").read_text(encoding="utf-8")


def test_history_stack_minimap_has_explicit_svg_palette():
    script = (ROOT / "assets" / "history-stack.js").read_text(encoding="utf-8")
    css = (ROOT / "assets" / "portal.css").read_text(encoding="utf-8")
    for class_name in ["ocean", "graticule", "land", "map-marker"]:
        assert f'class="{class_name}"' in script
        assert f".history-map-mini .{class_name}" in css
    assert '[data-theme="dark"] .history-map-mini .ocean' in css


def test_public_pages_do_not_contain_social_drafting_language():
    public = "\n".join((ROOT / name).read_text(encoding="utf-8") for name in [
        "records-stage.html", "history-stack.html", "methodology.html",
        "assets/portal.js", "assets/atlas.js", "assets/history-stack.js"
    ]).lower()
    assert not re.search(r"\b(tweet|social media campaign|draft post|clearance status)\b", public)


def test_atlas_layers_are_source_bounded_and_unsupported_modes_stay_locked():
    atlas = json.loads((ROOT / "data" / "atlas" / "atlas.json").read_text(encoding="utf-8"))
    assert atlas["meta"]["historical_start"] == 1861
    assert atlas["meta"]["historical_end"] == 1992
    by_id = {row["id"]: row for row in atlas["layers"]}
    for layer_id in [
        "frus-activity", "access-relationships", "agreements",
        "stockpile-policy", "historical-events", "nara-discovery",
        "resource-geography", "quantitative-trade-flows",
    ]:
        assert by_id[layer_id]["availability"] == "supported"
        assert by_id[layer_id]["value_semantics"]
        assert by_id[layer_id]["source_ids"]
        assert by_id[layer_id]["caveat"]
    for layer_id in [
        "mineral-production", "import-dependence",
        "infrastructure", "alliances-boundaries", "strategic-risk",
    ]:
        assert by_id[layer_id]["availability"] == "locked"
        assert by_id[layer_id]["required_data"]
    assert all(row["line_value_semantics"] == "linked pilot FRUS records" for row in atlas["relationships"])


def test_atlas_uses_local_vector_runtime_and_orientation_geometry():
    html = (ROOT / "records-stage.html").read_text(encoding="utf-8")
    assert "assets/vendor/maplibre-gl/maplibre-gl.js?v=5.24.0" in html
    assert "unpkg.com" not in html
    assert (ROOT / "assets" / "vendor" / "maplibre-gl" / "LICENSE.txt").exists()
    geometry = json.loads((ROOT / "data" / "atlas" / "world-orientation.geojson").read_text(encoding="utf-8"))
    codes = {row["properties"]["ADM0_A3"] for row in geometry["features"]}
    assert {"USA", "BOL", "CHL", "COD", "ZMB", "ZAF", "SUR", "TUR", "IDN"} <= codes
    assert "historical borders are not yet reconstructed" in (ROOT / "methodology.html").read_text(encoding="utf-8").lower()


def test_atlas_url_state_and_accessible_contracts_are_visible():
    portal = (ROOT / "assets" / "portal.js").read_text(encoding="utf-8")
    atlas = (ROOT / "assets" / "atlas.js").read_text(encoding="utf-8")
    html = (ROOT / "records-stage.html").read_text(encoding="utf-8")
    for key in ["country", "atlas", "layers", "mineral", "year"]:
        assert f"{key}:" in portal
    assert 'role="tablist"' in html
    assert 'role="tabpanel"' in html
    assert "ArrowLeft" in atlas and "ArrowRight" in atlas
    assert "Counts are documentary coverage" in html
    assert 'data-atlas-tab="trade"' in html
    assert "renderTradePanel" in atlas
    assert "No annual value is inferred" in atlas


def test_atlas_visual_system_keeps_the_map_primary_and_resettable():
    atlas = (ROOT / "assets" / "atlas.js").read_text(encoding="utf-8")
    css = (ROOT / "assets" / "portal.css").read_text(encoding="utf-8")
    html = (ROOT / "records-stage.html").read_text(encoding="utf-8")
    assert 'id="atlasResetView"' in html
    assert 'id: "atlas-graticule"' in atlas
    assert "graticuleGeoJson" in atlas
    assert "fitWorld" in atlas
    assert "applyMapTheme" in atlas
    assert 'grid-template-areas:' in css
    assert '"map map"' in css
    assert ".atlas-legend-kicker" in css
