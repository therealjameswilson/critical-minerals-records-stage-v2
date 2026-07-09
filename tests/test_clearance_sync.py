"""Tests for app.js_str — the JS-literal escaper that the setup tool uses to
inject adopter values into records-stage.html's CLEARANCE_DEFAULTS and
DRAFTED_BY regions. Also locks in the marker-substitution regex behavior so
a future change to the markers in records-stage.html doesn't silently break
the publishing-tool sync."""

import re

from app import js_str


def test_basic_string_is_quoted():
    assert js_str("hello") == '"hello"'


def test_double_quote_is_escaped():
    assert js_str('a "b" c') == '"a \\"b\\" c"'


def test_backslash_is_escaped():
    # Use a non-raw literal on the right so the expected value's backslashes
    # are unambiguous in the assertion.
    assert js_str("C:\\path") == '"C:\\\\path"'


def test_script_close_is_neutralized():
    """A value containing </script> must not be able to close the surrounding
    <script> tag in records-stage.html. The forward slash gets escaped."""
    out = js_str("hi </script><img src=x>")
    assert "</script>" not in out
    assert "<\\/script>" in out


def test_newline_is_escaped():
    assert js_str("a\nb") == '"a\\nb"'


def test_clearance_marker_regex_finds_and_replaces():
    """The two clearance markers in records-stage.html are matched by a
    DOTALL non-greedy regex in app.py. This fixture mirrors the markers' shape
    so a future tweak (e.g. dropping a space inside /* CLEARANCE_DEFAULTS */)
    fails here before it ever breaks the live HTML."""
    fixture = (
        "before block\n"
        "/* CLEARANCE_DEFAULTS */\n"
        "const DEFAULT_CLEARANCES = [];\n"
        "/* /CLEARANCE_DEFAULTS */\n"
        "in between\n"
        "/* DRAFTED_BY */\n"
        'const DEFAULT_DRAFTER = "";\n'
        "/* /DRAFTED_BY */\n"
        "after block\n"
    )
    new_clearance = (
        "\nconst DEFAULT_CLEARANCES = [\n"
        '  ["A/SKS/OH:", "", "Required Clearance"],\n'
        "];\n"
    )
    out, n = re.subn(
        r"(/\* CLEARANCE_DEFAULTS \*/)(.*?)(/\* /CLEARANCE_DEFAULTS \*/)",
        lambda m: f"{m.group(1)}{new_clearance}{m.group(3)}",
        fixture,
        count=1,
        flags=re.DOTALL,
    )
    assert n == 1
    assert '["A/SKS/OH:", "", "Required Clearance"]' in out

    new_drafter = f'\nconst DEFAULT_DRAFTER = {js_str("Jane — 555-0100")};\n'
    out2, n2 = re.subn(
        r"(/\* DRAFTED_BY \*/)(.*?)(/\* /DRAFTED_BY \*/)",
        lambda m: f"{m.group(1)}{new_drafter}{m.group(3)}",
        out,
        count=1,
        flags=re.DOTALL,
    )
    assert n2 == 1
    assert 'const DEFAULT_DRAFTER = "Jane — 555-0100"' in out2
