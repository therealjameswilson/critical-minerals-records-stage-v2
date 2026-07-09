# The Constraint That Crosses Every Adoption

**The cache stores metadata only — never document body text.**

This is architectural, not a TODO. Every adopter inherits it. If your use
case is "researcher wants to full-text-search the corpus," this toolkit
does not fit — that's a different system entirely (Elasticsearch /
OpenSearch / similar), with a meaningfully larger operating burden.

---

## What the cache can do

Search and filter on:

- Title
- Source label
- Subject (if a taxonomy is wired up)
- Year / date range
- Score
- Any adopter-defined `extra.*` field surfaced into the compact format
  (author, department, classification, document type, country, etc.)

These are the dimensions Records Stage exposes as facets and
keyword search.

## What the cache cannot do

- Match a search term against paragraph text inside any document.
- Match a search term against the volume / issue title (those are not in
  the cache; only IDs are).
- Find documents that "mention" an entity not in the title or subjects.
- Rank by semantic similarity.

A researcher who needs full-text search should be pointed at whatever the
source archive provides for that (e.g. for FRUS:
[history.state.gov](https://history.state.gov)). This toolkit hands them a
faceted catalog and a URL; following the URL gets them to the document
body.

---

## Why this constraint exists

Three reasons, in priority order:

1. **Cache size and embed feasibility.** The HTML tool embeds the compact
   cache so it can ship as one self-contained file with no backend. Adding
   document body text would push the embed past comfortable browser load
   times (and into the tens of GB on full FRUS).
2. **Predictable performance.** Metadata search is sub-millisecond in the
   browser. Full-text search at corpus scale needs an index — and an index
   needs a server.
3. **Architectural simplicity.** No ingestion pipeline beyond the cache
   build. No server to maintain. The artifact is a static file and a
   Python script.

These tradeoffs were chosen consciously. Adopters who'd prefer the
opposite tradeoff (full-text, server-backed, more powerful) should look at
purpose-built search platforms rather than adapt this template.

---

## Communicating it to users

The HTML tool should make this constraint visible — in the search hint
text, in the help panel, or in a "what can I search?" tooltip. Don't let
users guess. State Magazine adopters should expect a question like "why
can't I find articles about NAFTA?" — the answer is "search for *Trade
& Economic Affairs* (the subject tag), or click through to the article."

The README that ships with each adoption should restate this constraint
prominently. Adopter documentation that fails to flag it produces frustrated
users.

---

## Edge cases worth knowing

- **Subject names are searchable; subject indices are not.** The HTML tool
  expands indices back to names at render time and searches on names. If
  you change taxonomy names, the cache stays valid (indices don't move),
  but search behavior changes.
- **Adopter-defined extra fields ARE searchable** if they're surfaced into
  the compact format via `cache_format.COMPACT_EXTRA_FIELDS`. Plan
  accordingly: anything you'd want to grep is metadata, and metadata goes
  in the cache.
- **There is no "full-text-fallback to external service" plumbing in this
  toolkit.** If you wire one in, that's adopter-specific code, and it
  changes the cost-and-complexity profile substantially.
