# State Magazine — POC working directory

This directory holds the State Magazine adopter work as a proof-of-concept,
co-located with the toolkit for convenience. In production this code would
live in its own repo (e.g. `historyatstate/state-magazine`) — the toolkit
itself stays generic.

The Python files and this README are tracked in git. The extracted article
JSONs, your Anthropic API key, and `__pycache__/` are gitignored.

## What lives here

| File | Purpose |
|---|---|
| `extract_articles.py` | AI-assisted article extraction. Reads an IA bundle's `*.pdf` (or accepts a bare PDF path), asks Claude to identify article boundaries + metadata via a document content block, emits one JSON file per issue. Falls back to the Files API for PDFs larger than ~22 MB. |
| `parser.py` | Adopter-side `parse_corpus()` that joins extracted article JSON with issue metadata, computes IA URLs, emits toolkit events. |
| `categorize_subjects.py` | One-shot back-fill script. Used to add categories to articles JSONs produced by older versions of `extract_articles.py`. Not needed for new extractions — categories are now baked in at extraction time. |
| `articles_<issue-id>.json` | Output of `extract_articles.py` — one record per article. Consumed by `parser.py`. **Gitignored.** |
| `.anthropic_key` | Your Anthropic API key. **Gitignored.** Save as a single line, no quotes. |

## Running the extractor

```bash
# One-time setup
pip install anthropic
echo "sk-ant-..." > .anthropic_key

# Run on an IA bundle directory (must contain *.pdf and *_meta.xml):
python extract_articles.py /path/to/sim_state-magazine_1991-05_344
# Writes articles_sim_state-magazine_1991-05_344.json

# Or on a bare PDF (identifier derived from filename):
python extract_articles.py /path/to/sim_state-magazine_1991-05_344.pdf

# Skip the API call but verify the bundle is readable:
python extract_articles.py /path/to/bundle --dry-run
```

### Picking a model

| Issue characteristics | Model | Why | Approx cost |
|---|---|---|---|
| Up to ~50 pages, ≤ ~75k input tokens | `claude-haiku-4-5` | Fits comfortably in Haiku's 200k context; produces high-quality structured output; ~4× cheaper than Sonnet | ~$0.05/issue |
| Larger combined issues (60+ pages, > 100k input tokens) | `claude-sonnet-4-6` | Auto-attaches the `context-1m-2025-08-07` beta header for 1M context; reliable on long inputs | ~$0.30–$0.40/issue |

Pass the chosen model via `--model`; the default is `claude-sonnet-4-6`.
The 1M context beta header is attached automatically whenever the model
name starts with `claude-sonnet-`. The old OCR-based estimate of
~$0.25/issue is obsolete — PDFs bill at vision-tier (~1.5–2k tokens/page).

**Full archive on Haiku** (where it fits): ~$25–$40 for ~420 issues.
**Full archive on Sonnet**: ~$140–$170 for ~420 issues.
**Recommended in practice**: try Haiku first for any issue under ~75 pages;
fall back to Sonnet only when Haiku's 200k context is too small (the script
will surface a clear "prompt is too long" error in that case).

### Batch workflow: extracting many issues at once

For the full ~420-issue archive (or any large batch), use `batch_extract.py`.
It's a thin wrapper around `extract_articles.py` that adds three things the
single-issue script doesn't have:

- **Auto-discovery.** Point at a parent folder containing bundle subdirectories
  and it finds them all (`*_meta.xml` + `*.pdf` is the bundle signature).
  Unrelated PDFs in the same parent are ignored.
- **Resume.** Skips any issue whose `articles_<id>.json` already exists; pass
  `--force` to re-extract.
- **Cheapest-model-that-fits.** Tries Haiku 4.5 first (~4× cheaper than Sonnet).
  Auto-falls-back to Sonnet 4.6 with the 1M context beta on any "prompt is too
  long" error. The script tracks which model handled which issue.

```bash
# Discover and extract every IA bundle under a folder:
python data/state-magazine/batch_extract.py /path/to/state-magazine-issues/

# Dry-run (list what would be extracted, no API calls):
python data/state-magazine/batch_extract.py --dry-run /path/to/issues/

# Re-extract everything (overwrite existing JSONs):
python data/state-magazine/batch_extract.py --force /path/to/issues/

# Force a single model — skip the Haiku → Sonnet auto-fallback:
python data/state-magazine/batch_extract.py --model claude-sonnet-4-6 /path/to/issues/

# Tune concurrency (default 3 workers):
python data/state-magazine/batch_extract.py --workers 5 /path/to/issues/
```

