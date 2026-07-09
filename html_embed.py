"""
Single source of truth for embedding generated data into records-stage.html.

The compact cache (events_cache.js) declares two JS globals:

    const SUBJECT_TAXONOMY = [...];
    const EVENTS_CACHE = {...};

build_cache.py writes them, merge_sources.py and app.py splice them into the
<script> block of records-stage.html, and fetch_records_stage.py blanks them
out when pulling a fresh upstream shell. Keeping the patterns and the escaping
in one place is what lets the writer and every reader stay byte-compatible —
previously these regexes were copy-pasted into four modules.

Two correctness rules live here:

  1. Single-line declarations + greedy, non-DOTALL matching. ``json.dumps`` with
     compact separators emits no newlines, so each ``const X = ...;`` is exactly
     one line. Matching greedily to the last ``};`` / ``];`` on that line is
     robust to values that themselves contain ``};`` or ``];`` (a non-greedy or
     DOTALL pattern truncates on the first such occurrence inside a title).

  2. JS-in-HTML escaping. The data lands inside a raw <script> element, so
     ``<``, ``>`` and ``&`` are escaped to their ``\\u00XX`` forms (plus
     U+2028 / U+2029, which are valid JSON but terminate JS string literals).
     This prevents a title like ``</script>`` from breaking out of the script
     context. The escapes are valid JSON string escapes, so the embedded text
     still parses identically in the browser.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Greedy + no DOTALL: matches the whole single-line declaration even when a
# value contains "};" / "];". See rule (1) above.
TAX_RE = re.compile(r"const SUBJECT_TAXONOMY = \[.*\];")
CACHE_RE = re.compile(r"const EVENTS_CACHE = \{.*\};")

# Empty-literal forms used when stripping a freshly fetched upstream shell.
EMPTY_TAX = "const SUBJECT_TAXONOMY = [];"
EMPTY_CACHE = "const EVENTS_CACHE = {};"

# Characters that are valid JSON but unsafe in a <script> block. The last two
# are U+2028 / U+2029 (line/paragraph separators), built via chr() so this
# source file contains no raw control characters of its own.
_JS_STRING_UNSAFE = {
    "<": "\\u003c",
    ">": "\\u003e",
    "&": "\\u0026",
    chr(0x2028): "\\u2028",
    chr(0x2029): "\\u2029",
}


def js_safe_dumps(obj) -> str:
    """Compact JSON, escaped so it is safe to embed inside a <script> block."""
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    for needle, repl in _JS_STRING_UNSAFE.items():
        text = text.replace(needle, repl)
    return text


def sync_html_embed(js_file: Path, html_file: Path) -> bool:
    """Replace the embedded SUBJECT_TAXONOMY / EVENTS_CACHE in ``html_file``
    with the values from ``js_file``. Returns True on a successful two-part
    splice, False if either declaration couldn't be located in either file.

    Uses function replacements (not template strings) because the matched
    text contains backslash escapes from :func:`js_safe_dumps`, which ``re``
    would otherwise try to interpret as backreferences.
    """
    js_text = js_file.read_text(encoding="utf-8")
    tax_match = TAX_RE.search(js_text)
    cache_match = CACHE_RE.search(js_text)
    if not tax_match or not cache_match:
        return False

    html_text = html_file.read_text(encoding="utf-8")
    html_text, n1 = TAX_RE.subn(lambda _m: tax_match.group(0), html_text, count=1)
    html_text, n2 = CACHE_RE.subn(lambda _m: cache_match.group(0), html_text, count=1)
    if not (n1 and n2):
        return False
    html_file.write_text(html_text, encoding="utf-8")
    return True


def strip_embedded_data(html: str) -> tuple[str, dict]:
    """Replace embedded data with empty literals. Returns ``(html, stats)``
    where stats reports how many bytes were stripped and whether each
    declaration was found (callers warn on a missing one)."""
    stats = {
        "taxonomy_bytes": 0,
        "cache_bytes": 0,
        "taxonomy_found": False,
        "cache_found": False,
    }

    tax_m = TAX_RE.search(html)
    if tax_m:
        stats["taxonomy_bytes"] = len(tax_m.group(0))
        stats["taxonomy_found"] = True
        html = TAX_RE.sub(lambda _m: EMPTY_TAX, html, count=1)

    cache_m = CACHE_RE.search(html)
    if cache_m:
        stats["cache_bytes"] = len(cache_m.group(0))
        stats["cache_found"] = True
        html = CACHE_RE.sub(lambda _m: EMPTY_CACHE, html, count=1)

    return html, stats
