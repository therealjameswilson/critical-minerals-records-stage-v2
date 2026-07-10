import json
import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest

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
        "minerals": 8,
        "countries": 9,
        "episodes": 8,
        "agreements": 15,
        "frus-documents": 27,
        "administrations": 5,
        "laws": 3,
        "stockpile-cases": 2,
        "nara-queries": 27,
        "country-briefs": 4,
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
        "resource-geography",
    ]:
        assert by_id[layer_id]["availability"] == "supported"
        assert by_id[layer_id]["value_semantics"]
        assert by_id[layer_id]["source_ids"]
        assert by_id[layer_id]["caveat"]
    for layer_id in [
        "mineral-production", "import-dependence", "quantitative-trade-flows",
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
