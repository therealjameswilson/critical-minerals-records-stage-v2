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
        "countries": 6,
        "episodes": 4,
        "agreements": 12,
        "frus-documents": 20,
        "administrations": 4,
        "laws": 3,
        "stockpile-cases": 2,
        "nara-queries": 25,
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


def test_history_stack_page_exposes_all_twelve_layers():
    html = (ROOT / "history-stack.html").read_text(encoding="utf-8")
    script = (ROOT / "assets" / "history-stack.js").read_text(encoding="utf-8")
    for layer in [
        "frus-layer", "timeline-layer", "statistics-layer", "agreements-layer",
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
    assert len(plans) == 25
    assert all(row["result_status"] == "live-query-plan" for row in plans)
    assert all("naid" not in row and "hits" not in row for row in plans)
    assert all(1861 <= row["date_start"] <= row["date_end"] <= 1992 for row in plans)


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
    assert "Open accessible map table" in html
    assert "role=\"img\"" in script
    assert "A table follows the chart" in script
    assert "prefers-reduced-motion" in (ROOT / "assets" / "portal.css").read_text(encoding="utf-8")


def test_public_pages_do_not_contain_social_drafting_language():
    public = "\n".join((ROOT / name).read_text(encoding="utf-8") for name in [
        "records-stage.html", "history-stack.html", "methodology.html",
        "assets/portal.js", "assets/history-stack.js"
    ]).lower()
    assert not re.search(r"\b(tweet|social media campaign|draft post|clearance status)\b", public)
