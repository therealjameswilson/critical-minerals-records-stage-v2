"""
Config-driven scorer used by the web wrapper.

Reads ``scoring_config.json`` (a sibling file) and computes a weighted-axis
score from each event. The web UI writes the config; this module evaluates
it. Adopters who want to slider-tune scoring without writing Python should
use this scorer as their ``scorer.py``:

    # scorer.py
    from axis_scorer import score_event  # noqa: F401

For richer scoring (regex matching against title, cross-field arithmetic,
external lookups) write a custom ``scorer.py`` and ignore this module.

Config schema
=============

{
  "threshold": 0,
  "axes": [
    {
      "name": "Author seniority",
      "field": "extra.author_title",          # dotted path into the event
      "weights": {                            # exact-match map: value → score
        "Secretary": 40,
        "Director": 20
      },
      "default": 0
    },
    {
      "name": "Topic relevance",
      "field": "subjects",                    # list field — match by overlap
      "any_of": {                             # if event[field] ∩ set → score
        "Information Technology": 30,
        "Public Diplomacy": 30,
        "Communications": 20
      },
      "default": 0
    },
    {
      "name": "Cover story",
      "field": "extra.cover_story",
      "if_truthy": 10                         # numeric bonus if field is truthy
    },
    {
      "name": "Long form",
      "field": "extra.word_count",
      "at_least": [                           # threshold ladder, first match wins
        [4000, 10],
        [2000, 5]
      ],
      "default": 0
    }
  ]
}

The web UI exposes "weights", "any_of", "if_truthy", and "at_least" as
labeled sliders so an editor can retune without touching JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent / "scoring_config.json"


def score_event(event: dict) -> int:
    cfg = _load_config()
    total = 0
    for axis in cfg.get("axes", []):
        total += _axis_score(event, axis)
    return total


def threshold() -> int:
    """Convenience: read MIN_SCORE from the config (cache_format still wins
    if the adopter sets it explicitly there)."""
    return int(_load_config().get("threshold", 0))


def _axis_score(event: dict, axis: dict) -> int:
    value = _lookup(event, axis.get("field", ""))
    default = int(axis.get("default", 0))

    if "weights" in axis:
        return int(axis["weights"].get(value, default))

    if "any_of" in axis:
        if not value:
            return default
        if isinstance(value, (list, tuple, set)):
            hits = [axis["any_of"][v] for v in value if v in axis["any_of"]]
            return int(max(hits)) if hits else default
        return int(axis["any_of"].get(value, default))

    if "if_truthy" in axis:
        return int(axis["if_truthy"]) if value else default

    if "at_least" in axis:
        try:
            value_n = float(value or 0)
        except (TypeError, ValueError):
            return default
        for cutoff, points in sorted(axis["at_least"], reverse=True):
            if value_n >= cutoff:
                return int(points)
        return default

    return default


def _lookup(event: dict, path: str) -> Any:
    if not path:
        return None
    cur: Any = event
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


# Cache the parsed config keyed by file mtime. A live build scores tens of
# thousands of events; re-reading and re-parsing the JSON on every call (the
# old behavior) was pure overhead. Keying on mtime still picks up Streamlit
# slider saves immediately — the save bumps the mtime, so the next score
# reloads — without paying the parse cost per event.
_CONFIG_CACHE: dict = {"mtime": None, "data": {"threshold": 0, "axes": []}}


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"threshold": 0, "axes": []}
    mtime = CONFIG_PATH.stat().st_mtime
    if _CONFIG_CACHE["mtime"] != mtime:
        _CONFIG_CACHE["data"] = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        _CONFIG_CACHE["mtime"] = mtime
    return _CONFIG_CACHE["data"]


def write_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    _CONFIG_CACHE["mtime"] = None  # force reload on next score
