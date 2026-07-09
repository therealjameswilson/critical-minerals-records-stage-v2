# Toolkit Adoption Guide

A longer walkthrough of what an adopter does to stand up a working campaign
builder over their own archive. Pair this with `README.md` (orientation) and
`docs/data-contract.md` (schema reference).

---

## The seams, restated

The upstream FRUS toolkit interleaves FRUS-specific code with generic code.
This template marks the seams explicitly:

| Layer | Status | Who owns it |
|---|---|---|
| Cache schema (`MM-DD` keyed, score-sorted within day) | Generic | Toolkit |
| Compact JS encoding (taxonomy indices, classification extraction pattern) | Generic | Toolkit |
| HTML shell (date picker, draft generator, multi-tweet, char counter, image upload, alt text, clearance block, Word export) | Generic | Toolkit |
| Subject filter UI (Category → Subcategory → Subject cascade) | Generic if a taxonomy is provided | Toolkit |
| Cache-merge utility (incremental source-by-source updates) | Generic | Toolkit |
| Taxonomy loader with multi-source resolution | Generic | Toolkit |
| **Parser** (raw corpus → normalized events) | Adopter | You |
| **Scoring function** (event → integer score) | Adopter | You |
| **Taxonomy** (optional) | Adopter | You |
| Clearance-block defaults (which bureaus / approvers) | Customize | You (small HTML edit) |

---

## Step 1 — Decide what an "event" is in your corpus

An event is the smallest thing you'd surface in a single post. Examples:

- One FRUS document.
- One State Magazine article.
- One presidential trip.
- One administrative-history milestone.
- One declassified memo.

Events have **dates**, **titles**, and **URLs** as required fields. Everything
else is optional but useful for filtering and ranking.

If your corpus has nested structure (issues → articles, volumes → documents),
your parser walks the outer container and emits one event per inner item.

---

## Step 2 — Implement `parser.py`

The contract is one function:

```python
def parse_corpus(source_root: Path) -> Iterable[dict]:
    """Yield normalized event records. Schema in docs/data-contract.md."""
```

Implementation notes:

- **Yield, don't collect.** Large corpora shouldn't sit in memory.
- **One event per item.** No batching.
- **Don't score here.** Scoring is a separate concern. Emit events with no
  `score` field; `build_cache.py` will fill it in by calling your scorer.
- **`extra` is a free-form dict** for corpus-specific fields (author,
  department, classification, participants, etc.). The cache builder threads
  these through; the HTML tool surfaces a configurable subset.

See `examples/example_parser.py` for a worked tiny-corpus parser.

---

## Step 3 — Implement `scorer.py`

The contract is one function:

```python
def score_event(event: dict) -> int:
    """Return an integer score reflecting editorial significance."""
```

Implementation notes:

- **Score 0–100 is the convention**, not a requirement. Use whatever range
  works; the threshold is configurable.
- **Multiple axes recommended.** The upstream FRUS toolkit uses three (doc
  type 0–40, prestige 0–40, classification 0–10). State Magazine's proposed
  scoring uses four (author seniority, topic relevance, editorial salience,
  anniversary alignment). Pick what reflects what *your editor* would flag.
- **Set a threshold.** Documents below the threshold are excluded from the
  cache permanently. For small corpora (≲20k events), set this low (5–10);
  for large corpora (≳100k events), set it high enough that the cache stays
  manageable. See `cache_format.py`.

See `examples/example_scorer.py` for a worked example, and
`docs/scoring-guide.md` for axis-design recommendations.

---

## Step 4 — Optionally, implement `taxonomy.py`

If your corpus has a subject taxonomy (a controlled vocabulary of topics),
wire it in here. The HTML tool's Category → Subcategory → Subject cascade
will activate.

Two paths:

1. **Use a flat list** of subjects with categories. Easiest. See the
   `load_taxonomy()` stub.
2. **Use an external taxonomy export** (JSON files in another repo). The
   upstream FRUS toolkit does this for `frus-subject-taxonomy`. See the
   resolution-order pattern in the stub.

If you skip this entirely, the subject UI hides. No code changes needed.

---

## Step 5 — Build the cache

```bash
python build_cache.py
```

This:

1. Calls `parser.parse_corpus()` to walk your data.
2. Calls `scorer.score_event()` on each event.
3. Drops events below threshold (configurable in `cache_format.py`).
4. Calls `taxonomy.enrich()` if a taxonomy is present.
5. Writes `events_cache.json` (full fields, source of truth).
6. Writes `events_cache.js` (compact, embedded in the HTML tool).

If your corpus splits cleanly into independent sources, use
`merge_sources.py` to refresh one without rebuilding the whole cache.

---

## Step 6 — Customize the clearance block

The HTML tool's "Approvals & Clearances" block defaults to the upstream FRUS
toolkit's bureaus (A/SKS/OH, A/SKS, A/FO, D, etc.). These are almost certainly
wrong for your organization.

Open `records-stage.html`, search for `<!-- CLEARANCE_DEFAULTS -->`, and
replace the default rows with your organization's clearance chain. Status
options (Required Clearance, Info, Info\*, N/A) carry over without change.

---

## Step 7 — Test with five real events

Run end-to-end on five events you know well. Confirm:

- The parser emits each one.
- The scorer gives them sensible relative rankings.
- The HTML tool finds them by date, subject, and keyword.
- A draft tweet looks reasonable.
- Word export produces a usable document.

This is the calibration step. Expect to tune scoring weights at least once.

---

## What's deliberately not in the template

- **No backend.** Everything runs as static files plus a Python script for
  cache builds. If you need real-time ingestion or user accounts, that's a
  different system.
- **No full-text search.** Metadata-only cache. See `docs/constraints.md`.
- **No analytics.** The tool generates posts; it doesn't track them.
- **No multi-corpus dashboards.** One archive per instantiation.

---

## What if my archive doesn't have dates?

Then this toolkit doesn't fit. The entire design pivots on `MM-DD` keying.
Look for a different tool, or add publication dates to your corpus before
adopting.
