# Scoping a tool to a subject vocabulary

**Audience:** anyone building a Records Studio edition that covers one slice of
a larger corpus.
**Worked example:** the FRUS *Energy & Natural Resources* edition wired into
this repo.

---

## The idea

A corpus is usually broader than any single campaign needs. FRUS spans 182,000+
documents across war, trade, human rights, arms control, and dozens of other
themes. If your office runs an energy-policy campaign, you don't want the
diplomatic-history firehose — you want the energy thread pulled out of it.

The lever for that is the **subject vocabulary**. Records Studio already filters
events by a Category → Subcategory → Subject cascade. If you hand it a
vocabulary that *only* contains the subjects you care about, the tool narrows to
exactly that aspect of the corpus: the subject picker offers only those topics,
and — when the corpus carries per-document subject tags — the catalog itself can
be cut down to the documents those subjects touch.

So a subject-scoped edition is two choices:

1. **A subject vocabulary subset** — the controlled list of topics that defines
   the slice (here, the 23 subjects under *Energy and Natural Resources*).
2. **A corpus source** — where the documents come from, and how each document is
   matched to subjects in the vocabulary.

Everything else (scoring, the browse/draft/clear/export workflow, the HTML
shell) is unchanged. You're not building a new tool; you're aiming the existing
one at a theme.

---

## How the two pieces fit the seams

| Piece | Where it lives | What it controls |
|---|---|---|
| Subject vocabulary subset | a `taxonomy.json` (Subjects tab / `taxonomy.py`) | The subjects offered in the filter UI; the index space events map into. |
| Document → subject matching | the parser (`parser.parse_corpus`) | Which subjects each event carries; whether off-theme events are dropped. |

The vocabulary is the *definition* of the slice. The parser is what *applies* it
to real documents. They share the subject names, so the names a parser attaches
to an event resolve cleanly into the vocabulary's indices at build time.

A vocabulary alone narrows the **filter**. To also narrow the **catalog** —
"only energy documents" rather than "all documents, energy filter available" —
the corpus has to tell you which documents belong to the slice. For FRUS that
mapping is published separately (see below); for a corpus whose events already
carry their own `subjects`, the parser can simply drop events whose subjects
don't intersect the vocabulary.

---

## Worked example: FRUS Energy & Natural Resources

This repo is wired as that edition. Two inputs make it work:

- **`taxonomy-energy-natural-resources.json`** — the vocabulary subset: the
  single category *Foreign Economic Policy* → subcategory *Energy and Natural
  Resources*, with its 23 subjects (Oil, Petroleum and natural gas, Energy,
  Energy policy, Conservation, Environmental affairs, Pollution control,
  Solar/Wind/Ocean energy, Minerals and metals, Water, Natural resources, …).
  It's a strict subset of the full FRUS taxonomy, in the same schema, so it
  loads through the Subjects tab unchanged. `taxonomy.py` also loads it directly
  at build time.

- **The FRUS corpus on GitHub** plus the **`document_subjects.json`** mapping
  from `frus-subject-taxonomy`. FRUS volume XML doesn't carry subjects inline;
  the taxonomy project publishes a separate index of which documents each
  subject touches. The adapter (`data/frus/parser.py`) cross-references the two:
  for every document it reads, it looks up the energy subjects that document
  carries, attaches them, and **yields only documents that carry at least one**
  (and that clear the FRUS score threshold). That's what turns "all of FRUS"
  into "the ~22,000 energy documents."

### Build it

1. Launch the setup tool (`Start Tool.command`, or `streamlit run app.py`).
2. **Connect** tab → Step 2 → expand **"Fetch from a public GitHub repo"** →
   enter `historyatstate/frus`, then choose how to read it:
   - **Stream — no download** (recommended when disk is tight): the volumes are
     fetched over the network as the catalog builds and **nothing is stored on
     disk**. Only the energy-bearing volumes are fetched, one at a time, and
     discarded after parsing.
   - **Clone locally**: download a shallow copy to a temp folder once, then read
     from disk. Faster rebuilds, but needs room for the repo.
3. **Subjects** tab → upload `taxonomy-energy-natural-resources.json` (it reports
   23 subjects).
4. **Connect** tab → **Read my archive** to confirm energy events come back,
   then **Build & download** → build the catalog and add it to the publishing
   tool.

> Either way the build scans ~550 volumes, so it takes a few minutes. Streaming
> trades bandwidth and time for zero persistent storage — it re-fetches on every
> build rather than caching to disk. The subject mapping is read from a sibling
> `frus-subject-taxonomy` checkout, the `TAXONOMY_REPO_DIR` env var, or — failing
> both — fetched from GitHub.

### How streaming reads the corpus

The streaming source is written as `github:owner/name` (optionally
`github:owner/name@branch`) in the path field. The adapter already knows which
volumes contain energy documents (from `document_subjects.json`), so it fetches
exactly those volume XML files from `raw.githubusercontent.com`, parses each in
memory, keeps the handful of energy events, and moves on. Peak disk footprint is
the output catalog plus one volume held in memory — never the whole repo.

---

## Making a different slice

The pattern is reusable. To scope to a *different* theme of the same corpus,
swap the vocabulary subset and let the same adapter apply it:

1. Export the subcategory (or set of subjects) you want from the full taxonomy,
   in the same `categories → subcategories → subjects` schema — e.g. *Arms
   Control and Disarmament* or *Human Rights*. (The energy file was produced this
   way: filter the full `exports/taxonomy.json` to one subcategory, keep the
   matching `subjectIndex` entries.)
2. Point `taxonomy.py`'s `LOCAL_TAXONOMY_FILE` at the new file (or upload it in
   the Subjects tab).
3. Rebuild. The FRUS adapter keys off whatever subjects are in the loaded
   vocabulary, so no parser change is needed — the energy refs aren't
   hard-coded.

For a non-FRUS corpus whose events already carry `subjects`, you don't need a
separate document-subject index at all: load the vocabulary subset, and have the
parser keep only events whose `subjects` intersect it.

---

## What this does and doesn't change

- **Scoring is a separate, deliberate choice.** Scoping picks *which subjects*
  define the slice; *which documents are significant within it* is set by the
  scoring template you choose in the Tune scoring tab (e.g. "FRUS standard" —
  document type, participant prestige, classification). The parser emits neutral
  signals and does no scoring or filtering of its own. See
  [scoring-guide.md](scoring-guide.md).
- **The metadata-only constraint still holds.** Filtering is by subject *tag*,
  not document text — the catalog never stores document bodies. A subject-scoped
  edition narrows the tags on offer; it doesn't add full-text search. See
  [constraints.md](constraints.md).
- **The vocabulary is the contract.** Subjects present in events but absent from
  the loaded vocabulary simply don't appear in the filter. That's the mechanism,
  not a bug: the vocabulary is how you declare the slice.
