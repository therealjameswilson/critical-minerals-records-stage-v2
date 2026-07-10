# Country Intelligence Data Model

The country intelligence engine joins a historical entity in
`data/history-stack/countries.json` to an optional curated record in
`data/history-stack/country-briefs.json`. FRUS remains the first page layer and
the principal documentary source. Country briefs supply bounded orientation,
not an automatically generated historical narrative.

## Country brief schema

Each record contains:

- `country_id`: ID of the historical country or territory record.
- `default_year`: best-supported pilot year, always within 1861-1992.
- `baseline_facts`: political and diplomatic facts with fact-level status and
  provenance.
- `profile_periods`: dated overrides for offices or other facts that change.
- `relationship_periods`: curated periods linking resources, FRUS documents,
  instruments, NARA query plans, and official sources.
- `source_ids`, `mineral_ids`, `frus_document_ids`, `agreement_ids`, and
  `nara_query_ids`: normalized cross-file references.
- `data_gaps`: known omissions that the interface must display.

Fact objects use this shape:

```json
{
  "value": "President Salvador Allende",
  "status": "verified",
  "frus_document_id": "frus-1969-76v21-d250"
}
```

Allowed statuses are `verified`, `estimated`, and `unknown`. A verified fact
must carry either `source_id` or `frus_document_id`. An unknown fact must have
a null value. Estimated facts are supported by the schema but are not used in
the current pilot.

## Statistical boundary

The current USGS dataset contains U.S. and world commodity series, not
country-specific production or bilateral trade series. Country pages therefore
show country production, exports, U.S. import share, and world rank as unknown.
Nearby U.S. and world observations may appear as contextual benchmarks, always
with their actual source year, unit, agency, publication location, and URL.

No dependency ratio, supplier share, ranking, or relationship score is inferred
from those contextual series.

## Historical names and years

The selected year is read from the `year` query parameter and clamped to
1861-1992. The display name comes from the matching `names_by_period` entry in
the country record. A selected year does not imply that every fact shown was
measured in that year; period context and nearest-year statistical context are
visibly labeled.

## Pilot coverage

Curated pilot briefs currently cover:

- Bolivia, 1942
- Belgian Congo, 1953
- Indonesia, 1965
- Chile, 1971

The country interface also works for uncurated entities. In that case it keeps
the year control and linked evidence layers but marks the country-year brief as
a research queue.

## Adding a country-period record

1. Add or update the historical entity in `scripts/build_history_pilot.py`.
2. Add reviewed source-registry records and the country brief in
   `scripts/country_brief_data.py`.
3. Link only reviewed FRUS documents. Subject-index leads must retain their
   discovery status.
4. Record unknown values as unknown rather than omitting the evidentiary gap.
5. Run `python3 scripts/build_history_pilot.py`.
6. Run `python3 scripts/validate_history_data.py` and the test suite.

The official publication or archival record controls. The portal is an
orientation and discovery layer.
