# Records Studio Lite — build your tool in the browser

**Records Studio Lite turns a spreadsheet or data export into a working
Records Stage publishing tool, using nothing but a web browser.** No Python,
no installing software, no command line, no uploading your data anywhere.

This guide walks you through it from scratch, assuming no technical
background. If you can fill out a web form and double-click a file, you can
use this.

---

## Lite or the full Records Studio? (start here)

There are two ways to build a Records Stage tool. They produce the same
result; they differ in what they ask of you.

| | **Records Studio Lite** (this guide) | **Records Studio** (`app.py`) |
|---|---|---|
| What it is | A web page you open in your browser | A program you install and run |
| Needs Python installed? | **No** | Yes |
| Needs the command line? | No | Yes (two commands) |
| Your data must be… | a **JSON or CSV** file | any format (you supply a small parser) |
| Good for | spreadsheets, clean data exports | messy archives (XML, PDFs, scraped web pages) |
| Controlled subject taxonomy | not supported (tags become a flat list) | supported |

**Use Lite if** your data is already a tidy table or JSON export — a CSV from
a database, a spreadsheet saved as CSV, a JSON export from a content system.
That covers most cases.

**Use the full Records Studio if** your source is something the browser can't
read directly (a folder of PDFs, raw XML, a website you have to scrape) or you
need a formal subject taxonomy. See the [README](../README.md) for that path.

Both produce a metadata-only tool: it catalogs and links to your documents,
but does not store or search their full text. See
[constraints.md](constraints.md) for why.

---

## What you'll need before you start

1. **A web browser** — Chrome, Edge, Firefox, or Safari. You almost certainly
   already have one.
2. **The toolkit files** — two HTML files from this project:
   `studio-lite.html` (the builder) and `records-stage.html` (the template it
   fills in). Getting them is Step 1 below.
3. **Your data**, saved as **one JSON file** or **one CSV file**. Preparing it
   is Step 2 below.

That's everything. Nothing gets installed.

> **Just want to see it work first?** The toolkit ships with ready-made sample
> data: `examples/studio-lite-sample.csv` (or `.json`). You can do this whole
> walkthrough with that file before preparing your own — a clean run reports
> 12 records in, 12 included, 0 dropped.

---

## Step 1 — Get the toolkit files

If someone handed you a folder that already contains `studio-lite.html` and
`records-stage.html`, skip to Step 2.

Otherwise, download them from the project's GitHub page — no account or git
needed:

1. Open the project page in your browser.
2. Click the green **`Code`** button near the top right.
3. Choose **Download ZIP**.
4. Find the downloaded `.zip` in your Downloads folder and **unzip it**
   (Windows: right-click → *Extract All*; Mac: double-click it).
5. You now have a folder containing many files. The two that matter are
   **`studio-lite.html`** and **`records-stage.html`**. Leave them where they
   are — keeping them in the same folder makes the next steps easier.

---

## Step 2 — Prepare your data

Lite reads **one file**: either JSON or CSV. Each row/record becomes one
document in your tool. Every record needs, at minimum:

- a **title** (the headline shown on each card), and
- a **date** (so it can be placed on the calendar).

A **link (URL)** to the original document is strongly recommended — the tool
links out to it. **Subjects/tags** and a short **description** are optional but
make the tool more useful.

### If your data is a spreadsheet

Open it in Excel (or Google Sheets) and make sure the **first row is a header
row** with column names like `title`, `date`, `url`, `tags`. Then **Save As →
CSV**. That's it.

A CSV looks like this (the header names can be anything — you'll map them in
Step 5):

```
title,date,url,tags
"Secretary Visits Tokyo",2011-07-04,https://example.gov/news/123,"Diplomacy, Asia"
"New Trade Agreement Signed","March 15, 2010",https://example.gov/news/124,"Trade, Economics"
```

### If your data is JSON

It should be a **list of records**, like this:

```json
[
  {
    "title": "Secretary Visits Tokyo",
    "date": "2011-07-04",
    "url": "https://example.gov/news/123",
    "tags": ["Diplomacy", "Asia"]
  },
  {
    "title": "New Trade Agreement Signed",
    "date": "March 15, 2010",
    "url": "https://example.gov/news/124",
    "tags": ["Trade", "Economics"]
  }
]
```

If your JSON wraps the list inside a named key — for example
`{"results": [ ... ]}` — that's fine; you'll type the key name (`results`) into
one box in Step 3.

### Dates Lite understands

Any of these work: `2011-07-04`, `2011/07/04`, `July 4, 2011`, `4 July 2011`,
`July 2011`, or just `2011`. If you only give a year (or a month and year), the
document is placed on the first of that period.

> **Heads-up on numeric dates.** A date like `03/04/2020` is ambiguous —
> it's March 4th in the US and 4 March elsewhere. Lite reads it US-style
> (month first) by default. If your dates are day-first, tick the box for that
> in Step 3.

---

## Step 3 — Open Records Studio Lite

**Double-click `studio-lite.html`.** It opens in your browser as a web page
titled *Records Studio Lite*. You'll see five numbered steps down the page.

(There is no server and no internet involved — the page runs entirely on your
computer. You can confirm by noting your data never "uploads"; it's processed
right there in the browser.)

---

## Step 4 — Load your data (page step 1)

1. Under **"1 · Load your data,"** click **Choose File** and pick the JSON or
   CSV file you prepared.
2. If your JSON had its records under a named key (like `results`), type that
   key into the **"the array's key"** box.
