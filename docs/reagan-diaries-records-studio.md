# Building "The Reagan Diaries — Records Stage" in Records Studio

A step-by-step walkthrough for building the Reagan Diaries instance using
**Records Studio** — the Streamlit wizard (`app.py`) — instead of the
command-line builder.

> **Two paths to the same tool.** `build_reagan_stage.py` is the one-command,
> reproducible builder (see
> [`docs/reagan-diaries-build.md`](reagan-diaries-build.md)). **This** doc shows
> the equivalent build through the Records Studio UI — the right path for a
> non-technical adopter (editor, archivist, librarian) who would rather click
> than run scripts. Both produce the same artifact: the standard Records Stage UI
> with Ronald Reagan's ~2,500-entry personal diary embedded.
>
> The one task the wizard can't do for you is **the parser** — a ~20-line Python
> function. It's written out in full in Step 2 below; hand it to a developer if
> you don't have one, then the rest is clicks.

---

## What you're building

The standard Records Stage publishing tool (preset campaign builder, clearance
editor, Word export, the NARA + Wikimedia Commons + Library of Congress image
modal) carrying **the personal diary Ronald Reagan kept throughout his
presidency** (Jan 20, 1981 – Jan 20, 1989) — the entries published as *The
Reagan Diaries*, ed. Douglas Brinkley.

One entry per real calendar date, so the tool's **Browse by Date / On This Day**
view surfaces every year that shares a month-day. Pick January 20 and you see
both the 1981 inauguration entry and the 1989 "start of our new life" departure
entry, side by side.

> **This is the *personal* diary, not the White House "Daily Diary."** The Reagan
> Library's Daily Diary (reaganlibrary.gov) is a logbook of the President's
> meetings and movements — a different record. This instance carries Reagan's own
> handwritten journal, transcribed from the Reagan Foundation editions.

**Inherited from the vendored shell automatically — no action needed:** the
current model id for AI drafts and every other fix already in this repo's
`records-stage.html`. Records Studio splices your data into that shell, so
anything already fixed there comes along for free.

---

## Prerequisites

```bash
pip install -r requirements.txt
```

Python 3.10+. Run everything from the repo root (the folder containing `app.py`,
`parser.py`, `build_cache.py`).

---

## Step 1 — Get the diary XML

Place the diary transcription — a single XML file of `<entry date="YYYY-MM-DD">`
elements, each with a `<body>` of `<p>` paragraphs — into a new corpus folder:

```
data/reagan-diaries/diary.xml
```

