# The United States and Strategic Resources, 1861–1992

A static, FRUS-led historical decision-support and orientation platform for
understanding how the United States sought access to critical minerals and
strategic resources. It is designed for Department of State employees, Foreign
Service Officers, historians, policy researchers, and students.

**Live site:**
[therealjameswilson.github.io/critical-minerals-records-stage-v2/records-stage.html](https://therealjameswilson.github.io/critical-minerals-records-stage-v2/records-stage.html)

> **Governing principle:** FRUS explains what policymakers were thinking. Other
> official U.S. Government sources explain what they were looking at.

The main historical experience is hard-bounded to 1861–1992. Post-1992 material
appears only in a separately labeled Modern Context layer.

## What v2 Provides

- A historical homepage organized by mineral, country, period, episode, map,
  agreement, law, archive, stockpile case, and FRUS record.
- Reusable History Stack pages that connect an entity to twelve layers: FRUS,
  timeline, official statistics, agreements, geography, law, stockpiles,
  archives, decision process, outcomes, provenance, and Modern Context.
- A complete metadata-only FRUS Subjects discovery index for 1861–1992:
  16,811 document links across 545 volumes.
- A pilot with 8 minerals, 8 countries or territories, 6 periods, 14 typed
  agreements or policy instruments, 3 laws, 4 administrations, 2 stockpile
  cases, 20 linked FRUS records, and 25 NARA query plans.
- 1,114 unit-defined historical observations extracted from official USGS Data
  Series 140 workbooks without project interpolation.
- A country-level evidence map with a 1861–1992 year control and accessible
  table alternative.
- A source-visible NARA discovery layer that can use a secret-bearing serverless
  proxy without exposing the API key to GitHub Pages.

This is a public research demonstrator, not an official Department of State or
U.S. Government product.

## Trust Model

FRUS is the narrative spine, not the entire archive. The interface distinguishes:

- **Reviewed FRUS document:** document-level pilot metadata has been checked.
- **FRUS discovery lead:** only subject-authority and volume or chapter context
  are known; open the document before making a claim.
- **Official statistic:** value, unit, year, publication, workbook location,
  source URL, extraction method, and confidence are retained.
- **Partial coverage:** at least one evidence layer is linked and named gaps remain.
- **Research queue:** the schema or discovery route exists but needs verification.

The project never embeds full FRUS or NARA document text. Missing values are not
invented, estimated, or converted to zero. Historical country names are stored
by period. Formal treaties are distinguished from negotiations, concessions,
purchasing agreements, and domestic policy instruments.

Read the [full methodology](methodology.html) or
[`docs/methodology.md`](docs/methodology.md).

## Repository Structure

- `records-stage.html`: historical portal entry point
- `history-stack.html`: reusable entity and document detail route
- `methodology.html`: public methodology page
- `assets/portal.js`: homepage rendering, filters, map, search, and FRUS index
- `assets/history-stack.js`: reusable twelve-layer entity rendering
- `assets/history-data.js`: shared loaders, escaping, badges, links, and cards
- `assets/portal.css`: responsive, accessible archival interface
- `assets/frus-subjects-index.js`: full metadata-only FRUS discovery index
- `data/history-stack/`: normalized pilot JSON modules
- `schemas/`: JSON schemas for core entity types
- `scripts/build_history_pilot.py`: reproducible editorial pilot builder
- `scripts/ingest_usgs_ds140.py`: official XLSX extractor
- `scripts/validate_history_data.py`: dates, references, provenance, and secret checks
- `connectors/nara.py`: server-side, metadata-only NARA API client
- `nara_proxy_worker.js`: deployable serverless proxy for the static site
- `local_server.py`: optional local NARA proxy

The original parser, scorer, taxonomy, compact event-cache, Records Studio, and
NARA image-support code remain available for compatible metadata workflows, but
the v2 homepage no longer uses the old post-1992 demonstration cache.

## Run Locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python scripts/build_history_pilot.py
python scripts/ingest_usgs_ds140.py
python scripts/validate_history_data.py
python -m http.server 8000
open http://localhost:8000/records-stage.html
```

The site must be served over HTTP because browsers do not allow modular JSON
`fetch()` calls from a `file://` page.

To test only with the committed datasets:

```bash
python -m http.server 8000
```

## Rebuild Official USGS Statistics

The extractor downloads eight official Data Series 140 workbooks and writes
human-readable JSON. It selects benchmark years through 1992, preserves USGS
units, and skips missing, withheld, estimated-text, and nonnumeric cells.

```bash
python scripts/ingest_usgs_ds140.py --access-date YYYY-MM-DD
python scripts/validate_history_data.py
```

Use `--cache-dir <path>` to retain downloaded XLSX files outside the repository.

## Configure NARA Safely

Create an ignored local file from the empty example:

```bash
cp .env.example .env.local
```

Set `NARA_API_KEY` in `.env.local` or export it in the environment. Never place
the key in `records-stage.html`, `assets/runtime-config.js`, browser JavaScript,
screenshots, logs, documentation, or a committed file.

Local proxy:

```bash
pip install flask flask-cors
python local_server.py --no-browser-open
```

When the site itself is served from `localhost` or `127.0.0.1`, the browser
automatically uses `http://localhost:5757` for NARA requests.

GitHub Pages cannot hold a server-side secret. Deploy `nara_proxy_worker.js` as a
serverless Worker, store the key as a secret named `NARA_API_KEY`, and put only
the public Worker URL in `assets/runtime-config.js`:

```js
window.HISTORY_RUNTIME_CONFIG = Object.freeze({
  naraProxyUrl: "https://your-worker.example"
});
```

NARA’s current API terms say not to cache or store returned API content, so v2
uses on-demand, `no-store` responses instead of a GitHub Actions cache. Static
query plans and authoritative Catalog links remain available if the API fails.
See [`docs/nara-integration.md`](docs/nara-integration.md).

## Add or Correct Historical Data

1. Add the official source to `data/history-stack/sources.json` through
   `scripts/build_history_pilot.py`.
2. Add or update the normalized entity and link existing IDs rather than copying
   descriptions into multiple files.
3. Preserve historical names, dates, units, official URLs, and completeness.
4. Leave unavailable fields empty and add a precise `data_gaps` note.
5. Rebuild statistics only from official machine-readable files or reviewed
   page-level transcriptions.
6. Run validation and tests before publication.

Core schemas are under `schemas/`. Crosswalks for aliases, HS codes, agencies,
countries, and supply-chain terms remain under `data/crosswalks/`. HS-code
mappings must retain confidence and caveats because product codes may not
identify mined origin.

## Rebuild the FRUS Subject Index

The index combines the subject mappings in
[`therealjameswilson/frus-subjects`](https://github.com/therealjameswilson/frus-subjects)
with official lightweight TOC files from
[`HistoryAtState/frus`](https://github.com/HistoryAtState/frus). It contains no
document body text.

```bash
python build_frus_subject_index.py \
  --subjects-root ../frus-subjects \
  --toc-root ../frus/frus-toc
```

See [`docs/frus-subject-index.md`](docs/frus-subject-index.md).

## Tests

```bash
. .venv/bin/activate
python -m pytest tests/ -v
python scripts/validate_history_data.py
```

Validation checks entity minimums, unique IDs, cross-file references, the
1861–1992 boundary, statistical provenance, `.env.example`, and tracked-file
secret patterns.

## Provenance

This repository is a standalone v2 adaptation of
[`therealjameswilson/toolkit-template`](https://github.com/therealjameswilson/toolkit-template),
which descends from the FRUS On This Day toolkit. The v1 repository remains
preserved at
[`therealjameswilson/critical-minerals-records-stage`](https://github.com/therealjameswilson/critical-minerals-records-stage).
