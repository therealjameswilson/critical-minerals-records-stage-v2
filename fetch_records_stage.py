"""
Optional, legacy: refresh the Records Stage HTML shell from an upstream repo.

The toolkit ships its own copy of ``records-stage.html`` directly in this
repo. You don't need to run this script — the vendored copy is already
wired up.

⚠ The toolkit's ``records-stage.html`` has diverged from FRUS and is now a
maintained SUPERSET. It carries the IA-backed article-image gallery
(``eventImageGallery`` / ``attachIAImage`` + the ``/ia/fetch`` proxy route)
that lets adopters of Internet-Archive-hosted corpora (e.g. State Magazine)
attach page-scan images to tweets. The FRUS reference tool intentionally
does NOT have that feature — FRUS records are an embedded events cache of
document metadata, with no IA page-images to attach — so pulling from
``vak2ve/frus-otd`` would STRIP the gallery feature out of this toolkit.

Treat the two repos as separate. Only run this if you specifically want to
adopt a different upstream shell, and you understand it may remove
toolkit-only features. It downloads the upstream HTML, strips any embedded
data (``SUBJECT_TAXONOMY`` / ``EVENTS_CACHE`` become empty literals), and
overwrites ``records-stage.html`` in place. Re-run ``build_cache.py`` +
``merge_sources.py`` afterwards to splice your own cache back in.

Disabled by default. A bare run does NOTHING — it will not pull any HTML or
overwrite your file. There is no default upstream, so it cannot accidentally
fetch from FRUS. To do anything you must pass both ``--repo`` and ``--force``.

Even when forced, a feature-loss guard refuses to overwrite if the fetched
shell drops a toolkit-only feature (the IA gallery, ``/ia/fetch``, etc.) that
your current file has. Overriding that regression requires the additional,
deliberate ``--allow-feature-loss`` flag.

Usage:
    python fetch_records_stage.py                                   # no-op (safe)
    python fetch_records_stage.py --repo owner/shell --force        # adopt a shell
    python fetch_records_stage.py --repo owner/shell --force --allow-feature-loss
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

from html_embed import strip_embedded_data

UPSTREAM_REF_DEFAULT = "main"
UPSTREAM_PATH = "records-stage.html"

# Features that live only in this toolkit's HTML, not in the FRUS upstream.
# If a fetched shell lacks any of these but the current file has them,
# overwriting would regress the UI — so the fetch is blocked.
TOOLKIT_ONLY_MARKERS = ("eventImageGallery", "attachIAImage", "/ia/fetch")


def fetch(repo: str, ref: str) -> str:
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{UPSTREAM_PATH}"
    req = urllib.request.Request(url, headers={"User-Agent": "toolkit-template/1.0"})
    print(f"  GET {url}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read().decode("utf-8")
    print(f"  Fetched {len(data) / 1024 / 1024:.1f} MB")
    return data


def _lost_features(current: str, fetched: str) -> list[str]:
    """Toolkit-only markers present now but absent from the fetched shell."""
    return [m for m in TOOLKIT_ONLY_MARKERS if m in current and m not in fetched]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", default=None,
                    help="Upstream owner/repo to adopt a shell from. Required; there is "
                         "no default, so a bare run can't pull from FRUS or anywhere else.")
    ap.add_argument("--ref", default=UPSTREAM_REF_DEFAULT, help="Branch, tag, or SHA")
    ap.add_argument("--output", type=Path,
                    default=Path(__file__).resolve().parent / "records-stage.html")
    ap.add_argument("--force", action="store_true",
                    help="Required to actually fetch and overwrite. Without it the script "
                         "is a no-op — it pulls nothing and writes nothing.")
    ap.add_argument("--allow-feature-loss", action="store_true",
                    help="Override the guard that blocks overwriting when the fetched shell "
                         "drops a toolkit-only feature. Use only deliberately.")
    args = ap.parse_args()

    # Protective default: never pull or overwrite without an explicit opt-in.
    if not (args.repo and args.force):
        print(
            "fetch_records_stage.py is disabled by default — it pulled nothing and\n"
            "wrote nothing.\n\n"
            "This toolkit's records-stage.html is a maintained superset (it includes the\n"
            "IA article-image gallery) and is NOT meant to be refreshed from FRUS; doing so\n"
            "would strip toolkit-only features. To intentionally adopt a different upstream\n"
            "shell, opt in explicitly:\n\n"
            "    python fetch_records_stage.py --repo <owner/repo> --force\n"
        )
        if args.repo and not args.force:
            print("(You passed --repo but not --force, so nothing was fetched or written.)\n")
        return 0

    html = fetch(args.repo, args.ref)
    html, stats = strip_embedded_data(html)

    # Feature-loss guard: refuse to regress the current file unless forced.
    if args.output.exists():
        lost = _lost_features(args.output.read_text(encoding="utf-8"), html)
        if lost and not args.allow_feature_loss:
            print(
                "\n  ✗ Refusing to overwrite. The fetched shell is missing feature(s) your\n"
                f"    current records-stage.html has: {', '.join(lost)}.\n"
                "    Overwriting would regress the UI, so nothing was written.\n"
                "    If you truly intend to adopt the feature-poorer shell, re-run with\n"
                "    --allow-feature-loss.\n"
            )
            return 2

    if not stats["taxonomy_found"]:
        print("  ⚠ SUBJECT_TAXONOMY const not found upstream — upstream HTML changed?")
    if not stats["cache_found"]:
        print("  ⚠ EVENTS_CACHE const not found upstream — upstream HTML changed?")
    args.output.write_text(html, encoding="utf-8")
    final_kb = args.output.stat().st_size / 1024
    print(
        f"  ✓ Wrote {args.output} ({final_kb:.0f} KB after stripping "
        f"{(stats['taxonomy_bytes'] + stats['cache_bytes']) / 1024 / 1024:.1f} MB of data)"
    )
    print(
        "\nNext steps (if you haven't already done these):\n"
        "  1. Run `python build_cache.py --source-root <your-corpus>` to produce events_cache.js.\n"
        "  2. Run `python merge_sources.py --only <source>` to splice it into the HTML\n"
        "     (or edit the two const lines by hand).\n"
        "  3. Update the CLEARANCE_DEFAULTS and DRAFTED_BY blocks for your organization.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
