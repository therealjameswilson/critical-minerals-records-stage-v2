(function () {
  "use strict";

  const H = window.HistoryData;
  const $ = (id) => document.getElementById(id);
  const TYPE_MAP = {
    mineral: "minerals", country: "countries", episode: "episodes",
    agreement: "agreements", law: "laws", administration: "administrations",
    stockpile: "stockpile-cases", frus: "frus-documents"
  };
  let data;
  let entity;
  let dataset;
  let entityType;
  let countryBrief;
  let selectedYear;

  function activePeriod(periods) {
    return (periods || []).find((row) => row.start <= selectedYear && row.end >= selectedYear) || null;
  }

  function activeRelationship() {
    return countryBrief ? activePeriod(countryBrief.relationship_periods) : null;
  }

  function activeProfile() {
    return countryBrief ? activePeriod(countryBrief.profile_periods) : null;
  }

  function relatedIds(field) {
    return Array.isArray(entity[field]) ? entity[field] : [];
  }

  function relatedRows(type, field) {
    return relatedIds(field).map((id) => data.indexes[type].get(id)).filter(Boolean);
  }

  function inferMineralIds() {
    if (dataset === "minerals") return [entity.id];
    return relatedIds("mineral_ids");
  }

  function inferCountryIds() {
    if (dataset === "countries") return [entity.id];
    return relatedIds("country_ids");
  }

  function inferFrusRows() {
    if (dataset === "frus-documents") return [entity];
    return relatedRows("frus-documents", "frus_document_ids");
  }

  function inferAgreements() {
    if (dataset === "agreements") return [entity];
    return relatedRows("agreements", "agreement_ids");
  }

  function inferLaws() {
    if (dataset === "laws") return [entity];
    return relatedRows("laws", "law_ids");
  }

  function inferEpisodes() {
    if (dataset === "episodes") return [entity];
    const direct = relatedRows("episodes", "episode_ids");
    if (direct.length) return direct;
    return data.episodes.filter((row) => inferFrusRows().some((frus) => row.frus_document_ids.includes(frus.id)));
  }

  function inferAdministrations() {
    if (dataset === "administrations") return [entity];
    const frusIds = new Set(inferFrusRows().map((row) => row.id));
    return data.administrations.filter((row) => row.frus_document_ids.some((id) => frusIds.has(id)));
  }

  function inferStockpileCases() {
    if (dataset === "stockpile-cases") return [entity];
    const mineralIds = new Set(inferMineralIds());
    const frusIds = new Set(inferFrusRows().map((row) => row.id));
    return data["stockpile-cases"].filter((row) => row.mineral_ids.some((id) => mineralIds.has(id)) || row.frus_document_ids.some((id) => frusIds.has(id)));
  }

  function inferNaraQueries() {
    const relationship = activeRelationship();
    if (dataset === "countries" && relationship?.nara_query_ids?.length) {
      return relationship.nara_query_ids.map((id) => data.indexes["nara-queries"].get(id)).filter(Boolean);
    }
    const direct = relatedRows("nara-queries", "nara_query_ids");
    if (direct.length) return direct;
    const mineralIds = new Set(inferMineralIds());
    const countryIds = new Set(inferCountryIds());
    return data["nara-queries"].filter((row) => row.mineral_ids.some((id) => mineralIds.has(id)) || row.country_ids.some((id) => countryIds.has(id))).slice(0, 8);
  }

  function inferStatistics() {
    if (dataset === "frus-documents" && entity.statistic_ids.length) {
      const wanted = new Set(entity.statistic_ids);
      return data.statistics.filter((row) => wanted.has(row.id));
    }
    const relationship = activeRelationship();
    const mineralIds = new Set(dataset === "countries" && relationship ? relationship.mineral_ids : inferMineralIds());
    let rows = data.statistics.filter((row) => mineralIds.has(row.mineral_id));
    if (dataset === "countries") {
      const officialContext = rows.filter((row) => row.country_id === "united-states" || row.country_id == null);
      const exact = officialContext.filter((row) => row.year === selectedYear);
      if (exact.length) return exact;
      const years = [...new Set(officialContext.map((row) => row.year))]
        .sort((a, b) => Math.abs(a - selectedYear) - Math.abs(b - selectedYear) || a - b);
      const nearest = years[0];
      return Number.isFinite(nearest) && Math.abs(nearest - selectedYear) <= 5
        ? officialContext.filter((row) => row.year === nearest)
        : [];
    }
    const start = entity.start || entity.volume_year_start || entity.historical_scope?.start;
    const end = entity.end || entity.volume_year_end || entity.historical_scope?.end;
    if (dataset !== "minerals" && start && end) rows = rows.filter((row) => row.year >= start && row.year <= end);
    return rows;
  }

  function sourceRows() {
    const ids = new Set(relatedIds("source_ids"));
    if (countryBrief) countryBrief.source_ids.forEach((id) => ids.add(id));
    const relationship = activeRelationship();
    if (relationship) relationship.source_ids.forEach((id) => ids.add(id));
    inferFrusRows().forEach((row) => row.source_ids.forEach((id) => ids.add(id)));
    if (inferStatistics().length) ids.add("usgs-ds140");
    if (inferNaraQueries().length) ids.add("nara-catalog-api");
    return [...ids].map((id) => data.indexes.sources.get(id)).filter(Boolean);
  }

  function summary() {
    if (dataset === "countries") {
      const relationship = activeRelationship();
      return relationship?.why_mattered || `No curated country-year interpretation is available for ${selectedYear}. The page preserves linked FRUS and official-source discovery records as a research queue.`;
    }
    if (entity.summary) return entity.summary;
    if (entity.contextual_summary) return entity.contextual_summary;
    if (entity.strategic_uses?.length) return entity.strategic_uses[0].use;
    if (entity.data_gaps?.length) return `Pilot coverage is incomplete. ${entity.data_gaps[0]}`;
    return "This record connects the FRUS narrative to available official historical context.";
  }

  function layer(number, id, title, status, body) {
    const displayNumber = dataset === "countries" && !["frus-layer", "country-brief-layer"].includes(id)
      ? String(Number(number) + 1).padStart(2, "0") : number;
    if (dataset === "countries") {
      const open = ["frus-layer", "country-brief-layer"].includes(id) ? " open" : "";
      return `<section class="stack-layer collapsible-layer" id="${id}"><details${open}><summary class="layer-heading"><span class="layer-number">${displayNumber}</span><span class="layer-title" role="heading" aria-level="2">${H.escape(title)}</span>${H.completenessBadge(status || "partial")}<span class="layer-toggle" aria-hidden="true"></span></summary><div class="layer-body">${body}</div></details></section>`;
    }
    return `<section class="stack-layer" id="${id}" aria-labelledby="${id}-title"><header class="layer-heading"><span class="layer-number">${displayNumber}</span><h2 id="${id}-title">${H.escape(title)}</h2>${H.completenessBadge(status || "partial")}</header><div class="layer-body">${body}</div></section>`;
  }

  function empty(message) {
    return `<div class="research-gap"><p class="empty-note">${H.escape(message)}</p>${H.badge("Research queue", "queue")}</div>`;
  }

  function countryYearControls() {
    return `<div class="country-year-toolbar" aria-label="Country briefing year">
      <button class="year-step" id="previousCountryYear" type="button" aria-label="Previous year">&#8722;</button>
      <div class="country-year-range"><label for="countryYearRange">Briefing year <strong id="countryYearLabel">${selectedYear}</strong></label><input id="countryYearRange" type="range" min="1861" max="1992" step="1" value="${selectedYear}"></div>
      <div class="country-year-number"><label for="countryYearNumber">Year</label><input id="countryYearNumber" type="number" min="1861" max="1992" step="1" value="${selectedYear}"></div>
      <button class="year-step" id="nextCountryYear" type="button" aria-label="Next year">+</button>
    </div>`;
  }

  function briefSection(title, body, open) {
    return `<details class="brief-section"${open ? " open" : ""}><summary>${H.escape(title)}<span aria-hidden="true"></span></summary><div>${body}</div></details>`;
  }

  function renderFact(label, fact) {
    if (!fact || fact.status === "unknown" || fact.value == null) {
      return `<div class="brief-fact is-unknown"><dt>${H.escape(label)}</dt><dd>Unknown ${H.badge("Unknown", "queue")}${fact?.note ? `<small>${H.escape(fact.note)}</small>` : ""}</dd></div>`;
    }
    const source = fact.source_id ? data.indexes.sources.get(fact.source_id) : null;
    const frus = fact.frus_document_id ? data.indexes["frus-documents"].get(fact.frus_document_id) : null;
    const citation = source ? `<a href="${H.escape(source.url)}" target="_blank" rel="noopener">${H.escape(source.label)}</a>` :
      frus ? `<a href="${H.escape(frus.stable_url)}" target="_blank" rel="noopener">FRUS ${H.escape(frus.volume)}, document ${H.escape(frus.document_number)}</a>` : "Source link pending";
    return `<div class="brief-fact"><dt>${H.escape(label)}</dt><dd>${H.escape(fact.value)} ${H.badge("Verified", "verified")}<small>${citation}${fact.note ? ` · ${H.escape(fact.note)}` : ""}</small></dd></div>`;
  }

  function statisticCell(row) {
    if (!row) return '<span class="unknown-value">Unknown</span>';
    return `<strong>${H.escape(H.formatNumber(row.value))}</strong><small>${H.escape(row.unit)} · ${row.year}<br><a href="${H.escape(row.source_url)}" target="_blank" rel="noopener">${H.escape(row.agency)}, ${H.escape(row.table_or_page)}</a></small>`;
  }

  function renderCountryCommodityTable(relationship) {
    const ids = relationship?.mineral_ids?.length ? relationship.mineral_ids : (countryBrief?.mineral_ids || entity.mineral_ids || []);
    if (!ids.length) return empty("No strategic resource is linked to this country-year briefing.");
    const context = inferStatistics();
    const rows = ids.map((id) => {
      const mineral = data.indexes.minerals.get(id);
      const mineralRows = context.filter((row) => row.mineral_id === id);
      const imports = mineralRows.find((row) => /^U\.S\. imports$/i.test(row.metric));
      const world = mineralRows.find((row) => /^World (mine )?production$/i.test(row.metric));
      const contextYear = imports?.year || world?.year;
      return `<tr><th scope="row"><a href="${H.detailHref("minerals", id)}">${H.escape(mineral?.canonical_name || id)}</a>${contextYear && contextYear !== selectedYear ? `<small>Nearest official benchmark: ${contextYear}</small>` : ""}</th><td><span class="unknown-value">Unknown</span></td><td><span class="unknown-value">Unknown</span></td><td><span class="unknown-value">Unknown</span></td><td><span class="unknown-value">Unknown</span></td><td>${statisticCell(imports)}</td><td>${statisticCell(world)}</td></tr>`;
    }).join("");
    return `<p class="table-scope-note"><strong>Scope:</strong> Country production, exports, U.S. import share, and world rank remain unknown unless a country-specific official series is normalized. U.S. and world figures are context, not bilateral evidence.</p><div class="data-table-wrap country-commodity-table"><table><caption>Country evidence and official U.S. or world commodity context for ${selectedYear}</caption><thead><tr><th>Resource</th><th>Country production</th><th>Country exports</th><th>Share of U.S. imports</th><th>World rank</th><th>U.S. imports</th><th>World production</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  function renderCountryScorecard(relationship) {
    const frus = relationship ? relationship.frus_document_ids.map((id) => data.indexes["frus-documents"].get(id)).filter(Boolean) : [];
    const agreements = relationship ? relationship.agreement_ids.map((id) => data.indexes.agreements.get(id)).filter(Boolean) : [];
    const nara = relationship ? relationship.nara_query_ids.map((id) => data.indexes["nara-queries"].get(id)).filter(Boolean) : [];
    const statistics = inferStatistics();
    const contextYear = statistics[0]?.year;
    const indicators = [
      ["Principal strategic commodities", relationship?.resource_terms?.join(", ") || "Unknown", relationship ? "supported" : "unknown"],
      ["U.S. dependence", "Unknown; no bilateral supplier-share series normalized", "unknown"],
      ["World production significance", "Unknown for this country", "unknown"],
      ["FRUS documentary coverage", `${frus.length} reviewed record${frus.length === 1 ? "" : "s"} linked to this period`, frus.length ? "supported" : "unknown"],
      ["Treaty or instrument coverage", `${agreements.length} linked instrument${agreements.length === 1 ? "" : "s"}`, agreements.length ? "limited" : "unknown"],
      ["NARA archival discovery", `${nara.length} structured query plan${nara.length === 1 ? "" : "s"}; results require review`, nara.length ? "limited" : "unknown"],
      ["Official statistical context", statistics.length ? `${statistics.length} U.S./world observations for ${contextYear}${contextYear === selectedYear ? "" : " (nearest source year)"}` : "No nearby benchmark normalized", statistics.length ? "limited" : "unknown"],
      ["Strategic stockpile relevance", "Unknown unless documented in a linked instrument or stockpile case", "unknown"]
    ];
    return `<div class="country-scorecard">${indicators.map(([label, value, status]) => `<div><span>${H.escape(label)}</span><strong>${H.escape(value)}</strong>${H.badge(status === "supported" ? "Supported" : status === "limited" ? "Limited evidence" : "Unknown", status === "supported" ? "verified" : status === "limited" ? "partial" : "queue")}</div>`).join("")}</div>`;
  }

  function renderCountryBriefLayer() {
    const relationship = activeRelationship();
    if (!countryBrief) {
      return layer("02", "country-brief-layer", `Country intelligence brief · ${selectedYear}`, "research-queue", `${countryYearControls()}${empty("No curated country-year brief has been added for this country. Linked FRUS, NARA, and source records remain available below.")}`);
    }
    const profile = activeProfile();
    const facts = { ...countryBrief.baseline_facts, ...(profile?.facts || {}) };
    const factLabels = {
      official_name: "Official name", political_status: "Political status", government_type: "Government type",
      head_of_state: "Head of state", head_of_government: "Head of government", capital: "Capital",
      population: "Population", area: "Area", currency: "Currency", official_languages: "Official languages",
      recognition: "U.S. recognition", embassy_status: "Embassy status", major_diplomatic_change: "Major diplomatic change"
    };
    const factGrid = `<dl class="brief-fact-grid">${Object.entries(factLabels).map(([key, label]) => renderFact(label, facts[key])).join("")}</dl>`;
    const frusCount = relationship?.frus_document_ids?.length || 0;
    const agreementCount = relationship?.agreement_ids?.length || 0;
    const naraCount = relationship?.nara_query_ids?.length || 0;
    const policyNumbers = `<div class="policy-number-grid"><div><span>Historical name</span><strong>${H.escape(historicalName(entity, selectedYear))}</strong></div><div><span>Strategic resources linked</span><strong>${relationship?.mineral_ids?.length || 0}</strong></div><div><span>Reviewed FRUS records</span><strong>${frusCount}</strong></div><div><span>Linked instruments</span><strong>${agreementCount}</strong></div><div><span>NARA query plans</span><strong>${naraCount}</strong></div><div><span>Country statistical series</span><strong>0</strong><small>Unknown, not estimated</small></div></div>`;
    const instruments = relationship ? relationship.agreement_ids.map((id) => data.indexes.agreements.get(id)).filter(Boolean) : [];
    const nara = relationship ? relationship.nara_query_ids.map((id) => data.indexes["nara-queries"].get(id)).filter(Boolean) : [];
    const relationshipBody = relationship ? `<div class="brief-thesis"><div>${H.badge("Editorial synthesis", "concept")} ${H.badge(relationship.evidence_status === "verified-pilot" ? "Reviewed evidence" : "Partial evidence", relationship.evidence_status === "verified-pilot" ? "verified" : "partial")}</div><h3>${H.escape(relationship.title)}</h3><p>${H.escape(relationship.why_mattered)}</p></div><dl class="relationship-summary"><div><dt>Strategic-resource profile</dt><dd>${H.escape(relationship.resource_summary)}</dd></div><div><dt>U.S.-country resource trade</dt><dd>${H.escape(relationship.trade_summary)}</dd></div><div><dt>Diplomatic relationship</dt><dd>${H.escape(relationship.diplomatic_summary)}</dd></div><div><dt>Documented instruments</dt><dd>${H.escape(relationship.instrument_labels.join("; "))}</dd></div></dl>` : empty(`No curated relationship episode covers ${selectedYear}. The absence of a brief does not establish an absence of U.S. interest or activity.`);
    const instrumentBody = instruments.length ? `<div class="record-list">${instruments.map(agreementCard).join("")}</div>` : empty("No treaty, agreement, or policy instrument is linked to this country-year.");
    const naraBody = nara.length ? `<ul class="brief-link-list">${nara.map((row) => `<li><strong>RG ${H.escape(row.record_groups.join(", "))}</strong><span>${H.escape(row.label)}</span><a href="https://catalog.archives.gov/search?q=${encodeURIComponent(row.query)}" target="_blank" rel="noopener">Search NARA Catalog</a></li>`).join("")}</ul>` : empty("No structured NARA query plan is linked to this country-year.");
    const gaps = [...new Set([...(countryBrief.data_gaps || []), ...(entity.data_gaps || [])])];
    const body = `${countryYearControls()}${relationshipBody}${briefSection("Political profile", factGrid, true)}${briefSection("Policy in Numbers and commodity evidence", `${policyNumbers}${renderCountryCommodityTable(relationship)}`, true)}${briefSection("Treaties, agreements, and policy instruments", instrumentBody, false)}${briefSection("NARA archival discovery", naraBody, false)}${briefSection("Strategic Resource Relationship Scorecard", renderCountryScorecard(relationship), false)}${briefSection("Data gaps and research still needed", `<ul class="gap-list">${gaps.map((gap) => `<li>${H.escape(gap)}</li>`).join("")}</ul>`, false)}`;
    return layer("02", "country-brief-layer", `Country intelligence brief · ${selectedYear}`, relationship ? relationship.evidence_status : "research-queue", body);
  }

  function renderFrusLayer() {
    const relationship = activeRelationship();
    const relationshipIds = new Set(relationship?.frus_document_ids || []);
    const rows = inferFrusRows().sort((a, b) => {
      const aPriority = relationshipIds.has(a.id) ? 0 : 1;
      const bPriority = relationshipIds.has(b.id) ? 0 : 1;
      return aPriority - bPriority || (a.date || `${a.volume_year_start}`).localeCompare(b.date || `${b.volume_year_start}`);
    });
    let orientation = "";
    if (dataset === "minerals" && rows.length) {
      const first = rows[0];
      orientation = `<p class="orientation-note"><strong>First appearance in this pilot:</strong> ${H.escape(first.title || first.volume_context)} (${first.date || `${first.volume_year_start}–${first.volume_year_end}`}). ${first.metadata_status === "subject-index-lead" ? "This is a discovery-index appearance, not yet a document-level finding." : "This record has document-level pilot metadata."}</p>`;
    }
    if (dataset === "countries") {
      const exact = rows.filter((row) => row.date && Number(row.date.slice(0, 4)) === selectedYear).length;
      orientation = `<p class="orientation-note"><strong>FRUS remains the documentary backbone.</strong> ${exact ? `${exact} reviewed document${exact === 1 ? "" : "s"} date${exact === 1 ? "s" : ""} to ${selectedYear}.` : `No reviewed document is dated exactly to ${selectedYear}.`} ${relationshipIds.size ? `${relationshipIds.size} record${relationshipIds.size === 1 ? " is" : "s are"} linked to the active country-period briefing.` : "Other country records remain visible as longer historical context."}</p>`;
    }
    return layer("01", "frus-layer", "FRUS narrative", rows.some((row) => row.metadata_status === "verified-document") ? "verified-pilot" : "research-queue", orientation + (rows.length ? `<div class="record-list">${rows.map((row) => H.frusCard(row, false)).join("")}</div>` : empty("No FRUS document is linked to this pilot entity yet.")));
  }

  function renderTimelineLayer() {
    const episodes = inferEpisodes();
    const administrations = inferAdministrations();
    const countryItems = dataset === "countries" ? [
      ...(entity.sovereignty_changes || []).map((row) => ({ date: row.year, end: row.year, title: "Political-status change", summary: row.note, href: null, label: "Country history" })),
      ...inferFrusRows().filter((row) => row.date).map((row) => ({ date: Number(row.date.slice(0, 4)), end: Number(row.date.slice(0, 4)), title: row.title, summary: row.contextual_summary || row.volume_context, href: H.detailHref("frus-documents", row.id), label: "FRUS document" })),
      ...inferAgreements().filter((row) => row.signature_date).map((row) => ({ date: Number(row.signature_date.slice(0, 4)), end: Number(row.signature_date.slice(0, 4)), title: row.short_title, summary: row.summary, href: H.detailHref("agreements", row.id), label: "Instrument" }))
    ] : [];
    const items = [
      ...countryItems,
      ...episodes.map((row) => ({ date: row.start, end: row.end, title: row.title, summary: row.summary, href: H.detailHref("episodes", row.id), label: "Episode" })),
      ...administrations.map((row) => ({ date: row.start, end: row.end, title: `${row.president} administration`, summary: row.summary, href: H.detailHref("administrations", row.id), label: "Administration" }))
    ].sort((a, b) => a.date - b.date);
    const body = items.length ? `<ol class="detail-timeline">${items.map((item) => `<li><span>${item.date === item.end ? item.date : `${item.date}–${item.end}`}</span><div>${H.badge(item.label, "concept")}<h3>${item.href ? `<a href="${item.href}">${H.escape(item.title)}</a>` : H.escape(item.title)}</h3><p>${H.escape(item.summary)}</p></div></li>`).join("")}</ol>` : empty("No period or administration record is linked yet.");
    return layer("02", "timeline-layer", "Historical timeline", items.length ? "partial" : "research-queue", body);
  }

  function chartSvg(rows, metric) {
    const points = rows.filter((row) => row.metric === metric).sort((a, b) => a.year - b.year);
    if (points.length < 2) return empty("Fewer than two comparable observations are available for this metric.");
    const width = 800, height = 260, left = 64, right = 18, top = 16, bottom = 38;
    const minYear = Math.min(...points.map((row) => row.year));
    const maxYear = Math.max(...points.map((row) => row.year));
    const minValue = Math.min(...points.map((row) => row.value));
    const maxValue = Math.max(...points.map((row) => row.value));
    const spanYear = Math.max(1, maxYear - minYear);
    const spanValue = Math.max(1, maxValue - minValue);
    const xy = (row) => ({ x: left + ((row.year - minYear) / spanYear) * (width - left - right), y: top + (1 - ((row.value - minValue) / spanValue)) * (height - top - bottom) });
    const path = points.map((row, index) => `${index ? "L" : "M"}${xy(row).x.toFixed(1)},${xy(row).y.toFixed(1)}`).join(" ");
    const unit = points[0].unit;
    return `<div class="chart-shell"><svg viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="chart-title chart-desc"><title id="chart-title">${H.escape(metric)}, ${minYear} to ${maxYear}</title><desc id="chart-desc">${points.length} USGS observations in ${H.escape(unit)}. A table follows the chart.</desc><path class="chart-grid" d="M${left} ${top}V${height-bottom}H${width-right}M${left} ${top}H${width-right}M${left} ${(top+height-bottom)/2}H${width-right}"></path><path class="chart-axis" d="M${left} ${top}V${height-bottom}H${width-right}"></path><path class="chart-line" d="${path}"></path>${points.map((row) => { const point = xy(row); return `<circle class="chart-point" cx="${point.x}" cy="${point.y}" r="4"><title>${row.year}: ${H.formatNumber(row.value)} ${H.escape(row.unit)}</title></circle>`; }).join("")}<text class="chart-label" x="${left}" y="${height-12}">${minYear}</text><text class="chart-label" x="${width-right}" y="${height-12}" text-anchor="end">${maxYear}</text><text class="chart-label" x="${left-8}" y="${top+4}" text-anchor="end">${H.escape(H.formatNumber(maxValue))}</text><text class="chart-label" x="${left-8}" y="${height-bottom}" text-anchor="end">${H.escape(H.formatNumber(minValue))}</text></svg></div>`;
  }

  function renderStatisticsLayer() {
    const rows = inferStatistics();
    const title = dataset === "countries" ? "Official statistics: U.S. and world context" : "Official statistics";
    if (!rows.length) return layer("03", "statistics-layer", title, "research-queue", empty("No compatible, unit-defined official statistical series is linked to this entity yet."));
    const metrics = [...new Set(rows.map((row) => row.metric))].sort();
    const metric = metrics.find((item) => rows.filter((row) => row.metric === item).length >= 2) || metrics[0];
    const table = `<div class="data-table-wrap"><table><caption class="visually-hidden">Official statistics with units and provenance</caption><thead><tr><th>Year</th><th>Metric</th><th>Value</th><th>Unit</th><th>Agency</th><th>Publication location</th></tr></thead><tbody>${rows.slice(0, 200).map((row) => `<tr><td>${row.year}</td><td>${H.escape(row.metric)}</td><td>${H.formatNumber(row.value)}</td><td>${H.escape(row.unit)}</td><td>${H.escape(row.agency)}</td><td><a href="${H.escape(row.source_url)}" target="_blank" rel="noopener">${H.escape(row.table_or_page)}</a></td></tr>`).join("")}</tbody></table></div>`;
    const contextNote = dataset === "countries" ? `<p class="orientation-note"><strong>Context only:</strong> These are U.S. and world commodity observations for ${rows[0].year}${rows[0].year === selectedYear ? "" : `, the nearest normalized source year to ${selectedYear}`}. They are not statistics for ${H.escape(historicalName(entity, selectedYear))} and are not used to calculate bilateral dependence.</p>` : "";
    const body = `${contextNote}<div class="stat-toolbar"><div class="control"><label for="detailMetric">Chart metric</label><select id="detailMetric">${metrics.map((item) => `<option value="${H.escape(item)}"${item === metric ? " selected" : ""}>${H.escape(item)}</option>`).join("")}</select></div><p>${rows.length} observations. No project interpolation; original USGS-standardized units retained.</p></div><div id="detailChart">${chartSvg(rows, metric)}</div>${table}`;
    return layer("03", "statistics-layer", title, "verified-pilot", body);
  }

  function agreementCard(row) {
    return `<article class="instrument-card"><div>${H.badge(row.record_type.replaceAll("-", " "), "concept")} ${H.completenessBadge(row.completeness)}</div><h3><a href="${H.detailHref("agreements", row.id)}">${H.escape(row.official_title)}</a></h3><p>${H.escape(row.summary)}</p><p class="record-meta">${H.escape(row.parties.join(" · "))}${row.signature_date ? ` · ${row.signature_date}` : ""}</p>${H.officialLink(row.official_text_url, "Open linked official record")}</article>`;
  }

  function renderAgreementsLayer() {
    const rows = inferAgreements();
    return layer("04", "agreements-layer", "Treaties and agreements", rows.length ? "partial" : "research-queue", rows.length ? `<p class="orientation-note">Formal treaties, purchasing agreements, concessions, negotiation records, and policy instruments remain explicitly typed.</p><div class="record-list">${rows.map(agreementCard).join("")}</div>` : empty("No treaty or agreement record is linked yet."));
  }

  function historicalName(country, year) {
    const period = country.names_by_period.find((item) => item.start <= year && item.end >= year);
    return period ? period.name : country.canonical_historical_name;
  }

  function miniMap(countries, year) {
    if (!countries.length) return empty("No country or territory record is linked yet.");
    const markers = countries.map((country) => {
      const x = ((country.marker.longitude + 180) / 360) * 960;
      const y = ((90 - country.marker.latitude) / 180) * 500;
      return `<g class="map-marker"><circle cx="${x}" cy="${y}" r="10"></circle><text x="${x}" y="${y-18}" text-anchor="middle">${H.escape(historicalName(country, year))}</text></g>`;
    }).join("");
    return `<div class="map-canvas history-map-mini"><svg viewBox="0 0 960 500" role="img" aria-label="Country-level linked geography"><rect width="960" height="500" class="ocean"></rect><g class="graticule"><path d="M0 125H960M0 250H960M0 375H960M240 0V500M480 0V500M720 0V500"></path></g><g class="land" aria-hidden="true"><path d="M72 160 C130 96 236 92 290 148 C325 184 305 244 258 276 C225 299 214 347 184 385 C156 362 148 306 112 279 C72 249 45 194 72 160Z"></path><path d="M404 128 C442 96 501 89 536 115 C565 91 628 95 684 132 C726 161 745 212 713 241 C681 270 632 250 611 280 C588 314 572 369 527 390 C488 353 493 297 456 267 C417 236 372 159 404 128Z"></path><path d="M682 128 C748 88 852 105 913 166 C947 199 932 255 894 275 C855 297 819 270 778 282 C735 295 692 248 664 202 C647 174 653 145 682 128Z"></path><path d="M740 345 C781 319 849 334 880 376 C855 412 783 420 727 390 C714 372 720 354 740 345Z"></path></g>${markers}</svg></div><table><thead><tr><th>Historical entity</th><th>Names by period</th><th>Precision</th></tr></thead><tbody>${countries.map((country) => `<tr><td><a href="${H.detailHref("countries", country.id)}">${H.escape(country.canonical_historical_name)}</a></td><td>${H.escape(country.names_by_period.map((item) => `${item.name} (${item.start}–${item.end})`).join("; "))}</td><td>${H.escape(country.marker.precision)}</td></tr>`).join("")}</tbody></table>`;
  }

  function renderGeographyLayer() {
    const countries = inferCountryIds().map((id) => data.indexes.countries.get(id)).filter(Boolean);
    const year = dataset === "countries" ? selectedYear : entity.date ? Number(entity.date.slice(0, 4)) : entity.start || entity.volume_year_start || 1950;
    return layer("05", "geography-layer", "Maps and geography", countries.length ? "partial" : "research-queue", `<p class="orientation-note">Markers are country-level centroids unless a record explicitly says otherwise. No mine, port, railway, or smelter coordinate is invented.</p>${miniMap(countries, year)}`);
  }

  function renderLawLayer() {
    const rows = inferLaws();
    const body = rows.length ? `<div class="record-list">${rows.map((row) => `<article class="law-card"><div>${H.badge("Law", "source")} ${H.completenessBadge(row.completeness)}</div><h3><a href="${H.detailHref("laws", row.id)}">${H.escape(row.official_title)}</a></h3><p class="record-meta">${H.escape(row.public_law_number)} · ${H.escape(row.statutes_at_large_citation)} · ${H.escape(row.enactment_date)}</p><p>${H.escape(row.summary)}</p>${H.officialLink(row.official_text_url, "Read official text")}</article>`).join("")}</div>` : empty("No statutory or congressional context is linked yet.");
    return layer("06", "law-layer", "Legislation and congressional context", rows.length ? "partial" : "research-queue", body);
  }

  function renderStockpileLayer() {
    const rows = inferStockpileCases();
    const body = rows.length ? `<div class="record-list">${rows.map((row) => `<article class="instrument-card"><div>${H.badge("Stockpile case", "concept")} ${H.completenessBadge(row.completeness)}</div><h3><a href="${H.detailHref("stockpile-cases", row.id)}">${H.escape(row.title)}</a></h3><p>${H.escape(row.summary)}</p><p class="caveat"><strong>Data gap:</strong> ${H.escape(row.data_gaps[0])}</p></article>`).join("")}</div>` : empty("No stockpile case is linked yet.");
    return layer("07", "stockpile-layer", "Strategic stockpile", rows.length ? "partial" : "research-queue", body);
  }

  function renderArchivesLayer() {
    const rows = inferNaraQueries();
    const proxy = String((window.HISTORY_RUNTIME_CONFIG || {}).naraProxyUrl || "").replace(/\/$/, "");
    const body = rows.length ? `<p class="orientation-note">These are structured discovery plans, not stored NARA records. ${proxy ? "A live proxy is configured for on-demand searches." : "Use the official Catalog links until a deployment proxy is configured."}</p><div class="record-list">${rows.map((row) => `<article class="nara-card"><div>${H.badge("NARA query plan", "discovery")}</div><h3>${H.escape(row.label)}</h3><p class="record-meta">RG ${H.escape(row.record_groups.join(", "))} · ${row.date_start}–${row.date_end}</p><p class="caveat">${H.escape(row.relevance_method)}</p><div class="record-actions"><a href="https://catalog.archives.gov/search?q=${encodeURIComponent(row.query)}" target="_blank" rel="noopener">Run in NARA Catalog ↗</a>${proxy ? `<button class="quiet-button live-nara" type="button" data-query="${H.escape(row.id)}">Run live query</button>` : ""}</div><div class="live-nara-result" id="result-${H.escape(row.id)}"></div></article>`).join("")}</div><p class="nara-attribution">This product uses the National Archives Catalog API but is not endorsed or certified by the National Archives and Records Administration.</p>` : empty("No structured NARA query is linked yet.");
    return layer("08", "archives-layer", "Archival records", rows.length ? "partial" : "research-queue", body);
  }

  function renderDecisionLayer() {
    const frus = inferFrusRows();
    const agreements = inferAgreements();
    const laws = inferLaws();
    const stages = [
      ["Problem identified", frus.length ? `${frus.length} linked FRUS record${frus.length === 1 ? "" : "s"}` : null],
      ["Economic or intelligence assessment", frus.some((row) => row.policy_themes.some((item) => /assessment|estimate|requirements|sources/i.test(item))) ? "Supported by linked FRUS metadata" : null],
      ["Interagency review", frus.some((row) => /interagency|NSC/i.test(`${row.title || ""} ${row.contextual_summary || ""} ${row.policy_themes.join(" ")}`)) ? "Supported by reviewed FRUS metadata" : null],
      ["Presidential decision", null],
      ["Diplomatic negotiation", agreements.some((row) => row.record_type === "negotiation-record") ? "Linked negotiation record" : null],
      ["Treaty, contract, or law", agreements.length || laws.length ? `${agreements.length + laws.length} linked instrument${agreements.length + laws.length === 1 ? "" : "s"}` : null],
      ["Implementation", null],
      ["Outcome", entity.outcome ? "Outcome metadata linked" : null]
    ];
    const body = `<p class="orientation-note">A stage is marked only when the pilot links evidence. Empty stages are not inferred.</p><ol class="decision-chain">${stages.map(([name, evidence], index) => `<li class="${evidence ? "has-evidence" : "needs-evidence"}"><span>${index + 1}</span><div><strong>${H.escape(name)}</strong><small>${H.escape(evidence || "Evidence not yet linked")}</small></div></li>`).join("")}</ol>`;
    return layer("09", "decisions-layer", "Presidential and NSC decision chain", stages.some((item) => item[1]) ? "partial" : "research-queue", body);
  }

  function renderOutcomeLayer() {
    const outcome = entity.outcome || {};
    const body = `<p class="orientation-note">Outcomes require explicit evidence; a plausible sequence is not treated as a documented result.</p><div class="outcome-grid"><div><strong>Immediate outcome</strong><p>${H.escape(outcome.immediate || "Not yet documented in the pilot.")}</p></div><div><strong>Medium-term consequence</strong><p>${H.escape(outcome.medium_term || "Not yet documented in the pilot.")}</p></div><div><strong>Long-term historical significance</strong><p>${H.escape(outcome.long_term || "Not yet documented in the pilot.")}</p></div></div>`;
    return layer("10", "outcome-layer", "What happened next", entity.outcome ? "partial" : "research-queue", body);
  }

  function renderProvenanceLayer() {
    const sources = sourceRows();
    const body = `<p class="orientation-note">The official publication or archival record controls. Project summaries and cross-links are orientation aids.</p><div class="record-list">${sources.map(H.sourceRow).join("")}</div>`;
    return layer("11", "provenance-layer", "Provenance and citations", sources.length ? "verified-pilot" : "research-queue", body);
  }

  function renderModernLayer() {
    const row = data["modern-context"][0];
    const body = `<div class="modern-layer"><span class="boundary-label">Outside the 1861–1992 dataset</span><h3>${H.escape(row.title)}</h3><p>${H.escape(row.summary)}</p>${H.officialLink(row.source_url, row.source_label)}<p class="boundary-note">${H.escape(row.boundary_note)}</p></div>`;
    return layer("12", "modern-layer", "Modern Context", "partial", body);
  }

  function renderAside() {
    const counts = [
      ["FRUS records", inferFrusRows().length], ["Statistics", inferStatistics().length],
      ["Agreements", inferAgreements().length], ["Laws", inferLaws().length],
      ["Countries", inferCountryIds().length], ["NARA plans", inferNaraQueries().length]
    ];
    const totalPossible = counts.length;
    const covered = counts.filter((item) => item[1] > 0).length;
    const gaps = [...new Set([...(entity.data_gaps || []), ...(countryBrief?.data_gaps || [])])];
    const yearHeading = dataset === "countries" ? `<p class="aside-year"><span>Selected year</span><strong>${selectedYear}</strong><small>${H.escape(historicalName(entity, selectedYear))}</small></p>` : "";
    $("stackAside").innerHTML = `<section class="aside-panel">${yearHeading}<p class="eyebrow">History Stack coverage</p><h2>${covered} of ${totalPossible} evidence layers linked</h2><div class="completeness-bar" aria-label="${covered} of ${totalPossible} evidence layers linked"><span style="width:${(covered / totalPossible) * 100}%"></span></div><ul>${counts.map(([label, count]) => `<li><strong>${count}</strong> ${H.escape(label)}</li>`).join("")}</ul></section><section class="aside-panel"><p class="eyebrow">Data quality</p><h2>Known gaps</h2>${gaps.length ? `<ul>${gaps.map((gap) => `<li>${H.escape(gap)}</li>`).join("")}</ul>` : '<p class="empty-note">No entity-specific gap note; layer-level gaps still apply.</p>'}</section><section class="aside-panel"><p class="eyebrow">Cite responsibly</p><p>Use this page to locate evidence. Cite the linked FRUS document, statute, official table, or archival record rather than this interface when possible.</p></section>`;
  }

  async function runLiveNara(button) {
    const plan = data.indexes["nara-queries"].get(button.dataset.query);
    const target = $(`result-${plan.id}`);
    const proxy = String((window.HISTORY_RUNTIME_CONFIG || {}).naraProxyUrl || "").replace(/\/$/, "");
    button.disabled = true;
    target.innerHTML = '<p class="loading-note">Requesting live descriptions…</p>';
    try {
      const params = new URLSearchParams({ q: plan.query, limit: "10", photos_only: "0", record_group: plan.record_groups[0] || "", date_start: String(plan.date_start), date_end: String(plan.date_end) });
      const response = await fetch(`${proxy}/nara/search?${params}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      target.innerHTML = (payload.hits || []).slice(0, 5).map((hit) => `<p><a href="${H.escape(hit.catalogUrl || `https://catalog.archives.gov/id/${hit.naid}`)}" target="_blank" rel="noopener">${H.escape(H.text(hit.title))}</a> ${H.badge("Unreviewed live result", "queue")}</p>`).join("") || '<p class="empty-note">No descriptions returned.</p>';
    } catch (error) {
      target.innerHTML = `<p class="caveat">Live query unavailable: ${H.escape(error.message)}</p>`;
    } finally {
      button.disabled = false;
    }
  }

  function bindLayerInteractions() {
    const rows = inferStatistics();
    const metric = $("detailMetric");
    if (metric) metric.addEventListener("change", () => { $("detailChart").innerHTML = chartSvg(rows, metric.value); });
    document.querySelectorAll(".live-nara").forEach((button) => button.addEventListener("click", () => runLiveNara(button)));
    const range = $("countryYearRange");
    const number = $("countryYearNumber");
    if (range) {
      range.addEventListener("input", () => {
        $("countryYearLabel").textContent = range.value;
        if (number) number.value = range.value;
      });
      range.addEventListener("change", () => setCountryYear(range.value));
    }
    if (number) {
      number.addEventListener("input", () => {
        const value = Number.parseInt(number.value, 10);
        if (value >= 1861 && value <= 1992) setCountryYear(value);
      });
      number.addEventListener("change", () => setCountryYear(number.value));
    }
    $("previousCountryYear")?.addEventListener("click", () => setCountryYear(selectedYear - 1));
    $("nextCountryYear")?.addEventListener("click", () => setCountryYear(selectedYear + 1));
  }

  function setCountryYear(value) {
    const year = Math.max(1861, Math.min(1992, Number.parseInt(value, 10) || selectedYear));
    if (year === selectedYear) return;
    selectedYear = year;
    const url = new URL(location.href);
    url.searchParams.set("year", String(selectedYear));
    history.replaceState(null, "", url);
    render();
  }

  function openHashLayer() {
    if (!location.hash) return;
    const target = document.querySelector(location.hash);
    const details = target?.matches("details") ? target : target?.querySelector("details");
    if (details) details.open = true;
  }

  function render() {
    const displayTitle = dataset === "countries" ? historicalName(entity, selectedYear) : H.displayName(entity, dataset);
    document.title = `${displayTitle}${dataset === "countries" ? `, ${selectedYear}` : ""} | History Stack`;
    $("breadcrumbType").textContent = entityType.replaceAll("-", " ");
    $("detailEyebrow").textContent = `${entityType.replaceAll("-", " ")} History Stack · 1861–1992${dataset === "countries" ? ` · Selected year ${selectedYear}` : ""}`;
    $("detailTitle").textContent = displayTitle;
    $("detailSummary").textContent = summary();
    $("detailBadges").innerHTML = `${H.completenessBadge(entity.completeness || entity.metadata_status)} ${sourceRows().slice(0, 4).map(H.sourceBadge).join("")}`;
    $("countryBriefNav").hidden = dataset !== "countries";
    $("stackMain").innerHTML = [renderFrusLayer(), dataset === "countries" ? renderCountryBriefLayer() : "", renderTimelineLayer(), renderStatisticsLayer(), renderAgreementsLayer(), renderGeographyLayer(), renderLawLayer(), renderStockpileLayer(), renderArchivesLayer(), renderDecisionLayer(), renderOutcomeLayer(), renderProvenanceLayer(), renderModernLayer()].join("");
    renderAside();
    bindLayerInteractions();
    openHashLayer();
  }

  async function init() {
    H.initTheme($("themeToggle"));
    H.initNavigation($("navToggle"), $("primaryNav"));
    const params = new URLSearchParams(location.search);
    entityType = params.get("type") || "mineral";
    dataset = TYPE_MAP[entityType];
    const id = params.get("id");
    try {
      data = await H.loadAll();
      entity = dataset && id ? data.indexes[dataset].get(id) : null;
      if (!entity) throw new Error("The requested History Stack record does not exist in this pilot.");
      countryBrief = dataset === "countries" ? data.indexes["country-briefs"].get(entity.id) : null;
      const requestedYear = Number.parseInt(params.get("year"), 10);
      selectedYear = dataset === "countries"
        ? Math.max(1861, Math.min(1992, Number.isFinite(requestedYear) ? requestedYear : (countryBrief?.default_year || 1950)))
        : null;
      window.addEventListener("hashchange", openHashLayer);
      render();
    } catch (error) {
      $("detailTitle").textContent = "History Stack unavailable";
      $("detailSummary").textContent = error.message;
      $("stackMain").innerHTML = `<section class="stack-layer"><div class="layer-body"><p>Return to the historical portal and choose a listed entity.</p><a class="button-link" href="records-stage.html">Return to portal</a></div></section>`;
    }
  }

  init();
})();
