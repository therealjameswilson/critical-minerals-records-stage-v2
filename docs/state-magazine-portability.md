# State Magazine as a Portability Proof for the FRUS Toolkit

**Status:** Design proposal — no implementation on this branch.
**Audience:** Office of the Historian leadership (executive summary); engineers adopting the toolkit (technical sections).
**Branch:** `claude/state-magazine-toolkit-0flDF`.

---

## Executive Summary

The FRUS On This Day toolkit (this repo) turns a structured archive into Records Stage, a working social-media campaign tool: cache → score → faceted browse → drafted post → cleared and exported. It currently runs on FRUS plus seven auxiliary diplomatic-history datasets owned by the Office of the Historian.

This document proposes adapting the same toolkit to **State Magazine** — ~800 issues since 1989, with structured metadata (publication date, title, author, department, subjects) — as a **proof that the toolkit is portable**. State Magazine is the second test case, not the destination. If the adaptation works, the same pattern can be handed to any organization with a structured archive: a Treasury historian, a Pentagon archivist, a presidential library, a foreign ministry. They plug in their own data and scoring; they get a working campaign tool.

What this proves, concretely:

- The cache schema is **corpus-agnostic** — it doesn't know FRUS from State Magazine from anything else.
- The **scoring function is a seam**, not a fixture. Each adopter writes their own; the toolkit never has to know the editorial logic.
- **Records Stage** (date browse, subject filter, character counter, clearance block, Word export) is reusable as-is.
- The **adopter's effort** is bounded: a parser, a scorer, optionally a taxonomy. Days-to-weeks, not months.

The deliverable for the State Magazine instantiation is a working publishing tool (Records Stage) for ~16,000 articles (~800 issues × ~20 articles), driven by Magazine's own editorial scoring, packaged so a Magazine editor can use it without operating any of the underlying machinery.

---

## Why State Magazine

State Magazine is a strong second case for three reasons:

1. **Different shape from FRUS.** ~16,000 events vs. 172,000; near-uniform article structure vs. heterogeneous volume formats; modern editorial metadata (author, department) vs. archival classifications. If the toolkit accommodates this without architectural change, the portability claim is real.
2. **Same institutional context.** Same publisher, same approval chain, same audiences. The clearance block, the visual style, the campaign cadence all carry over without renegotiation.
3. **A real use case, not a contrivance.** Magazine has 35+ years of content that rarely resurfaces. A daily-or-weekly drip of "on this date in *State Magazine*" pulls institutional history into current conversation in exactly the way the FRUS tool already does for diplomatic documents.

---

## The Portability Thesis

The current codebase has FRUS-specific parts and generic parts mixed together. The portability work is mostly **identifying the seams**, not rewriting.

### What's generic (already)

| Component | File | Generic? |
|---|---|---|
| Cache schema (`MM-DD` keying, score-sorted within day) | `events_cache.json` | Yes |
| Compact JS encoding (subject indices, classification extraction) | `on_this_day.py` lines 617–640 | Yes |
| Records Stage shell (date picker, draft generator, multi-tweet, char counter, image upload, alt text, clearance block, Word export) | `records-stage.html` | Mostly — see below |
| Subject filter UI (Category → Subcategory → Subject cascade) | `records-stage.html` | Yes if a taxonomy is provided |
| Cache-merge utility (incremental source-by-source updates) | `merge_aux_sources_cache.py` | Yes |
| Taxonomy loader with multi-source resolution | `subject_taxonomy.py` | Yes |

### What's FRUS-specific

| Component | File | Why it's FRUS-specific |
|---|---|---|
| Document scoring (type 0–40, prestige 0–40, classification 0–10, threshold 30) | `on_this_day.py:_score_frus_document()` | Editorial weights — type, classification, participant prestige — only make sense for declassified diplomatic documents. |
| FRUS volume parser (regex over `<head>`, source notes, participant lists) | `on_this_day.py` | Format-specific. |
| Aux-source parsers (Travels, Visits, Countries, Conferences, Milestones, Admin Timeline) | `on_this_day.py` | Each is its own format. |
| Repo-clone step (`/tmp/otd_data/` from `github.com/historyatstate`) | `on_this_day.py` | Specific to OH-owned data on GitHub. |
| Compact-cache field set (`dt`, `cl`, `rp`, `co`, `tr`) | `on_this_day.py` | Some are FRUS-only (`dt`, `cl`, `rp`); some are aux-source-specific (`co`, `tr`). |
| Approval rows defaulting to A/SKS/OH, A/FO, P, etc. | `records-stage.html` | OH-internal clearance chain. |

