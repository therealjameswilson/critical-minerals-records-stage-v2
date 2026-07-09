"""
Persisted record of how the setup UI (app.py) wired up the toolkit.

Before this module, app.py inferred state by grepping parser.py / scorer.py for
magic substrings ("raise NotImplementedError", a specific repo literal,
"Stub Magazine", ...). That flipped on harmless reformatting and could not tell
a deliberately-stubbed branch from an unimplemented one.

The setup app now records its choices here explicitly. State lives in
``.toolkit_setup.json`` next to the modules. Source-based detection survives
only as a one-time bootstrap when the file is absent (see :func:`bootstrap`),
and is never used to decide whether to overwrite an adopter's file.
"""

from __future__ import annotations

import json
from pathlib import Path

_STATE_PATH = Path(__file__).resolve().parent / ".toolkit_setup.json"

# parser_mode values
GENERIC = "generic"   # generic JSON adapter (no-code path)
SAMPLE = "sample"     # examples/example_parser.py
CUSTOM = "custom"     # adopter-written parse_corpus()
STUB = "stub"         # shipped NotImplementedError stub (not implemented)

# Sentinel embedded in the shipped stub seam files. A real parser/scorer won't
# contain it, so its presence is a reliable "not implemented yet" signal that
# doesn't false-positive on a custom file that merely mentions NotImplementedError.
PARSER_STUB_SENTINEL = "TOOLKIT_PARSER_STUB"


def load() -> dict:
    if _STATE_PATH.exists():
        try:
            return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
    return {}


def save(**changes) -> dict:
    state = load()
    state.update(changes)
    _STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def parser_mode(parser_src: str | None = None) -> str:
    """Return the active parser mode, preferring the recorded state and falling
    back to a one-time source bootstrap. ``parser_src`` is the current text of
    parser.py (passed in so callers don't re-read the file)."""
    recorded = load().get("parser_mode")
    if recorded:
        return recorded
    return bootstrap(parser_src)


def bootstrap(parser_src: str | None) -> str:
    """Infer a mode from parser.py source when no state has been recorded yet.
    Best-effort and informational only — never gates a file overwrite."""
    if parser_src is None:
        return STUB
    if PARSER_STUB_SENTINEL in parser_src:
        return STUB
    if "generic_json_parser" in parser_src:
        return GENERIC
    if "Stub Magazine" in parser_src or "Worked example" in parser_src:
        return SAMPLE
    return CUSTOM
