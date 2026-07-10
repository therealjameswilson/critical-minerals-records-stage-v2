# Historical U.S. Trade Data Model

The Historical Geostrategic Atlas exposes a cited U.S. trade record for every
selectable year from 1861 through 1992. Coverage does not imply that one
compatible series exists across the entire period. The interface keeps two
official series separate and names their different scopes.

## 1861-1899: Census Economic-Class Context

The selected year is matched to a published five-year average in the U.S.
Department of Commerce, Bureau of the Census, *Statistical Abstract of the
United States: 1948*:

- Table 1013, pages 908-909: value of U.S. merchandise exports and general
  imports by economic class.
- Table 1014, page 910: percentage distribution by economic class.

The normalized rows reproduce the published values and shares for "crude
materials." This is a broad class that includes mineral and non-mineral raw
materials. It is not mineral-specific, bilateral, or an annual observation.
The interface states the published period and never interpolates an annual
value.

## 1900-1992: USGS Commodity Trade

The ingestion script downloads official U.S. Geological Survey Data Series 140
workbooks and extracts numeric imports and exports cells through 1992. Each row
retains:

- mineral and year;
- import or export direction;
- original USGS-standardized unit;
- commodity-specific worksheet header;
- worksheet row and column;
- publication and download URLs;
- access date and extraction method; and
- an explicit statement that the value is a national aggregate.

The current workbooks support aluminum, bauxite, chromium, cobalt, copper,
manganese, rare earth elements, tin, and tungsten. Uranium remains in the
portal because reviewed FRUS records support its diplomatic history, but no
compatible annual U.S. imports-and-exports workbook is currently normalized.
The interface reports that gap instead of omitting uranium from the mineral
system or treating missing values as zero.

## 1970-1990 Rare-Earth Census Recovery Series

The atlas includes a year-selectable series showing how legacy Census trade
reporting can be recovered without projecting modern HS categories backward.

The importer downloads and parses both official Rare Earths Statistical
Compendium text tables. Those tables name the Bureau of the Census as their
source:

- Table 3 supplies annual import quantity and current-dollar value for eight
  published product categories and a published total from 1970 through 1990.
- Table 4 supplies annual export quantity for four published product
  categories and a published total over the same years.

This produces 294 normalized detail rows: fourteen rows for each of twenty-one
years. Values retain the source's `NA`, dash, and footnote states. A published
dash is not converted to zero, a less-than value is not rounded upward, and a
category that was not separately available remains null.

The contemporaneous totals are displayed beside, but never merged with, the
later USGS Data Series 140 standardized values. Data Series 140 uses
rare-earth-oxide equivalent; the contemporaneous export table includes thorium
ore and concentrates. The scopes are therefore materially different. The
source also warns that 1989 and 1990 categories are not necessarily comparable
with earlier years after implementation of the Harmonized Tariff System.

`trade-research.json` records the next acquisition step rather than inventing
supplier countries. Each year from 1970 through 1990 has a separate queue for:

- FT 246, *U.S. Imports for Consumption and General Imports, TSUSA Commodity
  by Country of Origin*; and
- FT 446, *U.S. Exports, Schedule B Commodity by Country*.

No country flow is drawn on the atlas until those annual rows, classifications,
quantities, valuation bases, and report locations have been reviewed. The
published year-and-direction totals serve as controls for that future
transcription.

The generated detail row retains both a normalized category and the source
label, quantity and value measurement objects, original source symbol, table
URL, access date, extraction status, and applicable classification caveats.

## 1962-1992 UN Comtrade Partner Context

UN Comtrade provides official international reporter-partner merchandise trade
statistics from 1962. It is a Tier 2 contextual source in this portal: FRUS
remains the documentary spine, and USITC DataWeb remains the authoritative
U.S.-reported verification layer where its electronic series is available.

The strategic-material pilot contains 2,010 U.S.-reported observations from 31
annual queries. It covers aluminum, bauxite, chromium, cobalt, copper,
manganese, tin, tungsten, and uranium for the world and selected countries
already represented in the atlas. The audited code registry is
`data/crosswalks/comtrade_sitc_mineral_codes.yml`.

The strategic-material layer distinguishes ores and concentrates, compounds,
intermediates, ferroalloys, unwrought metals, alloys, waste, and articles. Gross
product values and weights are never converted to contained-mineral quantities.
The map may display reported partner value, but it does not interpret that value
as mine origin, U.S. dependence, or strategic importance.

The separate rare-earth pilot contains 177 observations recovered from 40
year-and-reporter queries. It uses:

- SITC Revision 1 for 1962-1975;
- SITC Revision 2 for 1976-1987; and
- SITC Revision 3 for 1988-1992.

Each revision remains a separate vintage. The project does not splice them into
a continuous numeric series. The historical baskets are preserved as distinct
product families because several are materially broader than rare-earth trade:

- metals proxies may also contain alkali, alkaline-earth, calcium, strontium,
  or barium trade;
- the Revision 2 compounds proxy includes thorium and depleted-uranium
  compounds;
- the magnet-system proxy includes electromagnets, work holders, couplings,
  brakes, and lifting heads; and
- the pyrophoric-alloy proxy includes prepared fuels as well as ferrocerium.

