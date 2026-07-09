"""Tests for the State Magazine parser's identifier date extraction. The
corpus uses two IA naming conventions (YYYY-MM_NNN and month-month-YYYY_NNN)
and a regression on either would silently misdate articles — they'd land in
the wrong MM-DD bucket and disappear from the publishing tool's calendar."""

import importlib.util
from pathlib import Path

# The State Magazine adapter sits in data/state-magazine/ and isn't a normal
# importable package. Load it the same way the root parser.py does.
_p = Path(__file__).resolve().parent.parent / "data" / "state-magazine" / "parser.py"
_spec = importlib.util.spec_from_file_location("state_magazine_parser", _p)
sm_parser = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm_parser)


def test_parses_iso_form():
    """sim_state-magazine_1991-05_344 → May 1991, issue 344"""
    info = sm_parser._parse_identifier("sim_state-magazine_1991-05_344")
    assert info["year"] == 1991
    assert info["month"] == 5
    assert info["issue_number"] == "344"
    assert info["date_display"] == "May 1991"


def test_parses_compound_month_form():
    """sim_state-magazine_june-july-1991_345 → first month wins (June 1991)"""
    info = sm_parser._parse_identifier("sim_state-magazine_june-july-1991_345")
    assert info["year"] == 1991
    assert info["month"] == 6
    assert info["issue_number"] == "345"
    assert "June" in info["date_display"]
    assert "July" in info["date_display"]


def test_unparseable_identifier_returns_empty_year():
    """parse_corpus uses year=None as the 'skip this file' signal — keep it
    that way so a malformed filename doesn't crash a full build."""
    info = sm_parser._parse_identifier("this-is-not-a-state-mag-identifier")
    assert info["year"] is None


def test_single_digit_month_is_padded_in_display_only():
    """The month field stays an int; the date_display string is the
    human-readable form. Both must come back populated for a one-digit
    month identifier (e.g. June)."""
    info = sm_parser._parse_identifier("sim_state-magazine_1991-6_350")
    assert info["year"] == 1991
    assert info["month"] == 6
    assert info["date_display"] == "June 1991"
