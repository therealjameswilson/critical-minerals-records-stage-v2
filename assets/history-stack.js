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
    const mineralIds = new Set(inferMineralIds());
    let rows = data.statistics.filter((row) => mineralIds.has(row.mineral_id));
    if (dataset === "countries") rows = rows.filter((row) => row.country_id === entity.id);
    const start = entity.start || entity.volume_year_start || entity.historical_scope?.start;
    const end = entity.end || entity.volume_year_end || entity.historical_scope?.end;
    if (dataset !== "minerals" && start && end) rows = rows.filter((row) => row.year >= start && row.year <= end);
    return rows;
  }

  function sourceRows() {
    const ids = new Set(relatedIds("source_ids"));
    inferFrusRows().forEach((row) => row.source_ids.forEach((id) => ids.add(id)));
    if (inferStatistics().length) ids.add("usgs-ds140");
    if (inferNaraQueries().length) ids.add("nara-catalog-api");
    return [...ids].map((id) => data.indexes.sources.get(id)).filter(Boolean);
  }

  function summary() {
    if (entity.summary) return entity.summary;
    if (entity.contextual_summary) return entity.contextual_summary;
    if (entity.strategic_uses?.length) return entity.strategic_uses[0].use;
    if (entity.data_gaps?.length) return `Pilot coverage is incomplete. ${entity.data_gaps[0]}`;
    return "This record connects the FRUS narrative to available official historical context.";
  }

  function layer(number, id, title, status, body) {
    return `<section class="stack-layer" id="${id}" aria-labelledby="${id}-title"><header class="layer-heading"><span class="layer-number">${number}</span><h2 id="${id}-title">${H.escape(title)}</h2>${H.completenessBadge(status || "partial")}</header><div class="layer-body">${body}</div></section>`;
  }

  function empty(message) {
    return `<div class="research-gap"><p class="empty-note">${H.escape(message)}</p>${H.badge("Research queue", "queue")}</div>`;
  }

  function renderFrusLayer() {
    const rows = inferFrusRows().sort((a, b) => (a.date || `${a.volume_year_start}`).localeCompare(b.date || `${b.volume_year_start}`));
    let orientation = "";
    if (dataset === "minerals" && rows.length) {
      const first = rows[0];
      orientation = `<p class="orientation-note"><strong>First appearance in this pilot:</strong> ${H.escape(first.title || first.volume_context)} (${first.date || `${first.volume_year_start}–${first.volume_year_end}`}). ${first.metadata_status === "subject-index-lead" ? "This is a discovery-index appearance, not yet a document-level finding." : "This record has document-level pilot metadata."}</p>`;
    }
    return layer("01", "frus-layer", "FRUS narrative", rows.some((row) => row.metadata_status === "verified-document") ? "verified-pilot" : "research-queue", orientation + (rows.length ? `<div class="record-list">${rows.map((row) => H.frusCard(row, false)).join("")}</div>` : empty("No FRUS document is linked to this pilot entity yet.")));
  }

  function renderTimelineLayer() {
    const episodes = inferEpisodes();
    const administrations = inferAdministrations();
    const items = [
      ...episodes.map((row) => ({ date: row.start, end: row.end, title: row.title, summary: row.summary, href: H.detailHref("episodes", row.id), label: "Episode" })),
      ...administrations.map((row) => ({ date: row.start, end: row.end, title: `${row.president} administration`, summary: row.summary, href: H.detailHref("administrations", row.id), label: "Administration" }))
    ].sort((a, b) => a.date - b.date);
    const body = items.length ? `<ol class="detail-timeline">${items.map((item) => `<li><span>${item.date}–${item.end}</span><div>${H.badge(item.label, "concept")}<h3><a href="${item.href}">${H.escape(item.title)}</a></h3><p>${H.escape(item.summary)}</p></div></li>`).join("")}</ol>` : empty("No period or administration record is linked yet.");
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
    if (!rows.length) return layer("03", "statistics-layer", "Official statistics", "research-queue", empty("No compatible, unit-defined official statistical series is linked to this entity yet."));
    const metrics = [...new Set(rows.map((row) => row.metric))].sort();
    const metric = metrics.find((item) => rows.filter((row) => row.metric === item).length >= 2) || metrics[0];
    const table = `<div class="data-table-wrap"><table><caption class="visually-hidden">Official statistics with units and provenance</caption><thead><tr><th>Year</th><th>Metric</th><th>Value</th><th>Unit</th><th>Agency</th><th>Publication location</th></tr></thead><tbody>${rows.slice(0, 200).map((row) => `<tr><td>${row.year}</td><td>${H.escape(row.metric)}</td><td>${H.formatNumber(row.value)}</td><td>${H.escape(row.unit)}</td><td>${H.escape(row.agency)}</td><td><a href="${H.escape(row.source_url)}" target="_blank" rel="noopener">${H.escape(row.table_or_page)}</a></td></tr>`).join("")}</tbody></table></div>`;
    const body = `<div class="stat-toolbar"><div class="control"><label for="detailMetric">Chart metric</label><select id="detailMetric">${metrics.map((item) => `<option value="${H.escape(item)}"${item === metric ? " selected" : ""}>${H.escape(item)}</option>`).join("")}</select></div><p>${rows.length} observations. No project interpolation; original USGS-standardized units retained.</p></div><div id="detailChart">${chartSvg(rows, metric)}</div>${table}`;
    return layer("03", "statistics-layer", "Official statistics", "verified-pilot", body);
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
    const year = entity.date ? Number(entity.date.slice(0, 4)) : entity.start || entity.volume_year_start || 1950;
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
    const gaps = entity.data_gaps || [];
    $("stackAside").innerHTML = `<section class="aside-panel"><p class="eyebrow">History Stack coverage</p><h2>${covered} of ${totalPossible} evidence layers linked</h2><div class="completeness-bar" aria-label="${covered} of ${totalPossible} evidence layers linked"><span style="width:${(covered / totalPossible) * 100}%"></span></div><ul>${counts.map(([label, count]) => `<li><strong>${count}</strong> ${H.escape(label)}</li>`).join("")}</ul></section><section class="aside-panel"><p class="eyebrow">Data quality</p><h2>Known gaps</h2>${gaps.length ? `<ul>${gaps.map((gap) => `<li>${H.escape(gap)}</li>`).join("")}</ul>` : '<p class="empty-note">No entity-specific gap note; layer-level gaps still apply.</p>'}</section><section class="aside-panel"><p class="eyebrow">Cite responsibly</p><p>Use this page to locate evidence. Cite the linked FRUS document, statute, official table, or archival record rather than this interface when possible.</p></section>`;
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
  }

  function render() {
    document.title = `${H.displayName(entity, dataset)} | History Stack`;
    $("breadcrumbType").textContent = entityType.replaceAll("-", " ");
    $("detailEyebrow").textContent = `${entityType.replaceAll("-", " ")} History Stack · 1861–1992`;
    $("detailTitle").textContent = H.displayName(entity, dataset);
    $("detailSummary").textContent = summary();
    $("detailBadges").innerHTML = `${H.completenessBadge(entity.completeness || entity.metadata_status)} ${sourceRows().slice(0, 4).map(H.sourceBadge).join("")}`;
    $("stackMain").innerHTML = [renderFrusLayer(), renderTimelineLayer(), renderStatisticsLayer(), renderAgreementsLayer(), renderGeographyLayer(), renderLawLayer(), renderStockpileLayer(), renderArchivesLayer(), renderDecisionLayer(), renderOutcomeLayer(), renderProvenanceLayer(), renderModernLayer()].join("");
    renderAside();
    bindLayerInteractions();
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
      render();
    } catch (error) {
      $("detailTitle").textContent = "History Stack unavailable";
      $("detailSummary").textContent = error.message;
      $("stackMain").innerHTML = `<section class="stack-layer"><div class="layer-body"><p>Return to the historical portal and choose a listed entity.</p><a class="button-link" href="records-stage.html">Return to portal</a></div></section>`;
    }
  }

  init();
})();
