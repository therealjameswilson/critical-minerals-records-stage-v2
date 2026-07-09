# Building the Records Stage Annex

`build_annex_stage.py` combines several already-built Records Stage caches into
one **`records-stage-annex.html`** — a companion "appendix" instance that
gathers secondary / supplementary source collections behind the main **OH
Records Stage**. Where each sibling instance carries a single corpus, the Annex
is a *reference shelf*: one tool where an editor can browse across every
supporting collection at once, filtering by source.

Out of the box it merges the three siblings:

| Collection | Cache | Source chips | Events |
|---|---|---|---|
| Founders Online | `founders_events_cache.js` | Washington / Jefferson / Madison / Adams / Hamilton / Franklin / Jay Papers | 183,500 |
| Federal Register | `fr_events_cache.js` | State Department, Presidential Documents | 19,690 |
| The Reagan Diaries | `reagan_events_cache.js` | The Reagan Diaries | 2,500 |
| **Annex total** | | **10 chips** | **205,690** |

The result is the standard Records Stage UI (preset campaign builder, clearance
editor, Word export, the NARA + Wikimedia Commons + Library of Congress image
modal) titled **"Records Stage — Annex"**, carrying all three collections with
each source as its own filter chip.

> The Annex is a *gathering*, not a fourth corpus. It does not re-parse any
> source data — it reads the compact caches the sibling builders already produced
> and unions them. It also does **not** include the main OH / FRUS content; it is
> the shelf of *other* resources that sits behind it.

---

## Build

The three sibling caches must exist first (each is gitignored and regenerable —
run its builder if missing):

```bash
python build_founders_stage.py      # writes founders_events_cache.js
python build_fr_cache.py            # writes fr_events_cache.js
python build_reagan_stage.py        # writes reagan_events_cache.js
```

Then merge:

```bash
python build_annex_stage.py
```

Output:

```
  events: 205690
  source_chips: 10
  days_with_events: 366
  taxonomy_subjects: 646
  ✓ records-stage-annex.html written (38.8 MB)
```

`--no-html-sync` builds the merged cache only; `--html`, `--json-out`,
`--js-out` override the output paths.

> **Size.** At ~39 MB the Annex is the largest instance (it is essentially
> Founders Online plus two smaller collections). That is inherent to embedding
> 205k events in a single self-contained file — the same trade every instance
> makes, just at the sum of three.

---

## How the merge stays correct

Each cache declares two JS globals: `SUBJECT_TAXONOMY` and `EVENTS_CACHE`
(compact, keyed by `MM-DD`). The merge:

- **Events** — unions the day buckets (concatenates each `MM-DD`'s event list),
  then sorts each day by year for a stable cache (the browser re-sorts anyway).
  Heterogeneous event shapes are fine: Founders/Reagan events are `{y,t,u,s}`;
  Federal Register events additionally carry `dt` (doc type), `sc` (score),
  `sb` (subject indices), `pr`, `eo`, etc. The shell reads every field
  defensively, so extra keys on some sources and not others cause no problem.

- **Taxonomy** — concatenates every source's `SUBJECT_TAXONOMY`, and shifts each
  source's per-event subject indices (`sb`) by the offset where that source's
  taxonomy lands in the combined list. Today only the Federal Register carries a
  taxonomy (646 subjects); Founders and Reagan contribute none and carry no
  `sb`. The offset math is what keeps this **correct when you add a second
  tagged source** — its indices are rebased onto the combined taxonomy rather
  than colliding with the first source's.

Because every source label auto-discovers into a filter chip (the shell appends
any label not in `SOURCE_META` with a neutral `badge-generic`), the 10 chips
appear with **no edit to the shared `records-stage.html`**.

---

## What the merge implies for the reader

- **Filtering is by source chip.** Turn collections on/off to scope a day to,
  say, just the Reagan Diaries or just the Founders editions.
- **Subject/topic filtering only bites on Federal Register events** — they are
  the only tagged ones. Founders/Reagan events show no subject tags and are
  unaffected by a subject filter (same as in their standalone instances).
- **Search spans everything**, but note each collection's own caveat carries
  over: Founders is title-only, Reagan searches the full entry prose (verbatim
  shorthand), Federal Register searches document titles.
- **On busy days, Founders dominates.** A single `MM-DD` can hold thousands of
  Founders documents beside a handful of Federal Register / Reagan items; use the
  source chips to cut through. (The shell renders large days in chunks.)

---

## Adding another collection to the Annex

The Annex is designed to grow — that's the point of an appendix.

1. Build the new collection's compact cache with any `build_*_stage.py` (or
   `build_cache.py`) so it emits a `<name>_events_cache.js` with the standard
   `SUBJECT_TAXONOMY` / `EVENTS_CACHE` globals and a distinct `source` label on
   every event.
2. Either add its path to the `SOURCES` list at the top of
   `build_annex_stage.py`, or pass it ad hoc:

   ```bash
   python build_annex_stage.py \
     --cache founders_events_cache.js \
     --cache fr_events_cache.js \
     --cache reagan_events_cache.js \
     --cache my_new_events_cache.js
   ```
3. Re-run the build. The new source becomes another filter chip; if it carries
   its own taxonomy, its subjects are appended and its `sb` indices rebased
   automatically.

---

## Rebuilding

Fully regenerable — delete `records-stage-annex.html` and the two
`annex_events_cache.*` files and re-run `python build_annex_stage.py` (after the
sibling caches exist). The build always starts from the current vendored
`records-stage.html`, so any fix already in that shell is inherited on the next
build.

---

## Optional follow-up: distinct source badges

All 10 sources currently share the neutral `badge-generic` (exactly how they
look in each standalone instance). If you want the Annex to visually distinguish
the collections — e.g. one color family for the founders, another for the
Federal Register, another for Reagan — that is a small, deliberate edit to the
shared shell: add `SOURCE_META` entries (`short` / `badge` / `abbr`) and matching
`.badge-*` CSS in `records-stage.html`. It's left out of the default build
because it touches the shared shell that every instance rebuilds from.
