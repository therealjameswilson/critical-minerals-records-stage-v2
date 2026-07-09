#!/usr/bin/env python3
"""
extract_articles.py — AI-assisted article extraction from State Magazine PDFs.

Sends an Internet Archive issue PDF directly to Claude (via the Anthropic
SDK's document content block) and asks it to identify articles, metadata,
and visual context. The PDF reader sees the actual magazine layout —
headline typography, columns, photo placements, page numbers — so
extraction is sharper than running Claude over OCR plain text. In
particular, the `media_type` field can be set from what the page
actually looks like rather than guessed from captions.

USAGE

    # One-time setup: get an Anthropic API key + install the SDK
    pip install anthropic
    echo "sk-ant-..." > .anthropic_key   # gitignored

    # Run on an IA bundle directory (contains *.pdf and *_meta.xml):
    python extract_articles.py /path/to/sim_state-magazine_1991-05_344

    # Or pass a bare PDF (identifier comes from the filename):
    python extract_articles.py /path/to/sim_state-magazine_1991-05_344.pdf

    # Override output path:
    python extract_articles.py /path/to/issue --output /tmp/articles.json

    # Or use a different model:
    python extract_articles.py /path/to/issue --model claude-haiku-4-5-20251001

COST ESTIMATE (Claude Sonnet 4.6)

PDFs are billed as vision-tier images — roughly 1,500–2,000 tokens per
page. A 48-page State Magazine issue therefore runs ~85k input tokens
and ~5k output tokens: about **$0.30–$0.40 per issue**, compared with
~$0.25 for the OCR-text approach this script replaced. The quality
upside is materially better article boundaries, accurate `page_start`
(taken from the actual PDF position), and visually-grounded
`media_type`. A full archive of ~420 issues runs ~$140–$170 on Sonnet.

OUTPUT FORMAT

    [
      {
        "title": "Bush comes to Department to thank employees …",
        "subheading": "President's March 27 visit recognized …",
        "author": "Jones, David",
        "page_start": 4,
        "page_end": 5,
        "summary": "Short 1–2 sentence summary.",
        "text_excerpt": "First few paragraphs of the article …",
        "media_type": "photo",
        "images": [
          {
            "page": 4,
            "type": "photograph",
            "caption": "President Bush addresses employees …",
            "description": "Photograph of George H.W. Bush at a podium …",
            "alt_text_suggestion": "President Bush at a podium …"
          }
        ],
        "subjects": [
          {"name": "Persian Gulf War", "category": "Events & History"}
        ]
      },
      ...
    ]

Each issue produces 10–25 records. Downstream tools can project headline-only,
images-only, or text-only views by selecting the relevant fields per record.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


# ── The extraction prompt ────────────────────────────────────────────────────
# Designed to leverage the PDF's actual layout rather than just text content.
# Calls out media_type explicitly because the visual signal is the whole
# reason we're paying the PDF surcharge.

EXTRACTION_PROMPT = """You're extracting articles from an issue of *State Magazine*,
the U.S. Department of State's employee magazine. I've attached the issue's PDF —
read the pages directly. Use the layout (headline typography, columns, photos,
captions, sidebars, page numbers as printed) to identify article boundaries and
classify each piece.

For each substantial article, produce a JSON record with:

  - title               : the article's headline, in the case as printed
  - subheading          : the deck / subhead under the title, in the case as
                          printed; "" if none
  - author              : byline if visible (e.g. "Smith, Jane"); "" otherwise
  - page_start          : 1-indexed PDF position where the article begins
                          (1 = front cover, 2 = inside front / first inside
                          page, etc.). This is the position in the PDF, NOT
                          the printed page numeral on the page.
  - page_end            : 1-indexed PDF position where the article ends.
                          Same as page_start for a single-page article.
  - summary             : 1–2 sentence factual summary suitable for a search
                          result or hover card
  - text_excerpt        : 100–300 words of the article's actual prose, as a
                          single string. Quote from the opening paragraphs;
                          do not paraphrase. Strip pull-quotes and captions.
                          For very short pieces (notices, columns), the
                          entire body is fine. Empty string if the piece is
                          predominantly visual (e.g. a photo essay with only
                          brief captions).
  - media_type          : visual classification of the whole article — pick
                          EXACTLY one:
                            ""             text-only article (no significant image)
                            "photo"        one or more photographs anchor the article
                            "illustration" drawn artwork, cartoon, or non-photographic graphic
                            "chart"        data table, infographic, or statistical chart
                            "audio"        piece centered on music/recording
                            "video"        piece centered on broadcast/film
  - images              : array of image entries that appear within this
                          article (NOT the cover, NOT generic department-mark
                          logos). Empty array [] for text-only articles.
                          Each entry has:
                            page                — PDF page number where the image appears
                            type                — "photograph" | "illustration" | "chart"
                                                  | "diagram" | "map" | "cartoon"
                            caption             — the image's caption text as printed,
                                                  or "" if there is no caption
                            description         — 1–2 sentence factual description of what
                                                  the image actually shows. Be specific:
                                                  who, what, where, when if visible.
                            alt_text_suggestion — concise (≤ 200 chars) alt text ready
                                                  to use in a tweet, screen reader, or
                                                  accessibility caption. Describe the
                                                  image, not the article.
  - subjects            : 2–5 short topical tags as objects, each with:
                            name     — the tag text (e.g. "Awards", "Persian Gulf War")
                            category — pick EXACTLY one of:
                                "Personnel"           (awards, retirements, appointments, careers, training)
                                "Posts & Geography"   (embassies, countries, cities, posts, travel)
                                "Operations"          (IT, security, inspector general, administrative)
                                "Events & History"    (conferences, anniversaries, wars, milestones)
                                "Culture & Community" (arts, music, hobbies, profiles, community)
                                "Health"              (health programs, wellness, work-life)
                                "Other"               (only as a last resort)