(Everything under `data/` is gitignored by default, which is correct — the file
isn't ours to redistribute and is re-obtainable.)

A quick shape check:

```xml
<diary>
  <entry date="1981-01-20">
    <head><source-url>…</source-url>…</head>
    <body><p>The Inaugural (Jan. 20) was an emotional experience…</p></body>
  </entry>
  …
</diary>
```

---

## Step 2 — Write the parser (the one developer task)

Records Studio walks a `parse_corpus(source_root)` function and expects each
event to match the toolkit's event contract
([`docs/data-contract.md`](data-contract.md)): `source`, `year`, `month`, `day`,
`title`, `url`. Create the Reagan adapter at `data/reagan-diaries/parser.py`:

```python
# data/reagan-diaries/parser.py
"""Reagan Diaries adapter — yields one event per dated entry."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

SOURCE_LABEL = "The Reagan Diaries"
ENTRY_URL_STEM = "https://www.reaganfoundation.org/ronald-reagan/white-house-diaries/diary-entry-"


def _entry_text(entry: ET.Element) -> str:
    """Join all <p> paragraphs into one whitespace-normalized string."""
    parts = []
    for p in entry.iter("p"):
        text = " ".join("".join(p.itertext()).split())
        if text:
            parts.append(text)
    return " ".join(parts)


def parse_corpus(source_root) -> Iterable[dict]:
    """Read diary.xml and yield normalized events."""
    xml_path = Path(source_root) / "diary.xml"
    root = ET.parse(xml_path).getroot()

    for entry in root.findall("entry"):
        date = (entry.get("date") or "").strip()
        # Need a full YYYY-MM-DD (the On This Day browse requires it).
        if len(date) != 10 or date[4] != "-" or date[7] != "-":
            continue
        y, m, d = date[:4], date[5:7], date[8:10]
        if not (m.isdigit() and d.isdigit() and 1 <= int(m) <= 12 and 1 <= int(d) <= 31):
            continue

        title = _entry_text(entry)   # the FULL entry text — see the note below
        if not title:
            continue

        yield {
            "source": SOURCE_LABEL,   # one source → one filter chip
            "year": int(y),
            "month": m,               # zero-padded "01".."12" → MM-DD bucket key
            "day": d,                 # zero-padded "01".."31"
            "title": title,
            "url": f"{ENTRY_URL_STEM}{m}{d}{y}",
            "subjects": [],           # the diary carries no subject tags
        }
```

> **Why the whole entry goes in `title`.** In this tool, `title` is what each row
> shows, the **only** field search scans, **and** what the AI drafter feeds to
> Claude. There's no separate "body" field, so putting the full entry text in
> `title` is what makes the diary searchable and draftable. Rows are taller than
> a one-line headline — the right trade for a diary you actually want to read.

> **Why the reconstructed URL.** The diary's original source links are dead
> (404). The Foundation republished each entry at a readable page with a
> predictable stem, so the parser rebuilds it as `…/diary-entry-MMDDYYYY`. About
> 96% resolve; a few entries with no published page will 404 — still far better
> than the uniformly-dead originals.

Then point the repo-root `parser.py` at this adapter (the same indirection the
shipped `parser.py` uses for the FRUS adapter) — replace its contents with:

```python
# parser.py  (repo root)
"""Adopter parser — wired to the Reagan Diaries adapter in data/reagan-diaries/."""
import importlib.util
from pathlib import Path

_p = Path(__file__).resolve().parent / "data" / "reagan-diaries" / "parser.py"
_spec = importlib.util.spec_from_file_location("reagan_parser", _p)
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
   `data/reagan-diaries`.
2. Click **Test parser**.
3. You should see a preview of the first five events — each with `source`
   *The Reagan Diaries*, a year, the entry text as the title, and a
   `reaganfoundation.org/…/diary-entry-…` URL. The wizard checks the required
   fields (`source`, `month`, `day`, `year`, `title`, `url`) and warns if any are
   missing.

If the parser raises an error, fix `data/reagan-diaries/parser.py` and click
**Test parser** again.

---

## Step 5 — Tab 2: Tune scoring

The diary has **no editorial score** — every entry is included.

1. Set the **threshold** slider (top of the tab) to **0**. With a 0 threshold
   nothing is dropped, so all ~2,500 entries make it into the cache.
2. Ignore the per-axis weight sliders. Diary entries carry none of the scoring
   signals the axes read (document type, participant prestige, classification),
   so every event scores 0 — the weights have nothing to act on. (If the tab says
   *"You're using a custom scorer.py,"* that's fine; leave it. The 0 threshold is
   what matters.)

The live top-10 preview shows entries in arbitrary order since all scores are
equal — expected. The browser tool sorts each day by **year** at display time
regardless.

---

## Step 6 — Tab 3: Subjects (optional)

Choose **No taxonomy**. The diary has no subject tags, so the subject / topic
cascade hides itself in the final tool. Search still works — and here it's more
useful than in a metadata-only instance, because it scans the **full entry
text**, not just a title.

> Reagan's shorthand is preserved verbatim, so search literally: "N.S.C." and
> "V.P." hit; "Sec'y" won't match "Secretary".

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
   `events_cache.json` and `events_cache.js`. The summary below the button should
   report ~2,500 events across 366 days (Feb 29 included) and 1 source.
2. Click **Splice cache into HTML** — copies the freshly built cache into
   `records-stage.html`. (Always run this *after* Build cache.)
3. Use the **download buttons** for the three artifacts. The one you publish is
   the customized **`records-stage.html`** (~3.6 MB).

---

## Step 9 — Final manual touches (what the wizard doesn't do)

Records Studio always operates on `records-stage.html` with the generic "Records
Stage" title. Two small edits finish the Reagan instance:

**a. Rename the file** to match the sibling instances:

```bash
mv records-stage.html reagan-diaries-stage.html
```

**b. Set the title** — open `reagan-diaries-stage.html` and change the two
generic strings to the house style (em-dash separator, matching
`Founders Online — Records Stage`):

| Find | Replace with |
|---|---|
| `<title>Records Stage</title>` | `<title>The Reagan Diaries — Records Stage</title>` |
| `<h1>Records Stage</h1>` | `<h1>The Reagan Diaries — Records Stage</h1>` |

That's the whole instance. Open `reagan-diaries-stage.html` in a browser: pick a
date under **Browse by Date** (try **01-20** to see 1981 through 1989), and —
with an `sk-ant-…` key pasted into the API-key field — use **AI Drafts**,
presets, image search, snapshots, and Word export exactly as in the other
Records Stage instances. Because the full entry text is the event title, the AI
drafter writes from Reagan's actual words.

---

## How this maps to the CLI builder

`build_reagan_stage.py` does all of the above in one command, and is the source
of truth for rebuilds:

| Records Studio step | `build_reagan_stage.py` equivalent |
|---|---|
| Step 2 parser | `parse_reagan()` (entry text → `title`, reconstructed deep-link `url`) |
| Step 5 threshold 0 | no score emitted at all (compact event is just `{y,t,u,s}`) |
| Step 6 No taxonomy | writes `const SUBJECT_TAXONOMY = []` |
| Step 8 Build + Splice | `html_embed.sync_html_embed` into a fresh copy of the shell |
| Step 9b title | the `STAGE_TITLE` constant, re-applied on every build |

The only functional difference: the CLI builder omits the per-event score key
entirely, while the Records Studio path stores `sc: 0` on each event. Both are
identical in the browser — the score badge is gated to FRUS and was removed from
the shell anyway, so a `0` score renders nothing.

---

## Data caveats (carried by both paths)

- **Search matches the entry text** — no subject tags or separate fields. This is
  usually what you want, but Reagan's abbreviations and curly quotes are verbatim,
  so search literally.
- **Not every day has an entry**, and a given month-day may carry only some of the
  eight years — Reagan didn't write daily.
- **~4% of the reconstructed URLs 404** — entries the Foundation didn't publish a
  page for. The collection home is a safe fallback:
  <https://www.reaganfoundation.org/ronald-reagan/white-house-diaries>.

See [`docs/reagan-diaries-build.md`](reagan-diaries-build.md) for the full data
notes and the CLI build.
