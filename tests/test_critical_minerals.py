import json
from pathlib import Path

import build_cache
import cache_format
from crosswalks import load_yaml_crosswalk
from event_contract import validate_event
from parsers.critical_minerals_json_parser import parse_corpus
from scorer import score_event


ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "examples" / "critical_minerals_sample"


def test_parser_emits_valid_required_fields():
    events = list(parse_corpus(SAMPLE))
    assert len(events) >= 12
    assert all(validate_event(event) == [] for event in events)
    assert all("extra" in event for event in events)
    assert all("source_type" in event["extra"] for event in events)


def test_dates_normalize_correctly():
    events = list(parse_corpus(SAMPLE))
    ministerial = next(e for e in events if e["extra"]["record_id"] == "state-2026-critical-minerals-ministerial")
    assert ministerial["year"] == 2026
    assert ministerial["month"] == "02"
    assert ministerial["day"] == "04"


def test_scoring_returns_integer():
    event = next(iter(parse_corpus(SAMPLE)))
    score = score_event(event)
    assert isinstance(score, int)
    assert score >= 0


def test_extra_fields_survive_compact_cache(tmp_path):
    json_out = tmp_path / "events_cache.json"
    js_out = tmp_path / "events_cache.js"
    build_cache.build(SAMPLE, json_out, js_out)
    by_day = json.loads(json_out.read_text(encoding="utf-8"))
    compact = build_cache.build_compact(by_day)
    events = [event for day_events in compact.values() for event in day_events]
    assert any("mi" in event for event in events)
    assert any("cty" in event for event in events)
    assert any("st" in event for event in events)
    assert any("et" in event for event in events)
    assert any("ch" in event for event in events)
    assert any("fu" in event for event in events)
    assert any("ag" in event for event in events)
    assert any("cf" in event for event in events)
    assert cache_format.COMPACT_EXTRA_FIELDS["minerals"] == "mi"


def test_sample_data_builds_into_events_cache_json(tmp_path):
    json_out = tmp_path / "events_cache.json"
    js_out = tmp_path / "events_cache.js"
    summary = build_cache.build(SAMPLE, json_out, js_out)
    assert summary["raw_events"] >= 12
    assert summary["invalid_dropped"] == 0
    assert json_out.exists()
    assert js_out.exists()
    by_day = json.loads(json_out.read_text(encoding="utf-8"))
    assert "02-04" in by_day


def test_mineral_to_hs_crosswalk_loads_correctly():
    crosswalk = load_yaml_crosswalk("mineral_to_hs_codes")
    nickel = crosswalk["nickel"]
    codes = {row["code"]: row for row in nickel["hs_codes"]}
    assert "nickel matte" in nickel["aliases"]
    assert codes["260400"]["confidence"] == "high"
    assert codes["750210"]["caveat"].startswith("Refined product")


def test_verified_historical_seed_records_are_present():
    events = list(parse_corpus(SAMPLE))
    record_ids = {event["extra"]["record_id"] for event in events}
    assert "frus-1947-v1-d395-strategic-materials" in record_ids
    assert "frus-1950-v1-d95-stockpile-program" in record_ids
    assert "frus-1952-54-v11p1-d27-tropical-africa" in record_ids
    assert "frus-1964-68-v9-d344-stockpile-objectives" in record_ids


def test_landau_command_center_records_are_present_and_tiered():
    events = list(parse_corpus(SAMPLE))
    by_id = {event["extra"]["record_id"]: event for event in events}
    assert "white-house-2026-processed-critical-minerals-proclamation" in by_id
    assert "state-2026-landau-africa-travel" in by_id
    assert "dfc-2026-uzbekistan-joint-investment-framework" in by_id
    assert "white-house-2026-critical-minerals-workforce" in by_id
    report = by_id["landau-critical-minerals-2026-analytical-report"]
    assert report["extra"]["source_type"] == "Analytical Report"
    assert report["extra"]["evidence_type"] == "analytical_synthesis"
    assert "mixed source tiers" in report["extra"]["caveat"]


def test_portal_shell_has_history_stack_sections_and_no_operational_ui():
    html = (ROOT / "records-stage.html").read_text(encoding="utf-8")
    assert "The United States and Strategic Resources, 1861–1992" in html
    assert "FRUS explains what policymakers were thinking" in html
    assert "State of the Mineral" in html
    assert "Historical resource relationships" in html
    assert "Policy in Numbers" in html
    assert "Evidence geography, 1861–1992" in html
    assert "Treaties, agreements, and law" in html
    assert "NARA archival discovery" in html
    assert "FRUS strategic-resources index" in html
    assert "Modern Context" in html
    assert 'id="navToggle"' in html
    assert 'aria-expanded="false"' in html
    assert "2025-2026 Command Center" not in html
    assert "Implementation workstreams" not in html
    assert "Diplomatic operating tempo" not in html
    assert "Anthropic API Key" not in html
    assert "Clearance Status" not in html
    assert "Export Notes as Word" not in html
    assert "Analytical Notes" not in html
    assert "Historical question" not in html
    assert "social media" not in html.lower()
    assert "tweet" not in html.lower()


def test_portal_data_is_modular_and_hard_bounded_to_1992():
    data_root = ROOT / "data" / "history-stack"
    assert (data_root / "minerals.json").exists()
    assert (data_root / "countries.json").exists()
    assert (data_root / "frus-documents.json").exists()
    episodes = json.loads((data_root / "episodes.json").read_text(encoding="utf-8"))
    assert min(row["start"] for row in episodes) >= 1861
    assert max(row["end"] for row in episodes) <= 1992
    assert any(row["id"] == "world-war-ii-procurement" for row in episodes)
    assert all(row["id"] != "ministerial-era" for row in episodes)


def test_curated_frus_records_are_visibly_separate_from_discovery_leads():
    records = json.loads((ROOT / "data" / "history-stack" / "frus-documents.json").read_text(encoding="utf-8"))
    reviewed = [row for row in records if row["metadata_status"] == "verified-document"]
    leads = [row for row in records if row["metadata_status"] == "subject-index-lead"]
    assert len(reviewed) == 4
    assert len(leads) == 16
    assert all(row["title"] and row["date"] and row["contextual_summary"] for row in reviewed)
    assert all(row["title"] is None and row["date"] is None and row["contextual_summary"] is None for row in leads)


def test_search_map_and_mobile_navigation_contracts_are_present():
    javascript = (ROOT / "assets" / "portal.js").read_text(encoding="utf-8")
    css = (ROOT / "assets" / "portal.css").read_text(encoding="utf-8")
    assert "function runGlobalSearch" in javascript
    assert "function renderFrus" in javascript
    assert "function renderMap" in javascript
    assert "history-stack.html" in (ROOT / "assets" / "history-data.js").read_text(encoding="utf-8")
    assert ".primary-nav.is-open" in css
    assert ".nav-toggle" in css
    assert "Evidence coverage" in (ROOT / "records-stage.html").read_text(encoding="utf-8")


def test_landau_report_is_preserved_outside_browser_cache():
    report = ROOT / "research" / "Landau-Critical-Minerals-2026.md"
    text = report.read_text(encoding="utf-8")
    assert text.startswith("# Deputy Secretary Landau and the Critical Minerals Imperative")
    assert "## Executive Summary" in text
    assert "## References" in text
    assert len(text.splitlines()) == 191
    html = (ROOT / "records-stage.html").read_text(encoding="utf-8")
    assert "The critical tension identified by multiple analysts" not in html