The interface displays U.S.-reported trade with China and the world. It also
displays China-reported mirror flows where Comtrade contains them. Mirror
values remain separate because import and export valuation, timing, routing,
transshipment, and origin rules differ. Converted classifications are visibly
labeled and never presented as the reporter's original commodity coding.

Every observation retains reporter, partner, flow, classification revision,
commodity code and description, product-family scope, current-dollar value,
reported quantity, net weight, estimation flags, original-versus-converted
status, query identifier, access date, and source URL. Zero-result query years
remain in the manifest so absence of a displayed row is not confused with an
unattempted query.

The UNCCD Knowledge Hub entry supplied during source discovery identifies UN
Statistics Division as the managing entity and links to UN Comtrade. It is
retained as a discovery URL, not treated as the publisher of the statistical
records.

Official references:

- [UN Comtrade](https://comtradeplus.un.org/)
- [UNCCD Knowledge Hub discovery entry](https://www.unccd.int/resources/knowledge-sharing-system/united-nations-commodity-trade-statistics-database-un-comtrade)
- [UNSD historical classification and availability explanation](https://unstats.un.org/unsd/trade/dataextract/dataclass.htm)
- [UN Comtrade methodology guide](https://comtradeapi.un.org/files/v1/app/wiki/MethodologyGuideforComtradePlus.pdf)

## 1989-1992 USITC DataWeb Partner Trade

USITC DataWeb supplies the first checked-in partner-country layer. DataWeb
provides official U.S. merchandise trade statistics published by the Department
of Commerce, Census Bureau, and states that its electronic trade series begins
in 1989. The portal therefore uses only 1989-1992, the overlap between DataWeb
and the project's historical boundary.

The importer runs two annual country-breakout queries:

- imports for consumption, with customs value and first quantity; and
- total exports, with F.A.S. value and first quantity.

It queries 32 six-digit Harmonized System headings associated with the ten
pilot mineral profiles. Imports are classified in the HTS and exports in
Schedule B; only the shared six-digit international level is compared. The
response-supplied historical commodity description is retained on every row.
The checked-in cache contains 3,669 positive partner-product records, including
rare-earth and uranium headings that were absent from the earlier national
aggregate display.

Each row preserves the source partner name, DataWeb country code, ISO codes,
flow definition, commodity code and description, customs or F.A.S. valuation
basis, first quantity and unit, source URL, access date, and a scope caveat.
The query manifest records the exact years, commodity headings, record count,
and a SHA-256 hash of the submitted payload.

The atlas only draws these quantitative lines when the DataWeb lens is selected.
Country shading and line width represent reported import customs value summed
across the selected headings. They do not represent import dependence,
production, reserves, strategic importance, mine origin, ownership, route, or
end use. Exports remain in the accessible U.S. Trade table rather than being
combined with imports on the map.

The official source pages are:

- [USITC DataWeb](https://dataweb.usitc.gov/)
- [About DataWeb](https://www.usitc.gov/applications/dataweb/about)
- [DataWeb FAQs](https://www.usitc.gov/applications/dataweb/faqs)
- [DataWeb API guide](https://www.usitc.gov/applications/dataweb/api/dataweb_query_api.html)

Suggested source form follows USITC guidance: compiled using USITC DataWeb from
official U.S. merchandise trade statistics published by the U.S. Department of
Commerce, Census Bureau, with the access date shown in the portal.

## Record Shape

Each object in `data/history-stack/trade.json` includes:

```json
{
  "year_start": 1942,
  "year_end": 1942,
  "temporal_precision": "annual",
  "direction": "imports",
  "metric": "U.S. imports",
  "material_scope": "commodity",
  "mineral_id": "tin",
  "partner_scope": "World aggregate; partner countries are not identified in this row.",
  "value": 27200,
  "unit": "metric tons (t) tin content",
  "agency": "U.S. Geological Survey",
  "table_or_page": "Tin worksheet, row 48, column 4 (Imports)",
  "source_url": "https://www.usgs.gov/media/files/tin-historical-statistics-data-series-140",
  "transcription_status": "machine-extracted-xlsx",
  "confidence": "high"
}
```

This example reproduces the committed 1942 U.S. tin-import row. The committed
JSON and official workbook control if the source series is refreshed.

## Data Rules

1. Do not combine the Census and USGS series into a continuous chart.
2. Do not merge Comtrade classification revisions, product families, or mirror reports.
3. Do not infer routes, mine origin, ownership, end use, or strategic importance from a reported partner.
4. Do not convert physical units or current dollars without a separate,
   documented transformation record.
5. Do not treat missing, withheld, or nonnumeric cells as zero.
6. Do not use a period average as an exact-year observation.
7. Preserve publication, table or worksheet location, access date, original
   unit, and extraction status.

## Refresh and Validation

```bash
python scripts/ingest_trade_data.py --access-date YYYY-MM-DD
python scripts/build_trade_pilot.py --access-date YYYY-MM-DD --cache-dir .cache/rare-earth-trade
python scripts/ingest_un_comtrade_rare_earth.py --access-date YYYY-MM-DD --cache-dir .cache/un-comtrade
python scripts/ingest_usitc_dataweb.py --access-date YYYY-MM-DD --cache-dir .cache/usitc-dataweb
python scripts/validate_history_data.py
python -m pytest tests/ -q
```

Validation fails if a trade row falls outside 1861-1992, references an unknown
source or mineral, loses a required provenance field, or leaves a selectable
year without any official trade context.