3. If your dates are day-first, tick the **day-first** checkbox.

You should see a green message like *"Found 1,234 record(s)."* If you get a red
error instead, see [Troubleshooting](#troubleshooting) below.

---

## Step 5 — Map your fields (page step 2)

Lite makes its best guess at which of your columns is the title, the date, and
so on, and pre-fills the dropdowns. **Check each one** and correct it if needed:

- **Source label** — a short name for this archive (e.g. *GPA Press
  Releases*). It appears as a badge on every card.
- **Title field** — required.
- **URL field** — the link to each document. Strongly recommended.
- **Date field** — pick the single column that holds the date. *(Or, if your
  date is split across three columns, leave Date blank and pick the Year,
  Month, and Day columns instead.)*
- **Subjects/tags** and **Description** — optional.

You can expand **"Preview of the first record"** to see exactly what your data
looks like, which helps when choosing fields.

---

## Step 6 — Scoring (page step 3) — optional

Records Stage can rank cards by an "interest score" and hide low-scoring ones.
**You can skip this entirely** — the defaults give every document the same
score, which is fine.

If you'd like some documents to rank higher:

- **Base score** — where every document starts (default 50).
- **Bonus if the record has subjects** — rewards better-tagged documents.
- **Priority keywords** — type words like `treaty, summit, sanctions`. Any
  document whose title or tags contain one gets a boost.
- **Points per keyword match** — how big that boost is.
- **Minimum score to include** — documents below this are left out of the
  tool. Leave it at `0` to keep everything.

---

## Step 7 — Choose the template (page step 4)

Click **Choose File** and select **`records-stage.html`** (from the same
folder you unzipped in Step 1). This is the shell that Lite fills with your
data. Your original file is never changed — Lite builds a fresh copy.

You'll see *"Template loaded."* (If you happen to be running this through a
local web address, Lite may load it automatically and tell you so — either way
is fine.)

---

## Step 8 — Build and download (page step 5)

1. Click **Build my Records Stage**.
2. A summary table appears, showing how many records were included and how many
   were dropped (and why — see below).
3. Click **⬇ Download records-stage.html**.

That downloaded `records-stage.html` **is your finished tool**, with your data
baked in. (The two extra download buttons — `events_cache.js` and
`events_cache.json` — are only needed for the advanced command-line workflow;
most people can ignore them.)

> **Why were some records dropped?** Lite skips records with no title, with a
> date it couldn't read, or with an out-of-range month/day, and it drops any
> below your minimum score. If the dropped count is high, it's almost always
> the **date** column — re-check your mapping in Step 5, and the day-first
> checkbox in Step 4.

---

## Step 9 — Use your new tool

**Double-click the `records-stage.html` you just downloaded.** It opens in your
browser, ready to use — browse documents by date, search, draft posts, track
clearances, and export to Word. To share it, send that one file (note it can be
large) or post it somewhere your team can open it.

### One extra step only if you want image search

The optional **photo search** (National Archives, Library of Congress) needs
the page opened through a local web address rather than by double-clicking.
This is the one place a couple of typed commands help. In a terminal /
Command Prompt, go to the folder with your tool and run:

```
python -m http.server 8000
```

then open **`http://localhost:8000/records-stage.html`** in your browser.
(Everything *except* image search works fine from a plain double-click, so skip
this if you don't need photos.)

---

## Troubleshooting

**"Expected a JSON array of records…"**
Your JSON wraps the records inside a named key. Find the key (the message
suggests likely ones) and type it into the *array's key* box in Step 4.

**"No rows found in the CSV…"**
The file needs a header row plus at least one data row. Re-export from your
spreadsheet as CSV and try again.

**Lots of records were dropped.**
Almost always the date. Confirm the **Date field** in Step 5 points at the
right column, and that the dates are in one of the
[understood formats](#dates-lite-understands). If your dates are day-first
(e.g. UK style), tick the day-first box in Step 4 and rebuild.

**"That file doesn't look like a Records Stage template…"**
In Step 7 you picked the wrong file. Choose **`records-stage.html`** (not
`studio-lite.html`, and not your data file).

**The finished tool's images won't load.**
You opened it by double-clicking. Image search needs the local-web-address
step in [Step 9](#one-extra-step-only-if-you-want-image-search). Everything
else works either way.

**My data is huge / the tool is slow to build.**
Lite builds everything in the browser's memory, which is comfortable into the
tens of thousands of records. For very large archives, use the command-line
build in the [README](../README.md) instead.

---

## What Lite does *not* do

For these, use the full Python **Records Studio** (`app.py`):

- **Messy source formats** — folders of PDFs, raw XML, scraped HTML. (Lite
  reads JSON and CSV only.)
- **A controlled subject taxonomy** — Lite turns whatever tags your records
  carry into a simple flat list. The full tool can load a curated taxonomy with
  categories and subcategories.

Two things you might expect to set up here you actually don't need to: the
**clearance chain** and **drafted-by** details are editable directly inside the
finished Records Stage tool, so Lite doesn't ask about them.

---

## The one rule that never changes

The tool stores **metadata only** — title, source, subjects, date, score — and
**links out** to each document. It does **not** store or full-text-search the
documents' contents. Searching for a word that appears only in the body text
won't find anything; search by title or subject tag instead, then click through
to read the document. This keeps the tool a single, fast, self-contained file
with no server. See [constraints.md](constraints.md) for the full reasoning.