### The data contract

An adopter — State Magazine, or any future fork — provides three things:

1. **A parser** that produces normalized event records:
   ```json
   {
     "source": "State Magazine",
     "date_display": "March 1995",
     "month": "03", "day": "15", "year": 1995,
     "title": "Diplomacy in the Digital Age",
     "description": "Feature article on emerging IT challenges...",
     "url": "https://state.gov/statemag/.../1995-03/digital-age.html",
     "score": 62,
     "subjects": ["Information Technology", "Public Diplomacy"],
     "extra": { "author": "Smith, Jane", "department": "IRM", "media": ["photo", "video"] }
   }
   ```
2. **A scoring function** that returns an integer score per event. Scoring is the **editorial seam** — what's significant in *this* corpus is the adopter's call.
3. **Optionally, a taxonomy** to drive subject filtering. If absent, the subject UI hides.

Everything else — the cache builder, the HTML shell, the campaign workflow, the export — is reused.

---

## State Magazine Instantiation

### Acquisition (TBD)

The data source for State Magazine is **deliberately left open** in this design. The acquisition strategy depends on what's already available internally vs. what would need to be built. Candidate approaches, in rough order of effort:

- **Internal export** — if Magazine has a CMS export (JSON/CSV/XML) covering the full archive, this is a same-day adoption. Strongly preferred.
- **Scrape `2009-2017.state.gov/statemag/`** — older HTML archive with structured pages. Cleaner parse, partial coverage.
- **Scrape `state.gov/statemag-archive/`** — modern PDF archive. Requires PDF text extraction; metadata quality varies; most coverage.
- **Hybrid HTML + PDF** — most complete; most engineering.

The toolkit doesn't care which path is chosen. The parser converts to the normalized schema; the cache builder is identical.

**Recommendation for v1:** start with whatever subset is easiest to acquire (likely the HTML archive), prove the end-to-end flow with ~5 years of content, then expand.

### Normalized schema

| Field | Type | Source in Magazine |
|---|---|---|
| `date_display` | string | Issue month/year ("March 1995") |
| `month`, `day`, `year` | int | Issue date (day = "01" if month-only) |
| `title` | string | Article title |
| `description` | string | Article summary or first paragraph |
| `url` | string | Permalink to the article |
| `source` | string | "State Magazine" |
| `subjects` | list | Department + topic tags |
| `extra.author` | string | Byline |
| `extra.department` | string | Bureau/office attribution |
| `extra.media` | list | "photo", "video", "audio" flags |

Two new compact-cache fields are needed for Magazine: `au` (author) and `dp` (department). Both are searchable in the HTML tool. This is a one-line addition to the compact-format builder.

### Recommended scoring function

State Magazine isn't FRUS — there are no classifications, document types, or participant lists. The editorial logic is different. Proposed weights, all **adjustable by the Magazine editor**:

| Axis | Range | Rationale |
|---|---|---|
| Author seniority | 0–40 | Secretary/Deputy = 40; Under/Assistant Secretary = 30; Ambassador or office director = 20; FSO/staff = 10; unattributed = 0. Senior bylines tend to mark policy-significant pieces. |
| Topic relevance | 0–30 | Configurable list of "current policy priorities" maintained by the editor. Direct subject match = 30; adjacent = 20; evergreen institutional = 10; unrelated = 0. |
| Editorial salience | 0–20 | Cover story = 10; feature length above a configurable word threshold = 5; multimedia present = 5. Proxies for what the editors themselves promoted. |
| Anniversary alignment | 0–10 | Boost when publication date aligns with a notable institutional anniversary or recurring observance (e.g. Foreign Service Day, FRUS centennial markers). |

**Total: 0–100. Recommended starting threshold: 35.**

This mirrors FRUS's three-axis structure (40+40+10 = 90, threshold 30) but reflects Magazine's editorial reality: there's no classification axis, but there is an author-seniority axis FRUS doesn't need (FRUS scores prestige via participants, not byline).

The threshold is a tuning knob. State Magazine's smaller corpus (~16,000 vs. 172,000) means filtering matters less for scale and more for ranking — the editor can run with a low threshold and rely on score-based sorting. Suggest revisiting after the first month of use.

### Taxonomy

Magazine has its own subject categories (Bureau-of-X, Foreign Service Life, Diplomacy Abroad, etc.). Two paths:

