# The web wrapper

`app.py` — **Records Studio** — is a Streamlit front-end over the Python
toolkit. It's the recommended entry point for non-technical adopters — editors, archivists,
librarians — who would rather not run shell commands.

This doc covers what the wrapper does (and doesn't) cover, and what to do
when something goes wrong.

---

## Launching

```bash
pip install -r requirements.txt
streamlit run app.py
```

A browser tab opens at `http://localhost:8501`. The wrapper runs entirely
on your laptop; **no corpus content is sent anywhere**.

The wrapper expects to be launched from the repo root (the directory that
contains `parser.py`, `scorer.py`, `build_cache.py`, etc.). If you cloned
the template into `~/my-archive`, run the two commands from inside that
directory.

---

## The five tabs

### 1. Connect corpus

Point at the directory your `parse_corpus()` walks. Click **Test parser**
to run it once and preview the first five events.

If `parser.py` is still a stub, the wrapper offers a one-click copy of
`examples/example_parser.py` so you can see the rest of the flow before
plugging in real data.

**What the wrapper checks:** required fields (`source`, `month`, `day`,
`year`, `title`, `url`) on each event. If any are missing it surfaces a
warning naming the field.

### 2. Tune scoring

Sliders for the weights in `scoring_config.json`. The threshold (events
scoring below this are dropped from the cache) is a separate slider at the
top.

The live preview re-scores the events from tab 1 and shows the top 10 — so
you can drag a weight and immediately see ranking changes.

**The slider-tunable path requires `scorer.py` to import from
`axis_scorer`.** The wrapper has a one-click button to switch it. If you've
written a custom scorer with its own logic, the wrapper leaves it alone and
tells you weights live in code.

### 3. Subjects (optional)

Three modes:

- **No taxonomy** — the subject cascade UI in the final HTML hides itself.
- **Local file or directory** — point at `taxonomy.json` (or a folder
  containing it).
- **Remote GitHub repo** — for adopters tracking an externally maintained
  taxonomy export, like `vak2ve/frus-subject-taxonomy`.

After loading, the wrapper previews the first 50 subjects so you can sanity
check.

### 4. Customize HTML

Tab 4 first confirms the vendored Records Stage HTML (`records-stage.html`)
is present — it ships with the repo, so normally you'll just see a "ready"
confirmation. There's no fetch button: Records Stage is this repo's
maintained copy, not something the wrapper pulls from upstream. If the file
is missing, the wrapper tells you to restore it from git (or, as a last
resort, ask a developer to run `python fetch_records_stage.py` from the
command line — see the note on that script in the README).

Then the branding controls:

- **Drafted-by line** — the "drafted by" header above the clearance block.
- **Clearance chain** — an editable table; each row becomes one clearance
  line. Status options are `Required Clearance / Info / Info* / N/A`. If your
  office already keeps a clearance template as a Word doc (a two-column
  table: office name / default status), you can upload it to populate the
  rows, then edit them.

The **Apply HTML customizations** button writes these into
`records-stage.html` between named comment markers
(`<!-- DRAFTED_BY -->` / `<!-- /DRAFTED_BY -->` and similar for clearances).
If those markers are missing from the HTML, the wrapper warns and you'll need
to edit by hand.

### 5. Build & download

Two buttons:

- **Build cache** — full rebuild. Walks the parser, scores everything,
  enriches with taxonomy, writes both `events_cache.json` and
  `events_cache.js`. Output summary shows up below the button.
- **Splice cache into HTML** — copies the freshly built cache into the
  embed point in `records-stage.html`. Run this after every cache build.

Then three download buttons for the artifacts. Email / Slack /
Sharepoint-upload them to your team or your CMS.

---

## Things the wrapper does **not** do

- **It doesn't write your parser for you.** Parsing is fundamentally
  corpus-specific. A developer needs to write `parse_corpus()` once,
  following `docs/data-contract.md`.
- **It doesn't host the final HTML.** Open it locally or upload it
  somewhere your team can reach (Sharepoint, GitHub Pages, a shared
  drive). The HTML has no server side.
- **It doesn't replace `git`.** If you want versioned configs and
  reproducible builds, commit `scoring_config.json` and `parser.py`
  alongside the rest.

---

## Troubleshooting

**The browser says "This site can't be reached."** Streamlit didn't start.
Check the terminal output for an error. Common causes: another app using
port 8501 (`streamlit run app.py --server.port 8502`), a Python version
older than 3.10, or a corrupted Streamlit install (`pip install --upgrade
streamlit`).

**Tab 1 fails with "Parser raised ModuleNotFoundError."** Your parser
imports a package that isn't installed in the environment running
Streamlit. Add it to `requirements.txt` and reinstall.

**Tab 2 shows "You're using a custom scorer.py."** Click the *Switch
scorer.py to axis_scorer* button if you want slider tuning; otherwise
your weights live in `scorer.py` and you'll edit them there.

**Tab 4 warns "couldn't find embed markers."** The `DRAFTED_BY` / clearance
comment markers aren't present in your `records-stage.html` (e.g. it was
replaced with a shell that lacks them). Restore the vendored copy from git,
or edit the clearance block by hand.

**Tab 5 fails with "events_cache.json not found"** during *Splice*. You
need to **Build cache** first.

---

## Running headless / on a server

By default Streamlit binds to localhost. For shared internal use:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

If you do this, put it behind authentication. The wrapper has no built-in
auth, and exposing the build pipeline to the open internet would let
anyone overwrite your cache and HTML.

For a corpus where multiple people refresh on a cron schedule, the CLI
path (`build_cache.py` + `merge_sources.py` in a GitHub Action) is the
right shape, not a long-running web app.