Per-issue records (status, model used, duration, errors) are appended to
`batch_log.jsonl` so you can `grep '"status":"error"'` later if anything failed.
The Anthropic SDK retries transient 5xx / 429 internally with backoff, so
short-lived rate-limit blips are usually invisible.

**Rough budget for a 420-issue run**, assuming ~80 % fit Haiku:

- Haiku 4.5 (336 issues × ~$0.05): ~$17
- Sonnet 4.6 + 1M (84 issues × ~$0.40): ~$34
- **Total: ~$50**, wall time ~30–60 minutes at 3 workers

After the batch finishes, rebuild the catalog and splice into the publishing
tool (same as the single-issue workflow below).

### Repeatable workflow: extracting a new issue and refreshing the cache

```bash
# From the toolkit root (one directory up from here):

# 1. Extract the issue
python data/state-magazine/extract_articles.py \
    /path/to/sim_state-magazine_YYYY-MM_NNN \
    --model claude-haiku-4-5
# Writes data/state-magazine/articles_sim_state-magazine_YYYY-MM_NNN.json

# 2. Rebuild the catalog (events_cache.json + events_cache.js)
python build_cache.py --source-root data/state-magazine

# 3. Splice the refreshed cache into the publishing tool
python -c "
import merge_sources
from pathlib import Path
merge_sources._sync_html_embed(Path('events_cache.js'), Path('records-stage.html'))
"

# 4. Open the publishing tool in a browser to verify
open records-stage.html
```

The Streamlit app (`streamlit run app.py`) does steps 2 + 3 via Tab 5
buttons once the extraction (step 1) is done.

### Known gotchas

- **30k tokens/minute rate limit** on Sonnet at the entry usage tier — a
  single 80k-token PDF triggers an immediate 429. Either run on Haiku for
  PDFs that fit, or upgrade tier. Haiku has more generous limits.
- **API request size ≤ 32 MB** for inline base64. The script automatically
  switches to the Files API for PDFs > 22 MB raw — no action needed.
- **URL source fetches can time out** on large IA PDFs (Anthropic-side).
  The script prefers Files API over URL source for that reason.
- **Streaming required** for `max_tokens` ≥ ~20k (which we use for the rich
  schema). The script handles this internally via `client.messages.stream()`.

## Schema

Each article in the output JSON looks like:

```json
{
  "title": "Bush comes to Department to thank employees for Gulf effort",
  "subheading": "President's March 27 visit recognized Department's role",
  "author": "Jones, David",
  "page_start": 4,
  "page_end": 5,
  "summary": "President Bush visited the State Department on March 27 to personally thank employees for their efforts during the Persian Gulf War.",
  "text_excerpt": "President George Bush thanked Foreign Service and Civil Service employees personally on March 27 for their efforts during the Persian Gulf War, the President's first visit to the Department as Commander-in-Chief …",
  "media_type": "photo",
  "images": [
    {
      "page": 4,
      "type": "photograph",
      "caption": "President Bush addresses State Department employees in the Benjamin Franklin Room",
      "description": "Photograph of President George H.W. Bush at a podium in the Benjamin Franklin Room, gesturing with one hand to a State Department audience.",
      "alt_text_suggestion": "President Bush at a podium addressing State Department employees in the Benjamin Franklin Room"
    }
  ],
  "subjects": [
    {"name": "Persian Gulf War", "category": "Events & History"},
    {"name": "Presidential Visit", "category": "Events & History"}
  ]
}
```

Field notes:

- `page_start` / `page_end` are 1-indexed PDF positions (page 1 = front cover),
  not the printed page numerals.
- `text_excerpt` is a quoted snippet of the article's prose (100–300 words),
  not a paraphrase. Empty string when the piece is predominantly visual.
- `images` lists images *within the article* — not cover photos or department
  logos. Empty array for text-only pieces.
- `media_type` classifies the whole article visually. One of `""` (text),
  `"photo"`, `"illustration"`, `"chart"`, `"audio"`, `"video"`.
- `subjects` are tagged with one of seven high-level categories (Personnel,
  Posts & Geography, Operations, Events & History, Culture & Community,
  Health, Other) so the publishing tool can filter by topic group.

The parser (`parser.py`) maps each article to a toolkit event, using the
issue's publication month + year as the event date, the IA cover image as
the thumbnail URL, and IA's deep-link reader URL as the article URL.
Top-level `images` and an enriched `extra` (with subheading, text_excerpt,
page_end, etc.) are passed through so downstream consumers can project
headline-only, images-only, or text-only views as needed.