1. **Use Magazine's existing categories directly.** The taxonomy loader accepts any flat or two-level category list; no alignment to FRUS taxonomy required.
2. **Map Magazine subjects to the FRUS subject taxonomy where it makes sense.** Allows cross-corpus subject browsing in a unified tool. Higher upfront effort; no functional dependency.

**Recommendation for v1:** option 1. Keep State Magazine standalone. Cross-corpus alignment is a Phase 3 idea.

---

## The One Constraint That Crosses Every Adoption

Two of the three constraints I'd previously flagged are actually **per-adopter tuning knobs**, not architectural facts:

- The FRUS minimum score of 30 only matters because FRUS has 172k events. An adopter with 16k events can drop the threshold to zero.
- The 50 MB self-contained HTML only matters at FRUS's scale. State Magazine's cache will be a tenth the size; no scaling pressure.

**The constraint that crosses every adoption is: the cache stores metadata only, never document body text.** Searches in the HTML tool match titles, subjects, source labels, doc types, and classifications — never paragraphs. This is a deliberate architectural line (cache size, simplicity, predictable performance). Every adopter inherits it.

For State Magazine specifically, this means: a researcher cannot search "find me articles that mention NAFTA"; they can search "find me articles tagged Trade & Economic Affairs". If full-text search is required, that's a separate system, not this toolkit.

This constraint should be communicated explicitly to any adopter at handoff time, in the README of whatever template repo we package.

---

## Phased Build Plan

| Phase | Scope | Deliverable |
|---|---|---|
| 1 | **Extract the generic toolkit.** Identify and document the seams; isolate FRUS-specific code from generic code where currently entangled; write a `TOOLKIT_ADOPTION.md` describing the data contract. | Internal refactor + adopter-facing docs. No behavior change. |
| 2 | **State Magazine acquisition + parser.** Resolve the TBD acquisition decision; write `state_magazine.py` to produce normalized events. | `events_cache.json` augmented with State Magazine entries. |
| 3 | **State Magazine scoring + taxonomy.** Implement `_score_state_magazine_article()` per the recommended axes; load Magazine's subject categories. Iterate weights with the Magazine editor. | Scored, tagged events visible in the HTML tool. |
| 4 | **Records Stage integration.** Add Magazine-specific compact-cache fields (`au`, `dp`); surface author and department in the document lookup UI; smoke test on real issues with the Magazine team. | Working Records Stage; ~5 sample posts drafted by the Magazine editor in a working session. |
| 5 | **Package for handoff.** Spin out a template repo (`historyatstate/archive-toolkit-template` or similar) containing the generic shell, a stub parser, a stub scorer, and the adoption docs. State Magazine's instantiation lives alongside as a worked example. | A repo a third organization could fork. |

Phases 1–4 are the State Magazine adaptation. Phase 5 is the portability proof landing — the moment another organization can do this themselves.

---

## Risks and Open Questions

- **Acquisition risk.** Until the data source is decided, parser effort is unknown. Likeliest blocker.
- **Scoring weights need editorial input.** The proposed weights are defensible but not authoritative. The Magazine editor's review of the first 100 ranked articles will calibrate them faster than any analytical exercise.
- **Author seniority lookup.** The "0–40" axis presupposes a name → role mapping. Either the editor maintains a small list, or the parser pulls roles from each issue's masthead. Both are tractable; needs a decision.
- **Cross-corpus future.** If a later phase wants to put FRUS and State Magazine in one tool, the subject taxonomies need an alignment layer. Out of scope for this proposal.
- **Approval chain.** The current `records-stage.html` clearance block defaults to FRUS-side bureaus (A/SKS/OH, etc.). State Magazine's clearance chain is different. Need to either parameterize the default rows or maintain a Magazine-specific HTML build. Latter is cheaper.

---

## Appendix: Out of Scope

- **Research mode.** A separate proposal — `docs/frus-research-mode.md` on this branch — addresses FRUS-specific faceted-discovery needs for compilers. That work is **not** part of the State Magazine toolkit and **not** part of any future handoff. The toolkit being handed to other organizations is Records Stage, a social-media campaign tool, full stop.
- **Full-text search.** Out by architectural choice (see "The One Constraint").
- **AI-generated drafts at scale.** The existing Anthropic-API integration in `records-stage.html` carries over; no new design needed.
- **Multi-corpus dashboards.** A unified UI across FRUS + State Magazine + others is a separate product, not a portability question.
