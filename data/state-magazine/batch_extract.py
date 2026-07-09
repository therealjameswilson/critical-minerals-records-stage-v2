#!/usr/bin/env python3
"""
batch_extract.py — Run extract_articles.py across a folder of IA issue bundles.

Built for the full-archive run (~500 issues of State Magazine). Three things
the single-issue script doesn't do:

  1. **Auto-discover** issues. Accepts a parent directory containing bundles
     (e.g. `~/Downloads/state-magazine/`), or a list of explicit bundle
     directories / PDFs.
  2. **Resume.** Skips any issue whose `articles_<identifier>.json` is
     already on disk. Pass --force to re-extract.
  3. **Cheapest-model-that-fits.** Tries Claude Haiku 4.5 first (about 4×
     cheaper than Sonnet). If Haiku's 200k context isn't big enough for
     the issue ("prompt is too long" error), automatically falls back to
     Claude Sonnet 4.6 with the 1M context beta header for that one
     issue. Larger combined issues take the Sonnet path; everything
     else stays on Haiku.

Concurrent extractions run in a thread pool. The Anthropic SDK retries
transient 429s / 5xx internally with backoff; the script catches
non-recoverable failures, logs them, and keeps going.

USAGE

    # Extract every bundle or PDF under a folder:
    python batch_extract.py /path/to/state-magazine-issues/

    # Or pass explicit targets:
    python batch_extract.py /path/to/bundle1 /path/to/bundle2.pdf

    # Tune concurrency (default 3):
    python batch_extract.py --workers 5 /path/to/issues/

    # Force model (skip auto-fallback):
    python batch_extract.py --model claude-sonnet-4-6 /path/to/issues/

    # Re-extract issues that already have articles_*.json:
    python batch_extract.py --force /path/to/issues/

    # Dry-run: list what would be extracted, no API calls:
    python batch_extract.py --dry-run /path/to/issues/

OUTPUTS

  - articles_<identifier>.json per successful issue (same place as the
    single-issue script writes them)
  - batch_log.jsonl — one JSON line per issue with status, model used,
    duration, article count, errors. Appendable across runs.
  - Final stdout summary: OK / errors / total articles / rough cost.

COST ESTIMATE

  ~$0.05/issue on Haiku (most issues), ~$0.40/issue on Sonnet 1M
  (oversized combined issues). For 500 issues with ~10–20 % falling
  back to Sonnet, expect roughly $50–80 total.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

# Import the building blocks from the single-issue script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_articles as ex


OUTPUT_DIR = Path(__file__).resolve().parent
LOG_FILE = OUTPUT_DIR / "batch_log.jsonl"

PRIMARY_MODEL = "claude-haiku-4-5"
FALLBACK_MODEL = "claude-sonnet-4-6"

# Approximate billed rates ($/MTok). Used for the post-run cost estimate.
# Source: anthropic.com/pricing as of late 2025. Update if rates change.
PRICING = {
    "claude-haiku-4-5":  {"in": 1.00, "out": 5.00},
    "claude-sonnet-4-6": {"in": 3.00, "out": 15.00},
}

# Vision-tier billing for PDFs runs roughly 1.5–2k tokens/page. A 25 MB
# scan averages ~50 pages, so bytes-per-input-token comes out near 250.
# This is a rough heuristic for the cost estimate only — the real billed
# token counts are in the API response (response.usage), which the
# single-issue extractor doesn't currently surface. Refining this is
# easy follow-up if the estimate ends up too far off.
BYTES_PER_INPUT_TOKEN = 250
APPROX_OUTPUT_TOKENS_PER_ISSUE = 6_000


# ── Discovery ─────────────────────────────────────────────────────────────────

def discover_issues(targets: list[Path]) -> list[Path]:
    """Expand the user's command-line targets into a flat list of bundle
    directories or bare PDFs.

    Rules:
      - A bare PDF path (explicitly passed) → use as-is.
      - A directory that is itself an IA bundle (has `*_meta.xml` and
        `*.pdf` inside) → use as-is.
      - A directory that is not a bundle → walk one level, picking up
        only subdirectories that look like IA bundles. Bare PDFs at this
        level are intentionally skipped so pointing at a general dump
        (e.g. ~/Downloads) doesn't accidentally enqueue unrelated PDFs.
    """
    out: list[Path] = []
    for t in targets:
        t = t.resolve()
        if not t.exists():
            print(f"  ⚠ Skipping (not found): {t}", file=sys.stderr)
            continue
        if t.is_file() and t.suffix.lower() == ".pdf":
            out.append(t)
        elif t.is_dir():
            if _is_ia_bundle_dir(t):
                out.append(t)
            else:
                for child in sorted(t.iterdir()):
                    if child.is_dir() and _is_ia_bundle_dir(child):
                        out.append(child)
    return out


def _is_ia_bundle_dir(path: Path) -> bool:
    """Recognize the IA bundle shape: at least one `*.pdf` and one
    `*_meta.xml` file at the directory's top level."""
    return any(path.glob("*.pdf")) and any(path.glob("*_meta.xml"))


