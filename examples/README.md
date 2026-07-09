# Worked example: a stub corpus

This directory contains a five-event toy archive (`sample_data.json`) plus a
parser and a scorer over it. Copy these files to the template root and adjust
them to your real corpus.

## For Records Studio Lite: ready-to-load sample data

If you're trying the no-install, browser-only builder
([`docs/studio-lite.md`](../docs/studio-lite.md)), use these instead — they're
already in the shape Lite expects, so you can load one straight into
`studio-lite.html` and click Build:

- **`studio-lite-sample.csv`** — a 12-row spreadsheet export.
- **`studio-lite-sample.json`** — the same 12 records as JSON.

Both hold the same fictional public-affairs items (press releases, readouts,
fact sheets) and use a mix of date formats on purpose. A clean run reports
12 records in, 12 included, 0 dropped.

## Try it

```bash
# From this directory, do a dry-run parse.
python example_parser.py

# Score one event by hand to sanity-check.
python -c "
from example_parser import parse_corpus
from example_scorer import score_event
from pathlib import Path
for ev in parse_corpus(Path('.')):
    print(score_event(ev), ev['title'])
"
```

Expected ranking (roughly):
- Embassy Security After Nairobi (high — cover story, long, multimedia, senior author)
- Diplomacy in the Digital Age (high — cover story, long, priority subject)
- Cultural Diplomacy in Practice (mid — priority subject, senior author)
- Foreign Service Day Reflections (low — junior author, adjacent subject only)
- Notes from the Mailroom (very low — unattributed, no subjects, short)

## What's intentionally bad

The example scorer's `_anniversary_alignment()` returns zero — real adopters
should wire that to a list of institutional dates. Treat it as the canonical
place where editorial knowledge lives in code.
