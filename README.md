# Critical Minerals Records Stage

An FSO-facing historical-data and briefing tool for U.S. critical-minerals
diplomacy. It adapts the Records Toolkit Template into a standalone site that
helps users discover, filter, draft, clear, and export historically grounded
critical-minerals content.

Primary use cases include meeting prep, reporting, public diplomacy,
investment-climate work, historical context, talking points, evidence packs,
and follow-up to the 2026 Critical Minerals Ministerial.

## Provenance

This repo is adapted from
[therealjameswilson/toolkit-template](https://github.com/therealjameswilson/toolkit-template),
which itself descends from the FRUS On This Day toolkit. The core Records
Studio / Records Stage workflow, compact cache format, clearance table, Word
export, snapshots, and NARA image-search support are preserved.

## What It Does

The project turns structured metadata records into two artifacts:

- `events_cache.json`: full metadata cache grouped by calendar day.
- `records-stage.html`: standalone browser UI with embedded compact metadata,
  critical-minerals filters, draft generation, clearance status, image search,
  snapshots, and Word export.

The app is metadata-only by design. Do not put full FRUS, NARA, report, cable,
or article body text into the cache. Use titles, dates, summaries, subjects,
source URLs, citation URLs, identifiers, caveats, and confidence fields.

## Data Model

Each parser-emitted event must include:

- `source`
- `year`
- `month`
- `day`
- `title`
- `url`

Recommended event fields:

- `description`
- `subjects`
- `date_display`

Critical-minerals fields live under `event["extra"]`:

- `minerals: list[str]`
- `countries: list[str]`
- `agencies: list[str]`
- `source_type: FRUS | NARA | Census | USGS | DOE | DLA | Federal Register | State | Other USG`
- `evidence_type: historical_record | archival_record | trade_data | policy_document | statistical_release | ministerial_document`
- `supply_chain_stage: mining | processing | refining | recycling | trade | stockpiling | diplomacy | finance | permitting | infrastructure`
- `fso_use_case: meeting_prep | reporting | public_diplomacy | investment_climate | historical_context | talking_points`
- `hs_codes: list[str]`
- `record_id`
- `retrieved_at`
- `citation_url`
- `caveat`
- `confidence: high | medium | low`

The compact browser cache surfaces minerals, countries, source type, evidence
type, supply-chain stage, FSO use case, agencies, confidence, HS codes, citation
URLs, and caveats.

## Included Source Scaffolding

Starter sample data lives in `examples/critical_minerals_sample/` and includes
representative FRUS, NARA, Census, USGS, DOE, DLA, Federal Register, State
Department, partner-country, and ministerial follow-up records.

Starter crosswalks live under `data/crosswalks/`:

- `mineral_aliases.yml`
- `mineral_to_hs_codes.yml`
- `country_iso.yml`
- `source_tiers.yml`
- `agencies.yml`
- `supply_chain_stages.yml`

Connector stubs live under `connectors/`:

- `frus.py`
- `nara.py`
- `census_trade.py`
- `usgs.py`
- `doe.py`
- `dla.py`
- `federal_register.py`
- `state.py`

The stubs define input/output shape and TODOs only. They do not make live
network calls and do not contain API keys.

See `docs/critical-minerals-data-sources.md` for intended source-module use.

## Run The Demo

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python build_cache.py --source-root examples/critical_minerals_sample
python -m http.server 8000
open http://localhost:8000/records-stage.html
```

`build_cache.py` writes `events_cache.json` and `events_cache.js`, then syncs
the compact cache into `records-stage.html` unless `--skip-html-sync` is used.

## Records Studio

For the browser setup wrapper:

```bash
. .venv/bin/activate
streamlit run app.py
```

Records Studio walks through corpus connection, scoring, taxonomy, HTML
branding, and build/download steps.

## Records Stage

Open `records-stage.html` directly after a build, or serve the repo with a
simple local HTTP server. Use the evidence browser to filter by mineral,
country, source type, evidence type, supply-chain stage, FSO use case, agency,
year/date, and subject. Select records to draft meeting-prep cards, talking
points, public-diplomacy posts, evidence-pack notes, or questions for
counterparts.

Briefing mode is described in `docs/critical-minerals-briefing-mode.md`.

## NARA API Keys

NARA image search is optional and preserved from the template.

Never commit API keys. For local use, put a NARA Catalog API key in `.nara_key`
in the repo root. That file is ignored by git. For cloud proxy use, store the
key as a server-side secret, not in browser JavaScript or sample data.

If no key or proxy is configured, the static demo still works; NARA image
search simply shows a setup hint.

## Add A New Source

1. Add or update a connector stub under `connectors/`.
2. Return metadata-only records shaped like the sample JSON.
3. Include source URLs, citation URLs, record IDs, confidence, caveats, and
   retrieval dates.
4. Save records to JSON/CSV or feed them through a parser.
5. Run `python build_cache.py --source-root <path>`.
6. Verify the embedded `records-stage.html` before using outputs for review.

## Add A Mineral, HS Code, Source, Or Taxonomy Term

- Minerals and aliases: update `data/crosswalks/mineral_aliases.yml`.
- HS-code mappings: update `data/crosswalks/mineral_to_hs_codes.yml` with
  `confidence` and `caveat`.
- Countries: update `data/crosswalks/country_iso.yml`.
- Source tiers: update `data/crosswalks/source_tiers.yml`.
- Agencies: update `data/crosswalks/agencies.yml`.
- Supply-chain stages: update `data/crosswalks/supply_chain_stages.yml`.
- Subject filter taxonomy: update `taxonomy-critical-minerals.json`.

Then rebuild the cache.

## Tests

```bash
. .venv/bin/activate
python -m pytest tests/ -v
```

The critical-minerals tests cover parser contract output, date normalization,
compact extra fields, scoring integers, sample cache builds, and HS-code
crosswalk loading.