def already_extracted(issue_target: Path) -> Optional[Path]:
    """Return the existing articles_<id>.json path if one is already on
    disk for this issue, else None."""
    try:
        pdf = ex.find_pdf(issue_target)
    except Exception:
        return None
    identifier = ex.identifier_for(issue_target, pdf)
    out = OUTPUT_DIR / f"articles_{identifier}.json"
    return out if out.exists() else None


# ── Per-issue extraction ──────────────────────────────────────────────────────

def extract_one(issue_target: Path, api_key: str, model: str) -> dict:
    """Run a single-issue extraction. Returns a result dict."""
    started = time.time()
    pdf = ex.find_pdf(issue_target)
    identifier = ex.identifier_for(issue_target, pdf)
    out_path = OUTPUT_DIR / f"articles_{identifier}.json"
    raw_bytes = pdf.stat().st_size

    if raw_bytes <= ex.INLINE_PDF_MAX_BYTES:
        pdf_b64, _ = ex.encode_pdf(pdf)
        document_source = {
            "type": "base64",
            "media_type": "application/pdf",
            "data": pdf_b64,
        }
    else:
        file_id = ex.upload_pdf_via_files_api(pdf, api_key)
        document_source = {"type": "file", "file_id": file_id}

    raw_response = ex.call_claude(document_source, api_key, model)
    articles = ex.parse_json_response(raw_response)
    out_path.write_text(
        json.dumps(articles, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "status": "ok",
        "identifier": identifier,
        "model": model,
        "pdf_bytes": raw_bytes,
        "articles": len(articles),
        "duration_s": round(time.time() - started, 1),
        "output": str(out_path),
    }


def _is_context_overflow(e: Exception) -> bool:
    """True if the exception is the model's "this input is too big" signal.

    Prefer the typed/status signal (a 400 BadRequest from the API) and fall
    back to message matching, so a change in the SDK's exact wording doesn't
    silently disable the Haiku→Sonnet fallback."""
    status = getattr(e, "status_code", None) or getattr(e, "status", None)
    msg = str(e).lower()
    length_words = ("prompt is too long", "context window", "too long", "maximum context")
    if status == 400 and any(w in msg for w in length_words):
        return True
    return any(w in msg for w in ("prompt is too long", "context window"))


def extract_with_fallback(
    issue_target: Path, api_key: str, primary: str, fallback: str,
) -> dict:
    """Try `primary`; on a context-overflow failure, retry with `fallback`.
    Any other failure is returned as a structured error."""
    try:
        return extract_one(issue_target, api_key, primary)
    except Exception as e:
        if _is_context_overflow(e) and primary != fallback:
            try:
                result = extract_one(issue_target, api_key, fallback)
                result["fell_back_from"] = primary
                return result
            except Exception as e2:
                return {
                    "status": "error",
                    "identifier": issue_target.name,
                    "error": f"{primary}: {e}  |  {fallback}: {e2}",
                    "traceback": traceback.format_exc(),
                }
        return {
            "status": "error",
            "identifier": issue_target.name,
            "model": primary,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


# ── Cost estimate ─────────────────────────────────────────────────────────────

def estimate_cost(results: list[dict]) -> dict:
    """Rough total cost across successful extractions. Uses a constant
    bytes-per-token heuristic since the single-issue extractor doesn't
    surface response.usage. Good enough for "is this in the ballpark."""
    total = 0.0
    by_model: dict[str, dict] = {}
    for r in results:
        if r.get("status") != "ok":
            continue
        model = r.get("model")
        if model not in PRICING:
            continue
        in_tok = r["pdf_bytes"] / BYTES_PER_INPUT_TOKEN
        out_tok = APPROX_OUTPUT_TOKENS_PER_ISSUE
        rate = PRICING[model]
        cost = in_tok * rate["in"] / 1_000_000 + out_tok * rate["out"] / 1_000_000
        total += cost
        bucket = by_model.setdefault(model, {"issues": 0, "cost": 0.0})
        bucket["issues"] += 1
        bucket["cost"] += cost
    return {"total": total, "by_model": by_model}


# ── CLI / orchestration ───────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("targets", nargs="+", type=Path,
                    help="IA bundle directories, individual PDFs, or a parent "
                         "directory containing bundles.")
    ap.add_argument("--workers", type=int, default=3,
                    help="Concurrent extractions (default 3). Bump for Haiku, "
                         "drop to 1 if you're hitting Sonnet rate limits.")
    ap.add_argument("--model", default=None,
                    help=f"Force a specific model — skip the {PRIMARY_MODEL} → "
                         f"{FALLBACK_MODEL} auto-fallback.")
    ap.add_argument("--force", action="store_true",
                    help="Re-extract issues whose articles_<id>.json already exists.")
    ap.add_argument("--dry-run", action="store_true",
                    help="List what would be extracted; no API calls.")
    ap.add_argument("--key", default=None,
                    help="Anthropic API key (overrides .anthropic_key and env).")
    args = ap.parse_args()

    issues = discover_issues(args.targets)
    print(f"  Found {len(issues)} candidate issue(s).")
    if not issues:
        sys.exit(1)

    todo: list[Path] = []
    skipped: list[tuple[Path, Path]] = []
    for issue in issues:
        existing = already_extracted(issue) if not args.force else None
        if existing:
            skipped.append((issue, existing))
        else:
            todo.append(issue)
    print(f"  {len(skipped)} already extracted (use --force to re-run).")
    print(f"  {len(todo)} to extract.")
    if args.dry_run:
        for issue in todo[:20]:
            print(f"    • {issue.name}")
        if len(todo) > 20:
            print(f"    … and {len(todo) - 20} more")
        return
    if not todo:
        return

    api_key = ex.load_api_key(args.key)
    print(f"\n  Workers: {args.workers}")
    if args.model:
        print(f"  Model:   {args.model} (forced)")
    else:
        print(f"  Model:   {PRIMARY_MODEL} → {FALLBACK_MODEL} on context overflow")
    print()

    def runner(issue: Path) -> dict:
        if args.model:
            r = extract_one(issue, api_key, args.model)
        else:
            r = extract_with_fallback(
                issue, api_key, PRIMARY_MODEL, FALLBACK_MODEL,
            )
        # Append to log even on error so the operator can grep later.
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({**r, "ts": time.time()}) + "\n")
        return r

    started = time.time()
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as exe:
        futures = {exe.submit(runner, i): i for i in todo}
        for n, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            issue = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"status": "error", "identifier": issue.name, "error": str(e)}
            results.append(r)
            status = "✓" if r.get("status") == "ok" else "✗"
            fb = (f"  (fell back from {r['fell_back_from']})"
                  if r.get("fell_back_from") else "")
            err = f"  ERROR: {r.get('error', '')[:120]}" if r.get("status") != "ok" else ""
            print(
                f"  [{n:>3}/{len(todo)}] {status} {r.get('identifier', issue.name)} "
                f"({r.get('model', '?')}, "
                f"{r.get('articles', '-')} articles, "
                f"{r.get('duration_s', '-')}s){fb}{err}"
            )

    # ── Summary ──────────────────────────────────────────────────────────────
    elapsed = time.time() - started
    ok = sum(1 for r in results if r.get("status") == "ok")
    errored = len(results) - ok
    total_articles = sum(r.get("articles", 0) for r in results if r.get("status") == "ok")
    cost = estimate_cost(results)

    print()
    print(f"  ── Summary ────────────────────────────────────────────")
    print(f"  ✓ {ok} succeeded   ✗ {errored} failed")
    print(f"  Articles extracted: {total_articles:,}")
    print(f"  Wall time:          {elapsed/60:.1f} min")
    for model, b in sorted(cost["by_model"].items()):
        print(f"  {model}: {b['issues']} issue(s), ~${b['cost']:.2f}")
    print(f"  Estimated total cost: ~${cost['total']:.2f}")
    if errored:
        print()
        print(f"  See {LOG_FILE} for per-issue records (status='error' lines have")
        print(f"  the full traceback).")


if __name__ == "__main__":
    main()
