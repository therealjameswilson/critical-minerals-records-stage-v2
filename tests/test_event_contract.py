"""Tests for event_contract.validate_event — the boundary check that the
build pipeline runs against every parser-emitted event. The contract is the
only thing standing between a malformed adopter parser and a mid-build
KeyError, so the validation rules deserve explicit coverage."""

from event_contract import validate_event, validate_events


def _valid_event():
    return {
        "source": "State Magazine",
        "year": 1991,
        "month": "05",
        "day": "01",
        "title": "Systems management award goes to Susan Erlandsen",
        "url": "https://archive.org/details/sim_state-magazine_1991-05_344",
    }


def test_valid_event_has_no_problems():
    assert validate_event(_valid_event()) == []


def test_missing_required_field_is_reported():
    e = _valid_event()
    del e["title"]
    problems = validate_event(e)
    assert any("title" in p for p in problems)


def test_empty_title_is_rejected():
    e = _valid_event()
    e["title"] = "   "
    assert any("empty" in p for p in validate_event(e))


def test_month_out_of_range_is_rejected():
    e = _valid_event()
    e["month"] = "13"
    assert any("month" in p for p in validate_event(e))


def test_day_out_of_range_is_rejected():
    e = _valid_event()
    e["day"] = "32"
    assert any("day" in p for p in validate_event(e))


def test_non_dict_event_is_rejected():
    assert validate_event("definitely not a dict") != []


def test_validate_events_summarizes_a_batch():
    bad = _valid_event()
    bad["month"] = "13"
    summary = validate_events([_valid_event(), bad, _valid_event()])
    assert summary["ok"] is False
    assert summary["invalid"] == 1
    assert len(summary["problems"]) == 1
