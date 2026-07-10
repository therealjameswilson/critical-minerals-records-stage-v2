# Annual Atlas Coverage Plan, 1861-1992

## Objective

Provide a stable atlas view for every year from 1861 through 1992 without implying that every evidence type is equally complete. FRUS remains the documentary spine. Statistics, trade records, policy instruments, and archival discovery records explain the setting in which the diplomacy occurred.

The annual interface must answer two questions separately:

1. What evidence is checked in for this exact year and material?
2. What country or mineral relationships are known only at the broader profile level?

The map must never turn the second category into a claim about production, trade, supply, or dependence in the selected year.

## Implemented foundation

`scripts/build_annual_atlas.py` generates one record for each of the 132 selectable years. Every record also contains a separate evidence slice for every pilot material.

Each slice reports:

- FRUS records, separated into reviewed documents and discovery leads
- countries linked by exact-year or year-spanning evidence
- active historical episodes and documented access relationships
- dated agreements, laws, and stockpile pathways
- NARA query plans
- exact-year official statistics
- broad historical trade context
- commodity-specific Census, USGS, UN Comtrade, and USITC DataWeb rows
- profile-only country associations
- missing evidence lanes

Coverage labels are rule-based rather than scored:

- `document-plus-context`: at least one FRUS record and at least one statistical or trade record
- `documentary-only`: FRUS evidence without normalized statistical or trade context
- `context-only`: statistical or trade context without a matching checked-in FRUS record
- `sparse`: neither FRUS nor normalized statistical/trade context

## Acquisition plan

### 1. FRUS annual backbone

Generate a complete annual discovery index from the checked-in FRUS Subjects export, then review documents in policy-priority order. Preserve the distinction between subject-index leads and document-level review. Add document dates only when verified from the FRUS page or TEI source.

Priority review clusters:

- wartime procurement and shipping
- accessible foreign sources
- stockpile objectives and mobilization requirements
- production expansion and infrastructure finance
- nationalization, compensation, and investment disputes
- allied allocation and export controls

### 2. Production and use

Normalize annual country production from USGS and historical Bureau of Mines tables. Store mine, refined, and contained-material series separately. Required fields are country, historical country name, mineral, year, production basis, value, unit, publication, table or page, URL, transcription method, and confidence.

Do not interpolate missing years. Do not combine mine and refined output. Where only a regional total exists, retain the regional geography.

### 3. Trade by historical source era

Use the source appropriate to each period rather than forcing one classification backward:

- 1861-1913: Census and Treasury foreign-commerce publications; table-level transcription
- 1914-1961: Census `Foreign Commerce and Navigation of the United States` and historical statistical compendia
- 1962-1975: UN Comtrade SITC Revision 1, held as its own classification vintage
- 1976-1987: UN Comtrade SITC Revision 2, held separately
- 1988-1992: UN Comtrade SITC Revision 3 plus USITC DataWeb verification for U.S.-reported 1989-1992 values

Every series must preserve reporter, partner, direction, commodity code, classification revision, valuation basis, quantity unit, and original-versus-converted status. Mirror reports remain parallel observations.

### 4. Treaties, law, and stockpile policy

Add dated official records from State treaty publications, Statutes at Large, GovInfo, GSA, Defense, and congressional reports. A dated negotiation record must not be labeled a treaty. Stockpile goals, acquisitions, holdings, and disposals remain separate measures.

### 5. NARA discovery

Run the existing structured NARA queries through the secret-backed ingestion workflow. Store sanitized catalog metadata, retrieval dates, record groups, official URLs, and review status. Annual atlas counts must distinguish query plans from reviewed catalog results.

### 6. Historical geography

Add year-bounded country names and sovereignty status before adding historical boundary polygons. Country centroids remain country-level orientation. Mines, ports, railways, smelters, and routes require independently sourced coordinates and precision labels.

## Release sequence

1. Maintain a generated annual ledger for all 132 years.
2. Fill one representative year per decade with FRUS, statistics, law, and archival discovery.
3. Complete high-value episodes, including 1914-1918, 1939-1953, 1960-1976, and 1979-1992.
4. Backfill intervening years by official series, preserving classification and methodology breaks.
5. Promote a year from `partial` only after its citations, historical names, units, and missing-data statements pass review.

## Annual acceptance standard

An annual view is ready for public use when:

- the year and material have a generated evidence ledger
- FRUS coverage is labeled as reviewed, discovery-only, or absent
- every number exposes agency, publication, unit, year, and source URL
- map geography distinguishes year-linked evidence from profile context
- missing values are not shown as zero
- historical names are selected by year
- broad proxy commodities and converted classifications are visibly labeled
- the accessible table communicates the same evidence state as the map
- the view has no post-1992 historical data

The annual ledger is a coverage instrument, not a claim that the historical record is complete.
