"""Tests for the FRUS Energy adapter (data/frus/parser.py).

The parser detects neutral signals and yields *every* energy document — it does
no scoring and no threshold filtering (that's the user's call, in the Tune
scoring tab). These tests need neither a FRUS clone nor the taxonomy export.
"""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "frus_energy_parser_test", ROOT / "data" / "frus" / "parser.py"
)
frus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(frus)


# --- neutral signal extraction (no scoring) --------------------------------


def test_signals_memcon_with_president():
    s = frus._extract_document_signals(
        "Memorandum of Conversation", "The President; The Secretary of State", "Top Secret"
    )
    assert s["doc_type"] == "Memorandum of Conversation"
    assert "The President" in s["participant_roles"]
    assert "Secretary of State" in s["participant_roles"]
    assert s["classification"] == "Top Secret"


def test_signals_routine_doc():
    s = frus._extract_document_signals("Circular", "A clerk", "")
    assert s["doc_type"] == "Document"      # default label, no score
    assert s["participant_roles"] == []
    assert s["classification"] == ""        # unclassified -> empty


def test_parse_iso_date():
    assert frus.parse_iso_date("1862-07-04T00:00:00-05:00") == (7, 4)
    assert frus.parse_iso_date("1945-08-14") == (8, 14)
    assert frus.parse_iso_date("1970") is None
    assert frus.parse_iso_date("") is None


# --- parse_corpus: energy filter, but NO score filter ----------------------


def _write_volume(volumes_dir: Path, vol_id: str):
    """A volume with a high-signal energy doc, a routine energy doc, and a
    non-energy doc."""
    xml = f"""<?xml version="1.0"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0" xmlns:frus="http://history.state.gov/frus/ns/1.0">
<teiHeader><date type="publication-date" when="2016">2016</date></teiHeader>
<text><body>
<div subtype="historical-document" xml:id="d5" frus:doc-dateTime-min="1862-07-04T00:00:00">
<head>Memorandum of Conversation, by the Secretary of State</head>
<note type="source">Source: NARA. Top Secret.</note>
<list type="participants"><item>The President</item></list></div>
<div subtype="historical-document" xml:id="d6" frus:doc-dateTime-min="1862-09-02T00:00:00">
<head>Circular Telegram to Certain Posts</head>
<note type="source">Source: NARA.</note></div>
<div subtype="historical-document" xml:id="d9" frus:doc-dateTime-min="1862-08-09T00:00:00">
<head>Routine Note</head><note type="source">Source: NARA.</note></div>
</body></text></TEI>"""
    (volumes_dir / f"{vol_id}.xml").write_text(xml, encoding="utf-8")


def test_parse_corpus_keeps_all_energy_docs_regardless_of_significance(tmp_path, monkeypatch):
    vol_id = "frus1862"
    volumes = tmp_path / "volumes"
    volumes.mkdir()
    _write_volume(volumes, vol_id)

    # d5 (high-signal) and d6 (routine) are energy; d9 is not.
    monkeypatch.setattr(
        frus, "load_energy_doc_map",
        lambda: {(vol_id, "d5"): ["Oil"], (vol_id, "d6"): ["Energy"]},
    )

    events = list(frus.parse_corpus(tmp_path))
    by_url = {e["url"].rsplit("/", 1)[1]: e for e in events}

    # Both energy docs come through — the routine one is NOT dropped here.
    assert set(by_url) == {"d5", "d6"}

    memcon = by_url["d5"]
    assert memcon["extra"]["doc_type"] == "Memorandum of Conversation"
    # "The President" (participant) + "Secretary of State" (from the head text).
    assert memcon["extra"]["participant_roles"] == ["The President", "Secretary of State"]
    assert memcon["extra"]["classification"] == "Top Secret"
    assert "frus_score" not in memcon["extra"]  # parser does not score

    routine = by_url["d6"]
    assert routine["extra"]["doc_type"] == "Document"
    assert routine["extra"]["participant_roles"] == []
    assert routine["extra"]["classification"] == ""


def test_parse_corpus_empty_when_no_map(tmp_path, monkeypatch):
    (tmp_path / "volumes").mkdir()
    monkeypatch.setattr(frus, "load_energy_doc_map", lambda: {})
    assert list(frus.parse_corpus(tmp_path)) == []


def test_parse_corpus_streaming_reads_over_http_without_disk(tmp_path, monkeypatch):
    """github: source streams volume XML in memory — no local files written."""
    import github_fetch

    vol_id = "frus1862"
    volumes = tmp_path / "volumes"
    volumes.mkdir()
    _write_volume(volumes, vol_id)
    xml_text = (volumes / f"{vol_id}.xml").read_text(encoding="utf-8")

    monkeypatch.setattr(frus, "load_energy_doc_map", lambda: {(vol_id, "d5"): ["Oil"]})
    monkeypatch.setattr(github_fetch, "default_branch", lambda o, n, **k: "master")

    fetched = []

    def fake_fetch_text(owner, name, path, ref, **k):
        fetched.append((owner, name, path, ref))
        if path == f"volumes/{vol_id}.xml":
            return xml_text
        raise FileNotFoundError(path)

    monkeypatch.setattr(github_fetch, "fetch_text", fake_fetch_text)

    events = list(frus.parse_corpus("github:historyatstate/frus"))
    assert len(events) == 1
    assert events[0]["url"].endswith(f"{vol_id}/d5")
    assert fetched == [("historyatstate", "frus", f"volumes/{vol_id}.xml", "master")]


# --- the FRUS-standard template reproduces FRUS's original numbers ----------


def test_frus_standard_template_reproduces_original_scores(monkeypatch):
    import axis_scorer

    preset = json.loads(
        (ROOT / "scoring_presets" / "frus_standard.json").read_text(encoding="utf-8")
    )
    monkeypatch.setattr(axis_scorer, "_load_config", lambda: preset)

    # MemCon (40) + The President via any-of max (40) + Top Secret (10) = 90.
    memcon = {
        "extra": {
            "doc_type": "Memorandum of Conversation",
            "participant_roles": ["The President", "Secretary of State"],
            "classification": "Top Secret",
        }
    }
    assert axis_scorer.score_event(memcon) == 90

    # A routine, unclassified document with no senior participants: doc_type
    # default 2, nothing else. Below the template's threshold of 30.
    routine = {"extra": {"doc_type": "Document", "participant_roles": [], "classification": ""}}
    assert axis_scorer.score_event(routine) == 2
    assert axis_scorer.threshold() == 30