EXCLUDE these non-article items (do not emit records for them):
  - Masthead, ISSN/publisher boilerplate, mailing instructions
  - "On the Cover" caption blocks (these describe the cover image only)
  - Letters to the Editor (skip individual letters; if you see a clearly
    edited "Letters" department with multiple letters, emit ONE record
    titled "Letters to the Editor" with a brief summary of themes)
  - Classified advertisements, calendar of events, brief announcements
  - One-paragraph appointment/retirement notices that just list names —
    UNLESS they're feature pieces about a particular individual

A typical State Magazine issue has 10–25 articles. Be inclusive of substantive
content; exclusive of filler. When you're unsure whether a sidebar is part of
the main article or a separate piece, follow the visual cue: a shared
headline + column flow = one article.

Output ONLY a JSON array. No preamble, no markdown fences, no commentary.
Start with `[` and end with `]`.
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def find_one(directory: Path, glob: str) -> Path:
    matches = list(directory.glob(glob))
    if not matches:
        raise FileNotFoundError(
            f"No file matching {glob!r} in {directory}. "
            f"Is this a complete Internet Archive bundle?"
        )
    if len(matches) > 1:
        # Prefer the issue PDF over derivatives (e.g. *_text.pdf if IA ever
        # adds one). The bundle convention is `<identifier>.pdf` matching the
        # directory name exactly.
        named = [p for p in matches if p.stem == directory.name]
        if named:
            return named[0]
        raise ValueError(
            f"Multiple {glob!r} in {directory}; expected exactly one or a "
            f"file matching the bundle's identifier."
        )
    return matches[0]


def find_pdf(target: Path) -> Path:
    """Accept either an IA-bundle directory or a bare PDF path."""
    if target.is_file() and target.suffix.lower() == ".pdf":
        return target
    if target.is_dir():
        return find_one(target, "*.pdf")
    raise FileNotFoundError(f"Not a PDF or bundle directory: {target}")


def identifier_for(target: Path, pdf_path: Path) -> str:
    """Derive the IA identifier (used to build article URLs)."""
    if target.is_dir():
        # Prefer the masthead/metadata file when it's available
        meta_candidates = list(target.glob("*_meta.xml"))
        if meta_candidates:
            try:
                root = ET.parse(meta_candidates[0]).getroot()
                ident = root.findtext("identifier")
                if ident and ident.strip():
                    return ident.strip()
            except ET.ParseError:
                pass
        return target.name
    # Bare PDF: use the filename stem
    return pdf_path.stem


def encode_pdf(pdf_path: Path) -> tuple[str, int]:
    raw = pdf_path.read_bytes()
    return base64.standard_b64encode(raw).decode("ascii"), len(raw)


# 32 MB is the API's request-size ceiling; base64 inflates ~33%, so we cap
# the raw size more conservatively. Above this we ask Claude to fetch the
# PDF by URL (Internet Archive hosts every issue at a stable path).
INLINE_PDF_MAX_BYTES = 22 * 1024 * 1024  # 22 MB → ~29 MB base64


def ia_pdf_url(identifier: str) -> str:
    """Public URL where IA exposes the issue PDF for download. Matches the
    same identifier-derived pattern used elsewhere in this adapter."""
    return f"https://archive.org/download/{identifier}/{identifier}.pdf"


def load_api_key(arg_key: str | None) -> str:
    if arg_key:
        return arg_key
    env = os.environ.get("ANTHROPIC_API_KEY")
    if env:
        return env.strip()
    sibling = Path(__file__).resolve().parent / ".anthropic_key"
    if sibling.exists():
        return sibling.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "Anthropic API key not found. Set ANTHROPIC_API_KEY, pass --key, "
        "or save the key to .anthropic_key in this directory."
    )


FILES_API_BETA = "files-api-2025-04-14"
CONTEXT_1M_BETA = "context-1m-2025-08-07"


def _new_client(api_key: str):
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise RuntimeError(
            "anthropic package not installed. Run: pip install anthropic"
        ) from e
    return Anthropic(api_key=api_key)


