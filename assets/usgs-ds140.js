(function () {
  "use strict";

  const H = window.HistoryData;
  const refs = {
    metrics: document.getElementById("ds140Metrics"),
    commodity: document.getElementById("ds140Commodity"),
    series: document.getElementById("ds140Series"),
    measure: document.getElementById("ds140Measure"),
    year: document.getElementById("ds140Year"),
    yearValue: document.getElementById("ds140YearValue"),
    source: document.getElementById("ds140Source"),
    yearPanel: document.getElementById("ds140YearPanel"),
    chart: document.getElementById("ds140Chart"),
    quality: document.getElementById("ds140Quality"),
    tableCaption: document.getElementById("ds140TableCaption"),
    tableBody: document.getElementById("ds140TableBody"),
    download: document.getElementById("ds140Download")
  };
  const state = { catalog: null, commodity: null, series: null, measure: null, year: 1983 };

  function escape(value) { return H.escape(value); }
  function number(value) { return H.formatNumber(value); }
  function option(value, label, selected) { return `<option value="${escape(value)}"${selected ? " selected" : ""}>${escape(label)}</option>`; }
  function observation(measure, year) { return measure.observations.find((row) => row[0] === year); }

  function queryState() {
    const params = new URLSearchParams(location.search);
    state.year = Math.max(1861, Math.min(1992, Number(params.get("year")) || 1983));
    return { commodity: params.get("commodity") || "rare-earths", series: params.get("series"), measure: params.get("measure") };
  }

  function updateUrl() {
    const params = new URLSearchParams();
    params.set("commodity", state.commodity.commodity.id);
    params.set("series", state.series.id);
    params.set("measure", state.measure.id);
    params.set("year", String(state.year));
    history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
  }

  function renderMetrics() {
    const rows = [
      [number(state.catalog.commodity_count), "official commodity workbooks"],
      [number(state.catalog.series_count), "separate worksheet series"],
      [number(state.catalog.measure_count), "published measures"],
      [number(state.catalog.observation_count), "numeric observations"],
      ["1900–1992", "observed catalog span"]
    ];
    refs.metrics.innerHTML = rows.map(([value, label]) => `<div><strong>${escape(value)}</strong><span>${escape(label)}</span></div>`).join("");
  }

  async function loadCommodity(id, requestedSeries, requestedMeasure) {
    const entry = state.catalog.commodities.find((row) => row.id === id) || state.catalog.commodities[0];
    const response = await fetch(entry.data_url, { cache: "no-cache" });
    if (!response.ok) throw new Error(`${entry.title}: HTTP ${response.status}`);
    state.commodity = await response.json();
    state.series = state.commodity.series.find((row) => row.id === requestedSeries) || state.commodity.series[0];
    state.measure = state.series.measures.find((row) => row.id === requestedMeasure) || state.series.measures[0];
    refs.commodity.value = state.commodity.commodity.id;
    refs.series.innerHTML = state.commodity.series.map((row) => option(row.id, row.label, row.id === state.series.id)).join("");
    renderMeasureOptions();
    render();
  }

  function renderMeasureOptions() {
    refs.measure.innerHTML = state.series.measures.map((row) => option(row.id, `${row.label} (${row.observation_count} years)`, row.id === state.measure.id)).join("");
  }

  function renderSource() {
    const commodity = state.commodity.commodity;
    const summary = state.commodity.summary;
    refs.source.innerHTML = `<div><span class="badge badge-source">USGS Data Series 140</span><span class="badge badge-verified">Numeric XLSX extraction</span></div><div><strong>${escape(commodity.title)}</strong><span>${escape(summary.year_start)}–${escape(summary.year_end)} · ${escape(number(summary.observation_count))} observations · updated ${escape(commodity.update_year)}</span></div><div><a href="${escape(commodity.source_url)}" target="_blank" rel="noopener">Source page ↗</a><a href="${escape(commodity.download_url)}" target="_blank" rel="noopener">Official XLSX ↗</a></div>`;
  }

  function renderYearPanel() {
    const available = state.series.measures.map((measure) => ({ measure, row: observation(measure, state.year) })).filter((item) => item.row);
    refs.yearPanel.innerHTML = `<div class="ds140-year-heading"><div><p class="eyebrow">Exact-year published values</p><h3>${escape(state.commodity.commodity.title)}, ${escape(state.year)}</h3></div><span>${escape(available.length)} of ${escape(state.series.measures.length)} measures reported</span></div>${available.length ? `<div class="atlas-number-grid atlas-number-grid-complete">${available.map(({ measure, row }) => `<article><strong>${escape(number(row[1]))}</strong><span>${escape(measure.label)}</span><small>${escape(measure.unit)}</small><small>${escape(state.series.worksheet)}, row ${escape(row[2])}, column ${escape(measure.column)}</small></article>`).join("")}</div>` : `<p class="empty-note">No numeric cells are published for this worksheet series in ${escape(state.year)}. This is not treated as zero.</p>`}`;
  }

  function chartSvg() {
    const rows = state.measure.observations;
    if (rows.length < 2) return `<p class="empty-note">Fewer than two numeric observations are available for a line chart.</p>`;
    const width = 900, height = 330, left = 78, right = 24, top = 24, bottom = 52;
    const years = rows.map((row) => row[0]);
    const values = rows.map((row) => row[1]);
    const minYear = Math.min(...years), maxYear = Math.max(...years);
    let minValue = Math.min(...values), maxValue = Math.max(...values);
    if (minValue === maxValue) { minValue -= 1; maxValue += 1; }
    const x = (year) => left + ((year - minYear) / Math.max(1, maxYear - minYear)) * (width - left - right);
    const y = (value) => top + (1 - ((value - minValue) / (maxValue - minValue))) * (height - top - bottom);
    const path = rows.map((row, index) => `${index ? "L" : "M"}${x(row[0]).toFixed(2)},${y(row[1]).toFixed(2)}`).join(" ");
    const xTicks = [minYear, Math.round(minYear + (maxYear - minYear) / 2), maxYear];
    const yTicks = [minValue, (minValue + maxValue) / 2, maxValue];
    const selected = observation(state.measure, state.year);
    return `<svg class="ds140-chart" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="ds140-svg-title ds140-svg-desc"><title id="ds140-svg-title">${escape(state.measure.label)} for ${escape(state.commodity.commodity.title)}</title><desc id="ds140-svg-desc">Line chart of ${escape(rows.length)} published observations from ${escape(minYear)} through ${escape(maxYear)}. An accessible table follows.</desc>${yTicks.map((tick) => `<line x1="${left}" y1="${y(tick)}" x2="${width - right}" y2="${y(tick)}" class="chart-grid"/><text x="${left - 10}" y="${y(tick) + 4}" text-anchor="end">${escape(number(tick))}</text>`).join("")}${xTicks.map((tick) => `<text x="${x(tick)}" y="${height - 20}" text-anchor="middle">${escape(tick)}</text>`).join("")}<path d="${path}" class="chart-line"/>${selected ? `<circle cx="${x(selected[0])}" cy="${y(selected[1])}" r="6" class="chart-selected"><title>${escape(selected[0])}: ${escape(number(selected[1]))} ${escape(state.measure.unit)}</title></circle>` : ""}</svg>`;
  }

  function renderChartAndTable() {
    refs.chart.innerHTML = `<div class="ds140-chart-heading"><strong>${escape(state.measure.label)}</strong><span>${escape(state.measure.unit)}</span></div>${chartSvg()}`;
    refs.tableCaption.textContent = `${state.commodity.commodity.title}: ${state.series.label}, ${state.measure.label}`;
    refs.tableBody.innerHTML = state.measure.observations.map((row) => `<tr${row[0] === state.year ? ' class="is-selected-year"' : ""}><th scope="row">${escape(row[0])}</th><td>${escape(number(row[1]))}</td><td>${escape(state.measure.unit)}</td><td>${escape(state.series.worksheet)}, row ${escape(row[2])}, column ${escape(state.measure.column)} (${escape(state.measure.label)})</td></tr>`).join("");
  }

  function renderQuality() {
    const missing = state.measure.missing;
    refs.quality.innerHTML = `<h3 id="quality-title">Data quality</h3><dl><div><dt>Published observations</dt><dd>${escape(number(state.measure.observation_count))}</dd></div><div><dt>Observed span</dt><dd>${escape(state.measure.year_start)}–${escape(state.measure.year_end)}</dd></div><div><dt>Not available</dt><dd>${escape(number(missing.not_available))}</dd></div><div><dt>Withheld</dt><dd>${escape(number(missing.withheld))}</dd></div><div><dt>Blank cells</dt><dd>${escape(number(missing.blank))}</dd></div><div><dt>Other nonnumeric</dt><dd>${escape(number(missing.other_nonnumeric))}</dd></div></dl><p class="caveat"><strong>Interpretive limit:</strong> ${escape(state.commodity.commodity.caveat)}</p><p>${escape(state.commodity.commodity.conversion_methodology)}</p>`;
  }

  function render() {
    refs.year.value = String(state.year);
    refs.yearValue.value = String(state.year);
    renderSource(); renderYearPanel(); renderChartAndTable(); renderQuality(); updateUrl();
  }

  function downloadCsv() {
    const header = ["commodity", "worksheet", "measure", "year", "value", "unit", "source_url"];
    const quote = (value) => `"${String(value).replaceAll('"', '""')}"`;
    const lines = [header, ...state.measure.observations.map((row) => [state.commodity.commodity.title, state.series.worksheet, state.measure.label, row[0], row[1], state.measure.unit, state.commodity.commodity.source_url])];
    const blob = new Blob([lines.map((row) => row.map(quote).join(",")).join("\n") + "\n"], { type: "text/csv" });
    const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `usgs-ds140-${state.commodity.commodity.id}-${state.series.id}-${state.measure.id}.csv`; link.click(); URL.revokeObjectURL(link.href);
  }

  async function init() {
    H.initTheme(document.getElementById("themeToggle"));
    H.initNavigation(document.getElementById("navToggle"), document.getElementById("primaryNav"));
    const requested = queryState();
    const response = await fetch("data/usgs-ds140/catalog.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`DS140 catalog: HTTP ${response.status}`);
    state.catalog = await response.json(); renderMetrics();
    refs.commodity.innerHTML = state.catalog.commodities.filter((row) => row.status === "verified-numeric-extraction").map((row) => option(row.id, `${row.title} (${number(row.observation_count)})`, row.id === requested.commodity)).join("");
    await loadCommodity(requested.commodity, requested.series, requested.measure);
    refs.commodity.addEventListener("change", () => loadCommodity(refs.commodity.value));
    refs.series.addEventListener("change", () => { state.series = state.commodity.series.find((row) => row.id === refs.series.value); state.measure = state.series.measures[0]; renderMeasureOptions(); render(); });
    refs.measure.addEventListener("change", () => { state.measure = state.series.measures.find((row) => row.id === refs.measure.value); render(); });
    refs.year.addEventListener("input", () => { state.year = Number(refs.year.value); render(); });
    refs.download.addEventListener("click", downloadCsv);
  }

  init().catch((error) => { refs.yearPanel.innerHTML = `<p class="empty-note">The USGS statistical library could not load: ${escape(error.message)}</p>`; console.error(error); });
}());
