"""Tests for html_embed.js_safe_dumps — the JSON escaper used to embed the
events cache inside the records-stage.html <script> block.

These lock in the two correctness rules that html_embed.py's module docstring
calls out (compact one-line output + JS-in-HTML escaping), so a future
refactor can't quietly break the splice or open a script-injection hole.
"""

import json

from html_embed import js_safe_dumps


def test_escapes_script_close():
    """A title literally containing </script> must not be able to close the
    surrounding <script> tag when embedded in HTML."""
    payload = [{"title": "Breaking: </script><img src=x onerror=alert(1)>"}]
    out = js_safe_dumps(payload)
    assert "</script>" not in out
    assert "\\u003c/script\\u003e" in out


def test_escapes_html_unsafe_chars():
    """<, >, & are escaped to \\u00XX so HTML parsers don't see element or
    entity boundaries inside the embedded JSON."""
    out = js_safe_dumps({"a": "<b>&'c'"})
    assert "<" not in out
    assert ">" not in out
    assert "&" not in out
    assert "\\u003c" in out
    assert "\\u003e" in out
    assert "\\u0026" in out


def test_escapes_unicode_line_separators():
    """U+2028 / U+2029 are valid JSON but terminate JS string literals when
    embedded in a <script> block. Must be escaped to \\u2028 / \\u2029."""
    s = "before" + chr(0x2028) + "middle" + chr(0x2029) + "after"
    out = js_safe_dumps({"s": s})
    assert chr(0x2028) not in out
    assert chr(0x2029) not in out
    assert "\\u2028" in out
    assert "\\u2029" in out


def test_compact_one_line_output():
    """The splice regex in html_embed matches a single-line declaration. If
    js_safe_dumps ever started emitting whitespace or newlines, the regex
    would need a rewrite — so lock the format here."""
    out = js_safe_dumps({"a": 1, "b": [2, 3], "c": {"d": 4}})
    assert "\n" not in out
    assert ": " not in out
    assert ", " not in out


def test_output_remains_valid_json():
    """The escapes are all valid JSON string escapes, so the output should
    still parse identically in the browser (and via json.loads here)."""
    payload = {"a": "<b>", "&": "x", "z": [1, 2, "</script>"]}
    out = js_safe_dumps(payload)
    assert json.loads(out) == payload