def upload_pdf_via_files_api(pdf_path: Path, api_key: str) -> str:
    """Upload a PDF via the Files API beta and return the file_id. Used
    for PDFs too large to inline as base64."""
    client = _new_client(api_key)
    with open(pdf_path, "rb") as fh:
        uploaded = client.beta.files.upload(
            file=(pdf_path.name, fh, "application/pdf"),
            extra_headers={"anthropic-beta": FILES_API_BETA},
        )
    return uploaded.id


def call_claude(document_source: dict, api_key: str, model: str) -> str:
    """Send the extraction prompt with a `document` content block. The
    caller decides between an inline base64 PDF (for small files) or a
    file_id reference (for large files uploaded via the Files API)."""
    client = _new_client(api_key)
    betas = []
    if document_source.get("type") == "file":
        betas.append(FILES_API_BETA)
    # Some combined issues tokenize past the default 200 k context window;
    # the 1M beta gives us headroom on any Sonnet 4.x model. Harmless when
    # the request is small.
    if model.startswith("claude-sonnet-"):
        betas.append(CONTEXT_1M_BETA)
    extra_headers = {"anthropic-beta": ",".join(betas)} if betas else {}
    # Bumped from 8 000 — the richer schema (subheading + text_excerpt +
    # images[] + per-subject category) runs ~600–900 output tokens per
    # article, so a 25-article issue needs ~20 k tokens of headroom.
    # At this output size the SDK requires streaming (otherwise the
    # non-streaming timeout calculator refuses to send the request).
    with client.messages.stream(
        model=model,
        max_tokens=32000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": document_source},
                {"type": "text", "text": EXTRACTION_PROMPT},
            ],
        }],
        extra_headers=extra_headers or None,
    ) as stream:
        final = stream.get_final_message()
    return final.content[0].text


def parse_json_response(text: str) -> list[dict]:
    """Tolerate accidental markdown fences if the model wraps the JSON."""
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*\n", t)
    if m:
        t = t[m.end():]
        t = re.sub(r"\n```\s*$", "", t)
    return json.loads(t)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("target", type=Path,
                    help="An IA bundle directory or a bare PDF path.")
    ap.add_argument("--output", type=Path, default=None,
                    help="Output JSON path (default: articles_<identifier>.json "
                         "in this script's directory).")
    ap.add_argument("--model", default="claude-sonnet-4-6",
                    help="Anthropic model to use (default: claude-sonnet-4-6)")
    ap.add_argument("--key", default=None,
                    help="API key (overrides ANTHROPIC_API_KEY and .anthropic_key)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Skip the API call; print stats and exit.")
    args = ap.parse_args()

    target = args.target.resolve()
    pdf_path = find_pdf(target)
    identifier = identifier_for(target, pdf_path)

    print(f"  PDF: {pdf_path}")
    print(f"  Identifier: {identifier}")
    raw_bytes = pdf_path.stat().st_size
    print(f"  PDF size: {raw_bytes:,} bytes")

    api_key_needed = not args.dry_run
    api_key = load_api_key(args.key) if api_key_needed else None

    # Pick a document source: inline base64 for small files (one round-trip,
    # no extra API surface) or a Files-API upload for large ones (avoids
    # the Messages API's 32 MB request-size limit; Anthropic-side URL fetch
    # tends to time out for large IA PDFs, so we don't rely on it).
    if raw_bytes <= INLINE_PDF_MAX_BYTES:
        pdf_b64, _ = encode_pdf(pdf_path)
        document_source = {
            "type": "base64",
            "media_type": "application/pdf",
            "data": pdf_b64,
        }
        source_desc = "inline base64"
    else:
        if args.dry_run:
            document_source = None  # type: ignore[assignment]
            source_desc = "Files API upload (skipped under --dry-run)"
        else:
            print(f"  Uploading PDF to Anthropic Files API …")
            file_id = upload_pdf_via_files_api(pdf_path, api_key)
            document_source = {"type": "file", "file_id": file_id}
            source_desc = f"Files API file_id={file_id}"

    print(f"  Document source: {source_desc}")

    if args.dry_run:
        print("\n  --dry-run: skipping API call.")
        return

    print(f"\n  Calling {args.model} with PDF document …")
    raw = call_claude(document_source, api_key, args.model)

    try:
        articles = parse_json_response(raw)
    except json.JSONDecodeError as e:
        print(f"\n  ✗ Couldn't parse model output as JSON: {e}", file=sys.stderr)
        print("\n  Raw response (first 1000 chars):", file=sys.stderr)
        print(raw[:1000], file=sys.stderr)
        sys.exit(1)

    out_path = args.output or (
        Path(__file__).resolve().parent / f"articles_{identifier}.json"
    )
    out_path.write_text(
        json.dumps(articles, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Light reporting so the operator can sanity-check before moving on
    media_counts: dict[str, int] = {}
    for art in articles:
        m = art.get("media_type") or ""
        media_counts[m] = media_counts.get(m, 0) + 1
    print(f"\n  ✓ Extracted {len(articles)} articles → {out_path}")
    if media_counts:
        print("  media_type distribution:")
        for m in sorted(media_counts):
            label = m or "(text)"
            print(f"    {label:14s} {media_counts[m]}")


if __name__ == "__main__":
    main()
