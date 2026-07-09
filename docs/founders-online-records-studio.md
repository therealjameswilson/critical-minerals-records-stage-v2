# Building "Founders Online — Records Stage" in Records Studio

A step-by-step walkthrough for building the Founders Online instance using
**Records Studio** — the Streamlit wizard (`app.py`) — instead of the
command-line builder.

> **Two paths to the same tool.** `build_founders_stage.py` is the
> one-command, reproducible builder (see
> [`docs/founders-online-build.md`](founders-online-build.md)). **This** doc
> shows the equivalent build through the Records Studio UI — the right path
> for a non-technical adopter (editor, archivist, librarian) who would rather
> click than run scripts. Both produce the same artifact: the standard Records
> Stage UI with the ~183,500-document Founders Online corpus embedded.
>
> The one task the wizard can't do for you is **the parser** — a ~20-line
> Python function. It's written out in full in Step 2 below; hand it to a
> developer if you don't have one, then the rest is clicks.

---

## What you're building

The standard Records Stage publishing tool (preset campaign builder, clearance
editor, Word export, the NARA + Wikimedia Commons + Library of Congress image
modal) carrying the Founders Online corpus — the papers of Adams, Franklin,
Hamilton, Jay, Jefferson, Madison, and Washington (1706–1923). Each of the
seven editions becomes a source-filter chip, so you can filter by founder.

**Inherited from the vendored shell automatically — no action needed:** the
current model id (`claude-sonnet-4-6`) for AI drafts, and the removal of the
legacy FRUS interest-score badge / min-score slider. Records Studio splices
your data into this repo's `records-stage.html`, so anything already fixed in
that shell comes along for free.

---

## Prerequisites

```bash
pip install -r requirements.txt
```

Python 3.10+. Run everything from the repo root (the folder containing
`app.py`, `parser.py`, `build_cache.py`).

---

## Step 1 — Get the Founders Online metadata

The bulk metadata file is behind an **AWS WAF JavaScript challenge**, so a
scripted download fails (you get an `HTTP 202` challenge page, not JSON).
Download it in a real browser:

```
https://founders.archives.gov/Metadata/founders-online-metadata.json
```

Save it (~51 MB) into a new corpus folder:

```
data/founders-online/founders-online-metadata.json
```

(Everything under `data/` is gitignored by default, which is correct — the
file is large and re-downloadable.)

---

## Step 2 — Write the parser (the one developer task)

Records Studio walks a `parse_corpus(source_root)` function and expects each
event to match the toolkit's event contract
([`docs/data-contract.md`](data-contract.md)): `source`, `year`, `month`,
`day`, `title`, `url`. Create the Founders adapter at
`data/founders-online/parser.py`, mirroring `data/frus/parser.py`:

```python
# data/founders-online/parser.py
"""Founders Online adapter — yields one event per dated document."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def parse_corpus(source_root: Path) -> Iterable[dict]:
    """Read founders-online-metadata.json and yield normalized events."""
    data_path = Path(source_root) / "founders-online-metadata.json"
    raw = json.loads(data_path.read_text(encoding="utf-8"))

    for rec in raw:
        # Keep only full YYYY-MM-DD dates (99.7%); drop the ~638 blank/partial.
        df = (rec.get("date-from") or "").strip()
        if len(df) != 10 or df[4] != "-" or df[7] != "-":
            continue
        year_s, month_s, day_s = df[:4], df[5:7], df[8:10]
        if not (month_s.isdigit() and day_s.isdigit()):
            continue

        yield {
            # The edition becomes the source-filter chip (7 founders).
            "source": (rec.get("project") or "Founders Online").strip(),
            "year": int(year_s),
            "month": month_s,   # zero-padded "01".."12" → MM-DD bucket key
            "day": day_s,       # zero-padded "01".."31"
            "title": (rec.get("title") or "").strip() or "(untitled)",
            "url": (rec.get("permalink") or "").strip(),
            "subjects": [],     # Founders metadata carries no subject tags
        }
```

Then point the repo-root `parser.py` at this adapter (the same indirection the
shipped `parser.py` uses for the FRUS adapter) — replace its contents with:

```python
# parser.py  (repo root)
"""Adopter parser — wired to the Founders Online adapter in data/founders-online/."""
import importlib.util
from pathlib import Path

_p = Path(__file__).resolve().parent / "data" / "founders-online" / "parser.py"
_spec = importlib.util.spec_from_file_location("founders_parser", _p)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

parse_corpus = _mod.parse_corpus
```

> Keep a copy of the original `parser.py` first if you want to restore the FRUS
> wiring later (`cp parser.py parser.py.frus.bak`).

---

## Step 3 — Launch Records Studio

```bash
streamlit run app.py
```

A browser tab opens at `http://localhost:8501`. Everything runs locally — no
corpus content leaves your machine. The wizard has five tabs; work through them
in order.

---

## Step 4 — Tab 1: Connect corpus

1. In **Corpus directory**, enter the folder your parser reads:
   `data/founders-online`.
