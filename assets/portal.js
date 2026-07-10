(function () {
  "use strict";

  const H = window.HistoryData;
  const $ = (id) => document.getElementById(id);
  const state = {
    data: null,
    periodId: null,
    mapMineral: "all",
    mapYear: 1942,
    mapCountry: null,
    instrumentType: "all",
    instrumentMineral: "all",
    frusQuery: "",
    frusSubject: "all",
    frusFrom: 1861,
    frusTo: 1992,
    frusLimit: 24
  };

  function option(value, label, selected) {
    return `<option value="${H.escape(value)}"${String(value) === String(selected) ? " selected" : ""}>${H.escape(label)}</option>`;
  }

  function getUrlState() {
    const params = new URLSearchParams(window.location.search);
    state.mapMineral = params.get("mineral") || "all";
    state.mapYear = Math.max(1861, Math.min(1992, Number(params.get("year")) || 1942));
    state.frusQuery = params.get("frusq") || "";
    state.frusSubject = params.get("frussubject") || "all";
    state.frusFrom = Math.max(1861, Math.min(1992, Number(params.get("from")) || 1861));
    state.frusTo = Math.max(state.frusFrom, Math.min(1992, Number(params.get("to")) || 1992));
    return params.get("q") || "";
  }

  function syncUrl(extra) {
    const params = new URLSearchParams(window.location.search);
    const values = {
      mineral: state.mapMineral === "all" ? "" : state.mapMineral,
      year: state.mapYear === 1942 ? "" : state.mapYear,
      frusq: state.frusQuery,
      frussubject: state.frusSubject === "all" ? "" : state.frusSubject,
      from: state.frusFrom === 1861 ? "" : state.frusFrom,
      to: state.frusTo === 1992 ? "" : state.frusTo,
      ...(extra || {})
    };
    Object.entries(values).forEach(([key, value]) => value === "" || value == null ? params.delete(key) : params.set(key, value));
    const query = params.toString();
    history.replaceState(null, "", `${location.pathname}${query ? `?${query}` : ""}${location.hash}`);
  }

  function renderMetrics() {
    const data = state.data;
    const reviewed = data["frus-documents"].filter((row) => row.metadata_status === "verified-document").length;
    const metrics = [
      ["Historical boundary", "1861–1992"],
      ["FRUS subject records", new Intl.NumberFormat("en-US").format(window.FRUS_SUBJECTS_INDEX.meta.documents)],
      ["Reviewed FRUS pilot", `${reviewed} of ${data["frus-documents"].length}`],
      ["USGS observations", new Intl.NumberFormat("en-US").format(data.statistics.length)],
      ["Mineral profiles", data.minerals.length],
      ["NARA query plans", data["nara-queries"].length]
    ];
    $("metricsStrip").innerHTML = metrics.map(([label, value]) => `<div><strong>${H.escape(value)}</strong><span>${H.escape(label)}</span></div>`).join("");
  }

  function renderMinerals() {
    const data = state.data;
    $("mineralGrid").innerHTML = data.minerals.map((row) => {
      const stats = data.statistics.filter((item) => item.mineral_id === row.id);
      return `<article class="entity-card mineral-card">
        <div class="entity-top"><span class="chemical-symbol">${H.escape(row.chemical_symbol || "—")}</span>${H.completenessBadge(row.completeness)}</div>
        <h3><a href="${H.detailHref("minerals", row.id)}">${H.escape(row.canonical_name)}</a></h3>
        <p>${H.escape(row.strategic_uses[0] ? row.strategic_uses[0].use : "Historical use narrative is a research queue.")}</p>
        <dl class="mini-stats"><div><dt>FRUS links</dt><dd>${row.frus_document_ids.length}</dd></div><div><dt>Statistics</dt><dd>${stats.length}</dd></div><div><dt>Period</dt><dd>${H.escape(H.yearRange(row))}</dd></div></dl>
        <a class="card-link" href="${H.detailHref("minerals", row.id)}">Open History Stack <span aria-hidden="true">→</span></a>
      </article>`;
    }).join("");
  }

  function renderCountries() {
    const data = state.data;
    $("countryGrid").innerHTML = data.countries.map((row) => {
      const modern = row.present_day_name && row.present_day_name !== row.canonical_historical_name ? ` · now ${row.present_day_name}` : "";
      const minerals = row.mineral_ids.map((id) => data.indexes.minerals.get(id)).filter(Boolean);
      return `<article class="country-row">
        <div><span class="country-index">${String(row.frus_document_ids.length).padStart(2, "0")}</span><span class="visually-hidden"> linked FRUS records</span></div>
        <div class="country-main"><h3><a href="${H.detailHref("countries", row.id)}">${H.escape(row.canonical_historical_name)}</a></h3><p>${H.escape(H.yearRange(row.names_by_period[0] || {}))}${H.escape(modern)}</p></div>
        <div class="tag-row">${minerals.map((item) => H.badge(item.canonical_name, "neutral")).join("") || H.badge("Context entity", "neutral")}</div>
        <div>${H.completenessBadge(row.completeness)}</div>
        <a class="row-arrow" href="${H.detailHref("countries", row.id)}" aria-label="Open ${H.escape(row.canonical_historical_name)} History Stack">→</a>
      </article>`;
    }).join("");
  }

  function renderPeriods() {
    const data = state.data;
    if (!state.periodId) state.periodId = data.episodes.find((row) => row.id === "world-war-ii-procurement").id;
    $("periodRail").innerHTML = data.episodes.map((row) => `<button type="button" class="period-button${row.id === state.periodId ? " is-active" : ""}" data-period="${H.escape(row.id)}" aria-pressed="${row.id === state.periodId}"><span>${H.escape(H.yearRange(row))}</span><strong>${H.escape(row.title)}</strong></button>`).join("");
    $("periodRail").querySelectorAll("[data-period]").forEach((button) => button.addEventListener("click", () => {
      state.periodId = button.dataset.period;
      renderPeriods();
    }));
    const row = data.indexes.episodes.get(state.periodId);
    const frus = row.frus_document_ids.map((id) => data.indexes["frus-documents"].get(id)).filter(Boolean);
    $("periodDetail").innerHTML = `<div class="period-copy"><p class="eyebrow">${H.escape(H.yearRange(row))}</p><h3>${H.escape(row.title)}</h3><p>${H.escape(row.summary)}</p><div class="tag-row">${row.mineral_ids.map((id) => H.badge(data.indexes.minerals.get(id)?.canonical_name || id, "neutral")).join("")}</div><a class="button-link" href="${H.detailHref("episodes", row.id)}">Open period History Stack</a></div><div class="period-evidence"><strong>${frus.length}</strong><span>linked pilot FRUS records</span><div>${frus.slice(0, 3).map((item) => `<a href="${H.detailHref("frus-documents", item.id)}">${H.escape(item.title || item.volume_context)}</a>`).join("") || '<p class="empty-note">No reviewed FRUS records yet.</p>'}</div></div>`;

    $("administrationStrip").innerHTML = data.administrations.map((row) => `<a href="${H.detailHref("administrations", row.id)}"><span>${row.start}–${row.end}</span><strong>${H.escape(row.president)}</strong>${H.completenessBadge(row.completeness)}</a>`).join("");
  }

  function renderFeature() {
    const data = state.data;
    const frus = data["frus-documents"].find((row) => row.volume === "frus1942v05" && row.document_number === "493");
    $("featuredFrus").innerHTML = frus ? H.frusCard(frus, true) : "";
    const preferred = ["U.S. primary production", "U.S. imports", "U.S. apparent consumption", "Unit value", "World production"];
    const stats = data.statistics.filter((row) => row.mineral_id === "tin" && row.year === 1942 && preferred.includes(row.metric));
    $("policyNumbers").innerHTML = preferred.map((metric) => {
      const row = stats.find((item) => item.metric === metric);
      if (!row) return `<div><strong>Not available</strong><span>${H.escape(metric)}</span></div>`;
      return `<div><strong>${H.formatNumber(row.value)}</strong><span>${H.escape(metric)}</span><small>${H.escape(row.unit)}</small><a href="${H.escape(row.source_url)}" target="_blank" rel="noopener" aria-label="Source for ${H.escape(metric)}">USGS source ↗</a></div>`;
    }).join("");
  }

  function historicalName(country, year) {
    const period = country.names_by_period.find((item) => item.start <= year && item.end >= year);
    return period ? period.name : country.canonical_historical_name;
  }

  function countryActive(country) {
    const exists = country.names_by_period.some((item) => item.start <= state.mapYear && item.end >= state.mapYear);
    const linkedFrus = country.frus_document_ids.some((id) => {
      const row = state.data.indexes["frus-documents"].get(id);
      return row && row.volume_year_start <= state.mapYear && row.volume_year_end >= state.mapYear;
    });
    const linkedEpisode = country.episode_ids.some((id) => {
      const row = state.data.indexes.episodes.get(id);
      return row && row.start <= state.mapYear && row.end >= state.mapYear;
    });
    return exists && (linkedFrus || linkedEpisode) && (state.mapMineral === "all" || country.mineral_ids.includes(state.mapMineral));
  }

  function renderMapControls() {
    const data = state.data;
    $("mapMineral").innerHTML = option("all", "All pilot minerals", state.mapMineral) + data.minerals.map((row) => option(row.id, row.canonical_name, state.mapMineral)).join("");
    $("mapYear").value = state.mapYear;
    $("mapYearValue").textContent = state.mapYear;
    $("mapMineral").addEventListener("change", (event) => {
      state.mapMineral = event.target.value;
      state.mapCountry = null;
      renderMap();
      syncUrl();
    });
    $("mapYear").addEventListener("input", (event) => {
      state.mapYear = Number(event.target.value);
      $("mapYearValue").textContent = state.mapYear;
      state.mapCountry = null;
      renderMap();
      syncUrl();
    });
  }

  function renderMap() {
    const data = state.data;
    const countries = data.countries.filter(countryActive);
    const marker = (country) => {
      const x = ((country.marker.longitude + 180) / 360) * 960;
      const y = ((90 - country.marker.latitude) / 180) * 500;
      const count = country.frus_document_ids.length;
      const radius = 7 + Math.min(7, count);
      return `<g class="map-marker${country.id === state.mapCountry ? " is-selected" : ""}" tabindex="0" role="button" data-country="${H.escape(country.id)}" aria-label="${H.escape(historicalName(country, state.mapYear))}, ${count} linked FRUS records"><circle cx="${x}" cy="${y}" r="${radius}"></circle><text x="${x}" y="${y - radius - 7}" text-anchor="middle">${H.escape(historicalName(country, state.mapYear))}</text></g>`;
    };
    $("mapCanvas").innerHTML = `<svg viewBox="0 0 960 500" role="img" aria-label="World evidence-coverage map for ${state.mapYear}">
      <rect width="960" height="500" class="ocean"></rect>
      <g class="graticule"><path d="M0 125H960M0 250H960M0 375H960M240 0V500M480 0V500M720 0V500"></path></g>
      <g class="land" aria-hidden="true">
        <path d="M72 160 C130 96 236 92 290 148 C325 184 305 244 258 276 C225 299 214 347 184 385 C156 362 148 306 112 279 C72 249 45 194 72 160Z"></path>
        <path d="M404 128 C442 96 501 89 536 115 C565 91 628 95 684 132 C726 161 745 212 713 241 C681 270 632 250 611 280 C588 314 572 369 527 390 C488 353 493 297 456 267 C417 236 372 159 404 128Z"></path>
        <path d="M682 128 C748 88 852 105 913 166 C947 199 932 255 894 275 C855 297 819 270 778 282 C735 295 692 248 664 202 C647 174 653 145 682 128Z"></path>
        <path d="M740 345 C781 319 849 334 880 376 C855 412 783 420 727 390 C714 372 720 354 740 345Z"></path>
        <path d="M330 62 C350 40 382 45 393 70 C378 94 348 98 326 82Z"></path>
      </g>
      <g>${countries.map(marker).join("")}</g>
    </svg>`;
    $("mapCanvas").querySelectorAll(".map-marker").forEach((node) => {
      const activate = () => {
        state.mapCountry = node.dataset.country;
        renderMap();
      };
      node.addEventListener("click", activate);
      node.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate();
        }
      });
    });
    const selected = data.indexes.countries.get(state.mapCountry) || countries[0];
    if (selected) {
      const minerals = selected.mineral_ids.map((id) => data.indexes.minerals.get(id)?.canonical_name || id);
      $("mapInspector").innerHTML = `<p class="eyebrow">Selected geography</p><h3>${H.escape(historicalName(selected, state.mapYear))}</h3><p>${selected.present_day_name && historicalName(selected, state.mapYear) !== selected.present_day_name ? `Present-day name: ${H.escape(selected.present_day_name)}.` : "Historical name unchanged in this pilot."}</p><dl><div><dt>Linked minerals</dt><dd>${H.escape(minerals.join(", ") || "Context entity")}</dd></div><div><dt>FRUS pilot records</dt><dd>${selected.frus_document_ids.length}</dd></div><div><dt>Marker precision</dt><dd>${H.escape(selected.marker.precision)} level</dd></div></dl><p class="caveat">${H.escape(selected.data_gaps[0] || "Coverage remains incomplete.")}</p><a class="button-link" href="${H.detailHref("countries", selected.id)}">Open country History Stack</a>`;
    } else {
      $("mapInspector").innerHTML = `<p class="empty-note">No pilot country matches this mineral and year.</p>`;
    }
    $("mapTableBody").innerHTML = countries.map((country) => `<tr><td><a href="${H.detailHref("countries", country.id)}">${H.escape(country.canonical_historical_name)}</a></td><td>${H.escape(historicalName(country, state.mapYear))}</td><td>${H.escape(country.mineral_ids.map((id) => data.indexes.minerals.get(id)?.canonical_name || id).join(", ") || "Context only")}</td><td>${country.frus_document_ids.length}</td><td>${H.escape(country.marker.precision)}</td></tr>`).join("");
  }

  function renderInstruments() {
    const data = state.data;
    const types = [...new Set(data.agreements.map((row) => row.record_type))].sort();
    $("instrumentType").innerHTML = option("all", "All record types", state.instrumentType) + types.map((item) => option(item, item.replaceAll("-", " "), state.instrumentType)).join("");
    $("instrumentMineral").innerHTML = option("all", "All minerals", state.instrumentMineral) + data.minerals.map((row) => option(row.id, row.canonical_name, state.instrumentMineral)).join("");
    const filtered = data.agreements.filter((row) => (state.instrumentType === "all" || row.record_type === state.instrumentType) && (state.instrumentMineral === "all" || row.mineral_ids.includes(state.instrumentMineral)));
    $("instrumentCount").textContent = `${filtered.length} records`;
    $("agreementList").innerHTML = filtered.map((row) => `<article class="instrument-card"><div>${H.badge(row.record_type.replaceAll("-", " "), "concept")} ${H.completenessBadge(row.completeness)}</div><h4><a href="${H.detailHref("agreements", row.id)}">${H.escape(row.official_title)}</a></h4><p>${H.escape(row.summary)}</p><p class="record-meta">Parties: ${H.escape(row.parties.join(" · "))}${row.signature_date ? ` · ${H.escape(row.signature_date)}` : ""}</p>${H.officialLink(row.official_text_url, "Open linked official record")}</article>`).join("") || '<p class="empty-note">No instruments match these filters.</p>';
    $("lawList").innerHTML = data.laws.map((row) => `<article class="law-card"><div>${H.badge("Law", "source")} ${H.completenessBadge(row.completeness)}</div><h4><a href="${H.detailHref("laws", row.id)}">${H.escape(row.official_title)}</a></h4><p class="record-meta">${H.escape(row.public_law_number)} · ${H.escape(row.statutes_at_large_citation)} · ${H.escape(row.enactment_date)}</p><p>${H.escape(row.summary)}</p>${H.officialLink(row.official_text_url, "Read official text")}</article>`).join("");
  }

  function bindInstrumentControls() {
    ["instrumentType", "instrumentMineral"].forEach((id) => $(id).addEventListener("change", (event) => {
      if (id === "instrumentType") state.instrumentType = event.target.value;
      else state.instrumentMineral = event.target.value;
      renderInstruments();
    }));
  }

  function catalogSearchUrl(plan) {
    return `https://catalog.archives.gov/search?q=${encodeURIComponent(plan.query)}`;
  }

  function naraRelevance(hit, plan) {
    const haystack = `${H.text(hit.title)} ${H.text(hit.description)}`.toLowerCase();
    const terms = plan.query.toLowerCase().split(/\s+/).filter((term) => term.length > 3);
    const matches = terms.filter((term) => haystack.includes(term)).length;
    if (terms.length && matches === terms.length) return ["direct match", "verified"];
    if (matches >= Math.max(1, Math.ceil(terms.length / 2))) return ["probable match", "partial"];
    if (plan.record_groups.includes(String(hit.recordGroupNumber || ""))) return ["contextual match", "concept"];
    return ["broad archival lead", "queue"];
  }

  function renderNaraSetup() {
    const data = state.data;
    $("naraQuery").innerHTML = data["nara-queries"].map((row) => option(row.id, `${row.label} · RG ${row.record_groups.join(", ")}`, "")).join("");
    const proxy = String((window.HISTORY_RUNTIME_CONFIG || {}).naraProxyUrl || "").replace(/\/$/, "");
    $("naraStatus").innerHTML = proxy ? `<span class="status-dot is-ready"></span><strong>Live NARA proxy configured.</strong> Searches are requested on demand and are not stored by this site.` : `<span class="status-dot"></span><strong>Live NARA proxy not configured.</strong> Query plans still open in the official Catalog; add a proxy URL to enable in-page results.`;
    $("runNaraQuery").addEventListener("click", runNaraQuery);
  }

  async function runNaraQuery() {
    const data = state.data;
    const plan = data.indexes["nara-queries"].get($("naraQuery").value);
    const proxy = String((window.HISTORY_RUNTIME_CONFIG || {}).naraProxyUrl || "").replace(/\/$/, "");
    const button = $("runNaraQuery");
    if (!proxy) {
      $("naraResults").innerHTML = `<article class="nara-card"><div>${H.badge("Structured query plan", "discovery")}</div><h3>${H.escape(plan.label)}</h3><p>Record group ${H.escape(plan.record_groups.join(", "))} · ${plan.date_start}–${plan.date_end}</p><p class="caveat">The Catalog result set is an archival lead. Review descriptions and records before asserting relevance.</p><a href="${catalogSearchUrl(plan)}" target="_blank" rel="noopener">Run in the official NARA Catalog ↗</a></article>`;
      return;
    }
    button.disabled = true;
    button.textContent = "Searching…";
    $("naraResults").innerHTML = '<p class="loading-note">Requesting live archival descriptions from NARA…</p>';
    const params = new URLSearchParams({ q: plan.query, limit: "20", photos_only: "0", record_group: plan.record_groups[0] || "", date_start: String(plan.date_start), date_end: String(plan.date_end) });
    try {
      const response = await fetch(`${proxy}/nara/search?${params.toString()}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      const hits = Array.isArray(payload.hits) ? payload.hits : [];
      $("naraStatus").innerHTML = `<span class="status-dot is-ready"></span><strong>Live NARA response.</strong> ${H.escape(payload.returned || hits.length)} descriptions returned; retrieved ${H.escape(payload.retrievedAt || "just now")}.`;
      $("naraResults").innerHTML = hits.length ? hits.map((hit) => {
        const relevance = naraRelevance(hit, plan);
        const url = hit.catalogUrl || (hit.naid ? `https://catalog.archives.gov/id/${encodeURIComponent(hit.naid)}` : catalogSearchUrl(plan));
        return `<article class="nara-card"><div>${H.badge("NARA", "source")} ${H.badge(relevance[0], relevance[1])}</div><h3><a href="${H.escape(url)}" target="_blank" rel="noopener">${H.escape(H.text(hit.title))}</a></h3><p class="record-meta">NAID ${H.escape(hit.naid || "not returned")} · ${H.escape(H.text(hit.levelOfDescription))}${hit.recordGroupNumber ? ` · RG ${H.escape(hit.recordGroupNumber)}` : ""}</p>${hit.dateNote ? `<p>${H.escape(H.text(hit.dateNote))}</p>` : ""}${hit.description ? `<p>${H.escape(H.text(hit.description)).slice(0, 500)}</p>` : ""}<p class="caveat">Relevance label is a query-match aid, not a substantive archival judgment.</p></article>`;
      }).join("") : `<p class="empty-note">No descriptions returned. Broaden the query in the official Catalog.</p>`;
    } catch (error) {
      $("naraStatus").innerHTML = `<span class="status-dot is-error"></span><strong>NARA is unavailable.</strong> The static site remains usable and no prior API response is substituted.`;
      $("naraResults").innerHTML = `<article class="nara-card"><p>${H.escape(error.message)}</p><a href="${catalogSearchUrl(plan)}" target="_blank" rel="noopener">Continue in the official NARA Catalog ↗</a></article>`;
    } finally {
      button.disabled = false;
      button.textContent = "Search NARA";
    }
  }

  function renderStockpile() {
    const data = state.data;
    $("stockpileGrid").innerHTML = data["stockpile-cases"].map((row) => `<article><p class="eyebrow">${H.escape(H.yearRange(row))}</p><h3><a href="${H.detailHref("stockpile-cases", row.id)}">${H.escape(row.title)}</a></h3><p>${H.escape(row.summary)}</p><dl><div><dt>FRUS records</dt><dd>${row.frus_document_ids.length}</dd></div><div><dt>Laws</dt><dd>${row.law_ids.length}</dd></div><div><dt>Holdings verified</dt><dd>${row.holdings.length}</dd></div></dl><p class="stockpile-gap"><strong>Data gap:</strong> ${H.escape(row.data_gaps[0])}</p><a href="${H.detailHref("stockpile-cases", row.id)}">Open case study →</a></article>`).join("");
  }

  function subjectNames(mask) {
    return window.FRUS_SUBJECTS_INDEX.subjects.filter((subject) => mask & subject.bit).map((subject) => subject.name);
  }

  function renderFrusControls() {
    const index = window.FRUS_SUBJECTS_INDEX;
    $("frusSubject").innerHTML = option("all", "All indexed subjects", state.frusSubject) + index.subjects.map((row) => option(row.bit, `${row.name} (${new Intl.NumberFormat("en-US").format(row.references)})`, state.frusSubject)).join("");
    const years = Array.from({ length: 132 }, (_, index) => 1861 + index);
    $("frusFromYear").innerHTML = years.map((year) => option(year, year, state.frusFrom)).join("");
    $("frusToYear").innerHTML = years.map((year) => option(year, year, state.frusTo)).join("");
    $("frusQuery").value = state.frusQuery;
  }

  function curatedFrusMap() {
    return new Map(state.data["frus-documents"].map((row) => [`${row.volume}/${`d${row.document_number}`}`, row]));
  }

  function renderFrus() {
    const index = window.FRUS_SUBJECTS_INDEX;
    const tokens = state.frusQuery.toLowerCase().trim().split(/\s+/).filter(Boolean);
    const subjectBit = state.frusSubject === "all" ? null : Number(state.frusSubject);
    const curated = curatedFrusMap();
    const rows = index.records.filter((row) => {
      const [volume, document, start, end, mask, context] = row;
      if (start > state.frusTo || end < state.frusFrom) return false;
      if (subjectBit && !(mask & subjectBit)) return false;
      const verified = curated.get(`${volume}/${document}`);
      const haystack = `${volume} ${document} ${context} ${subjectNames(mask).join(" ")} ${verified?.title || ""} ${verified?.contextual_summary || ""}`.toLowerCase();
      return tokens.every((token) => haystack.includes(token));
    });
    $("frusResultsCount").textContent = `${new Intl.NumberFormat("en-US").format(rows.length)} indexed records`;
    $("frusCorpusNote").textContent = `${index.meta.volumes} volumes · ${index.meta.yearStart}–${index.meta.yearEnd} · subject index generated ${index.meta.generated}`;
    $("frusRecords").innerHTML = rows.slice(0, state.frusLimit).map((row) => {
      const [volume, document, start, end, mask, context] = row;
      const item = curated.get(`${volume}/${document}`);
      if (item) return H.frusCard(item, true);
      return `<article class="record-card frus-card is-compact"><div class="record-kicker">${H.badge("FRUS", "source")} ${H.completenessBadge("subject-index-lead")}</div><h3>${H.escape(context)}</h3><p class="record-meta">Volume span ${start}–${end} · ${H.escape(volume)}, ${H.escape(document)}</p><div class="tag-row">${subjectNames(mask).map((name) => H.badge(name, "neutral")).join("")}</div><p class="caveat">Volume or chapter navigation context only. Open the document to verify its title, date, and substantive relevance.</p>${H.officialLink(`${index.meta.documentBase}${volume}/${document}`, "Open in FRUS")}</article>`;
    }).join("") || '<p class="empty-note">No FRUS index records match these literal metadata filters.</p>';
    $("frusLoadMore").hidden = rows.length <= state.frusLimit;
  }

  function bindFrusControls() {
    let timer;
    $("frusQuery").addEventListener("input", (event) => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        state.frusQuery = event.target.value;
        state.frusLimit = 24;
        renderFrus();
        syncUrl();
      }, 150);
    });
    $("frusSubject").addEventListener("change", (event) => {
      state.frusSubject = event.target.value;
      state.frusLimit = 24;
      renderFrus();
      syncUrl();
    });
    $("frusFromYear").addEventListener("change", (event) => {
      state.frusFrom = Number(event.target.value);
      if (state.frusFrom > state.frusTo) state.frusTo = state.frusFrom;
      renderFrusControls();
      renderFrus();
      syncUrl();
    });
    $("frusToYear").addEventListener("change", (event) => {
      state.frusTo = Number(event.target.value);
      if (state.frusTo < state.frusFrom) state.frusFrom = state.frusTo;
      renderFrusControls();
      renderFrus();
      syncUrl();
    });
    $("frusClear").addEventListener("click", () => {
      state.frusQuery = "";
      state.frusSubject = "all";
      state.frusFrom = 1861;
      state.frusTo = 1992;
      state.frusLimit = 24;
      renderFrusControls();
      renderFrus();
      syncUrl();
    });
    $("frusLoadMore").addEventListener("click", () => {
      state.frusLimit += 24;
      renderFrus();
    });
  }

  function recordSearchText(row) {
    return JSON.stringify(row).toLowerCase();
  }

  function runGlobalSearch(query, shouldScroll) {
    const data = state.data;
    const normalized = query.trim().toLowerCase();
    const tokens = normalized.split(/\s+/).filter(Boolean);
    const section = $("searchResultsSection");
    if (!tokens.length) {
      section.classList.add("is-hidden");
      syncUrl({ q: "" });
      return;
    }
    const searchable = ["minerals", "countries", "episodes", "agreements", "laws", "administrations", "stockpile-cases", "frus-documents"];
    const results = searchable.flatMap((type) => data[type].filter((row) => tokens.every((token) => recordSearchText(row).includes(token))).map((row) => ({ type, row })));
    section.classList.remove("is-hidden");
    $("globalResultsSummary").textContent = `${results.length} pilot records match “${query}”. Search is literal metadata matching, not an AI answer.`;
    $("globalResults").innerHTML = results.slice(0, 36).map(({ type, row }) => `<article><div>${H.badge(type.replaceAll("-", " "), "neutral")} ${H.completenessBadge(row.completeness || row.metadata_status)}</div><h3><a href="${H.detailHref(type, row.id)}">${H.escape(H.displayName(row, type))}</a></h3><p>${H.escape(row.summary || row.contextual_summary || row.strategic_uses?.[0]?.use || row.volume_context || "Linked metadata record")}</p></article>`).join("") || '<p class="empty-note">No pilot record matched every token. Try the full FRUS index for broader discovery.</p>';
    syncUrl({ q: query });
    if (shouldScroll) section.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }

  function bindSearch(initialQuery) {
    $("globalSearchForm").addEventListener("submit", (event) => {
      event.preventDefault();
      runGlobalSearch($("globalQuery").value, true);
    });
    document.querySelectorAll("[data-search]").forEach((button) => button.addEventListener("click", () => {
      $("globalQuery").value = button.dataset.search;
      runGlobalSearch(button.dataset.search, true);
    }));
    $("closeSearch").addEventListener("click", () => {
      $("searchResultsSection").classList.add("is-hidden");
      $("globalQuery").value = "";
      syncUrl({ q: "" });
    });
    if (initialQuery) {
      $("globalQuery").value = initialQuery;
      runGlobalSearch(initialQuery, false);
    }
  }

  function renderModernContext() {
    const row = state.data["modern-context"][0];
    $("modernContextContent").innerHTML = `<p>${H.escape(row.summary)}</p>${H.officialLink(row.source_url, row.source_label)}<p class="boundary-note">${H.escape(row.boundary_note)}</p>`;
  }

  async function init() {
    H.initTheme($("themeToggle"));
    H.initNavigation($("navToggle"), $("primaryNav"));
    const initialQuery = getUrlState();
    try {
      state.data = await H.loadAll();
      renderMetrics();
      renderMinerals();
      renderCountries();
      renderPeriods();
      renderFeature();
      renderMapControls();
      renderMap();
      renderInstruments();
      bindInstrumentControls();
      renderNaraSetup();
      renderStockpile();
      renderFrusControls();
      renderFrus();
      bindFrusControls();
      bindSearch(initialQuery);
      renderModernContext();
    } catch (error) {
      document.querySelector("main").innerHTML = `<section class="section load-error"><h1>Historical data could not be loaded</h1><p>${H.escape(error.message)}</p><p>Serve the repository over HTTP so the browser can read the modular JSON files.</p></section>`;
    }
  }

  init();
})();