2. Click **Test parser**.
3. You should see a preview of the first five events — each with a
   `source` like *Washington Papers* / *Jefferson Papers*, a year, a title, and
   a `founders.archives.gov` URL. The wizard checks the required fields
   (`source`, `month`, `day`, `year`, `title`, `url`) and warns if any are
   missing.

If the parser raises an error, fix `data/founders-online/parser.py` and click
**Test parser** again.

---

## Step 5 — Tab 2: Tune scoring

Founders Online has **no editorial score** — every document is included.

1. Set the **threshold** slider (top of the tab) to **0**. With a 0 threshold
   nothing is dropped, so all ~183,500 dated documents make it into the cache.
2. Ignore the per-axis weight sliders. Founders events carry none of the
   scoring signals the axes read (document type, participant prestige, etc.),
   so every event scores 0 — the weights have nothing to act on. (If the tab
   says *"You're using a custom scorer.py,"* that's fine; leave it. The shipped
   `scorer.py` imports `axis_scorer`, which is also fine — the 0 threshold is
   what matters.)

The live top-10 preview will show documents in arbitrary order since all scores
are equal — expected. The browser tool sorts by **year (newest first)** at
display time regardless.

---

## Step 6 — Tab 3: Subjects (optional)

Choose **No taxonomy**. Founders metadata has no subject tags, so the subject /
topic cascade hides itself in the final tool. (Search still works on document
**titles** — the same metadata-only constraint every instance has.)

---

## Step 7 — Tab 4: Customize HTML

The tab first confirms the vendored `records-stage.html` shell is present
("ready"). Then, optionally, brand the clearance block:

- **Drafted-by line** — your A/SKS/OH drafter name + phone, if you want it
  pre-filled.
- **Clearance chain** — edit the rows, or upload your office's two-column Word
  template (office name / default status) to populate them.

Click **Apply HTML customizations**. These are optional — you can leave the
defaults and brand later.

> **Note:** this tab does **not** set the page title — Records Studio brands the
> clearance block, not the `<title>` / `<h1>`. The title is a one-line manual
> edit in Step 9.

---

## Step 8 — Tab 5: Build & download

1. Click **Build cache** — walks the parser, scores everything (all 0), writes
   `events_cache.json` and `events_cache.js`. The summary below the button
   should report ~183,500 events across 366 days and 7 sources.
2. Click **Splice cache into HTML** — copies the freshly built cache into
   `records-stage.html`. (Always run this *after* Build cache.)
3. Use the **download buttons** for the three artifacts. The one you publish is
   the customized **`records-stage.html`** (~30 MB).

---

## Step 9 — Final manual touches (what the wizard doesn't do)

Records Studio always operates on `records-stage.html` with the generic
"Records Stage" title. Two small edits finish the Founders instance:

**a. Rename the file** to match the sibling instances:

```bash
mv records-stage.html founders-online-stage.html
```

**b. Set the title** — open `founders-online-stage.html` and change the two
generic strings to the house style (em-dash separator, matching
`Federal Register — Records Stage`):

| Find | Replace with |
|---|---|
| `<title>Records Stage</title>` | `<title>Founders Online — Records Stage</title>` |
| `<h1>Records Stage</h1>` | `<h1>Founders Online — Records Stage</h1>` |

That's the whole instance. Open `founders-online-stage.html` in a browser: pick
a date under **Browse by Date**, see the seven founder chips, and (with an
`sk-ant-…` key pasted into the API-key field) use **AI Drafts**, presets, image
search, snapshots, and Word export exactly as in the other Records Stage
instances.

---

## How this maps to the CLI builder

`build_founders_stage.py` does all of the above in one command, and is the
source of truth for rebuilds:

| Records Studio step | `build_founders_stage.py` equivalent |
|---|---|
| Step 2 parser | `parse_founders()` (edition → `source`, zero-padded `MM-DD`) |
| Step 5 threshold 0 | no score emitted at all (compact event is just `{y,t,u,s}`) |
| Step 6 No taxonomy | writes `const SUBJECT_TAXONOMY = []` |
| Step 8 Build + Splice | `html_embed.sync_html_embed` into a fresh copy of the shell |
| Step 9b title | the `STAGE_TITLE` constant, re-applied on every build |

The only functional difference: the CLI builder omits the per-event score key
entirely, while the Records Studio path stores `sc: 0` on each event. Both are
identical in the browser — the score badge is gated to FRUS and was removed
from the shell anyway, so a `0` score renders nothing.

---

## Data caveats (carried by both paths)

- **Search is title-only** — the bulk metadata has no subject tags or body text.
- **~5.5% cross-edition duplication** — Founders Online publishes a letter in
  *both* correspondents' editions (a Jefferson→Madison letter appears in the
  Jefferson Papers and the Madison Papers as two records with different
  permalinks).
- **Jan 1 spike** — year-only-known dates default upstream to January 1.

See [`docs/founders-online-build.md`](founders-online-build.md) for the full
data notes and the CLI build.
