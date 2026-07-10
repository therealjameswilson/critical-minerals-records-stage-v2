(function () {
  "use strict";

  const FILES = [
    "sources", "minerals", "countries", "episodes", "agreements", "laws",
    "administrations", "stockpile-cases", "frus-documents", "statistics", "trade",
    "trade-details", "trade-research", "nara-queries", "country-briefs", "modern-context"
  ];

  function escape(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function text(value) {
    if (value == null || value === "") return "Not yet documented";
    if (Array.isArray(value)) return value.map(text).filter(Boolean).join("; ");
    if (typeof value === "object") {
      return Object.entries(value).map(([key, item]) => `${key}: ${text(item)}`).join("; ");
    }
    return String(value);
  }

  async function loadJson(name) {
    const response = await fetch(`data/history-stack/${name}.json`, { cache: "no-cache" });
    if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
    return response.json();
  }

  async function loadAll() {
    const [rows, atlas] = await Promise.all([
      Promise.all(FILES.map(loadJson)),
      fetch("data/atlas/atlas.json", { cache: "no-cache" }).then((response) => {
        if (!response.ok) throw new Error(`atlas: HTTP ${response.status}`);
        return response.json();
      })
    ]);
    const data = Object.fromEntries(FILES.map((name, index) => [name, rows[index]]));
    data.atlas = atlas;
    data.indexes = {};
    FILES.forEach((name) => {
      data.indexes[name] = new Map((data[name] || []).map((row) => [row.id, row]));
    });
    return data;
  }

  function displayName(row, type) {
    if (!row) return "Unknown record";
    const candidates = {
      minerals: [row.canonical_name],
      countries: [row.canonical_historical_name, row.present_day_name],
      episodes: [row.title],
      agreements: [row.short_title, row.official_title],
      laws: [row.official_title],
      administrations: [row.president],
      "stockpile-cases": [row.title],
      "frus-documents": [row.title, row.metadata_status === "subject-index-lead" && row.volume_context ? `FRUS discovery lead: ${row.volume_context}` : row.volume_context, `FRUS ${row.volume}, document ${row.document_number}`],
      "nara-queries": [row.label],
      sources: [row.label]
    };
    return (candidates[type] || [row.title, row.label, row.id]).find(Boolean) || row.id;
  }

  function detailHref(type, id) {
    const singular = {
      minerals: "mineral", countries: "country", episodes: "episode",
      agreements: "agreement", laws: "law", administrations: "administration",
      "stockpile-cases": "stockpile", "frus-documents": "frus"
    }[type] || type;
    return `history-stack.html?type=${encodeURIComponent(singular)}&id=${encodeURIComponent(id)}`;
  }

  function badge(label, kind) {
    return `<span class="badge badge-${escape(kind || "neutral")}">${escape(label)}</span>`;
  }

  function completenessBadge(status) {
    const labels = {
      "verified-pilot": "Verified pilot",
      partial: "Partial coverage",
      "research-queue": "Research queue",
      "verified-document": "Reviewed FRUS document",
      "subject-index-lead": "FRUS discovery lead"
    };
    const kind = status === "verified-pilot" || status === "verified-document" ? "verified" :
      status === "partial" ? "partial" : "queue";
    return badge(labels[status] || status || "Unspecified", kind);
  }

  function sourceBadge(source) {
    if (!source) return badge("Source unresolved", "queue");
    const short = {
      "frus-history-at-state": "FRUS",
      "frus-subject-index": "FRUS discovery index",
      "usgs-ds140": "USGS Data Series 140",
      "usgs-statistical-compendium": "USGS / Bureau of Mines",
      "usgs-circular-1141": "USGS Circular 1141",
      "nara-catalog-api": "NARA",
      "govinfo-statutes": "GovInfo",
      "state-treaties": "State treaty series",
      "census-historical-trade": "Census",
      "census-statistical-abstract-1948": "Census Statistical Abstract",
      "gsa-stockpile": "Stockpile records",
      "state-country-guide-bolivia": "State country guide",
      "state-country-guide-chile": "State country guide",
      "state-country-guide-congo-democratic-republic": "State country guide",
      "state-country-guide-indonesia": "State country guide",
      "loc-indonesia-mineral-regulation": "Library of Congress"
    }[source.id] || source.label;
    return badge(short, source.tier === 1 ? "source" : "discovery");
  }

  function sourceRow(source) {
    if (!source) return "";
    return `<article class="source-record">
      <div>${sourceBadge(source)} ${badge(`Tier ${source.tier}`, "neutral")}</div>
      <h4>${escape(source.label)}</h4>
      <p>${escape(source.scope)}</p>
      <p class="caveat"><strong>Use note:</strong> ${escape(source.trust_note)}</p>
      <a href="${escape(source.url)}" target="_blank" rel="noopener">Open authoritative source</a>
    </article>`;
  }

  function officialLink(url, label) {
    if (!url) return "";
    return `<a class="text-link" href="${escape(url)}" target="_blank" rel="noopener">${escape(label || "Open official record")} <span aria-hidden="true">↗</span></a>`;
  }

  function arrayLinks(data, type, ids, emptyLabel) {
    const index = data.indexes[type];
    const items = (ids || []).map((id) => index.get(id)).filter(Boolean);
    if (!items.length) return `<p class="empty-note">${escape(emptyLabel || "No linked records in the pilot.")}</p>`;
    return `<ul class="link-list">${items.map((row) => `<li><a href="${detailHref(type, row.id)}">${escape(displayName(row, type))}</a>${completenessBadge(row.completeness || row.metadata_status)}</li>`).join("")}</ul>`;
  }

  function frusCard(row, compact) {
    const title = row.title || `FRUS discovery lead: ${row.volume_context}`;
    return `<article class="record-card frus-card${compact ? " is-compact" : ""}">
      <div class="record-kicker">${badge("FRUS", "source")} ${completenessBadge(row.metadata_status)}</div>
      <h3>${escape(title)}</h3>
      <p class="record-meta">${row.date ? escape(row.date) : `Volume span ${escape(row.volume_year_start)}–${escape(row.volume_year_end)}`} · ${escape(row.volume)}, document ${escape(row.document_number)}</p>
      ${row.contextual_summary ? `<p>${escape(row.contextual_summary)}</p>` : `<p class="caveat">The title and date have not been curated at document level. The text shown above is volume or chapter navigation context.</p>`}
      <div class="tag-row">${(row.mineral_ids || []).map((item) => badge(item, "neutral")).join("")}${(row.policy_themes || []).map((item) => badge(item, "concept")).join("")}</div>
      <div class="record-actions">
        <a href="${detailHref("frus-documents", row.id)}">Open History Stack</a>
        ${officialLink(row.stable_url, "Read in FRUS")}
      </div>
    </article>`;
  }

  function formatNumber(value) {
    if (!Number.isFinite(Number(value))) return text(value);
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(Number(value));
  }

  function yearRange(row) {
    const start = row.start || row.volume_year_start || (row.historical_scope && row.historical_scope.start);
    const end = row.end || row.volume_year_end || (row.historical_scope && row.historical_scope.end);
    if (!start && !end) return "Date not documented";
    return start === end || !end ? String(start) : `${start}–${end}`;
  }

  function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("history-theme", theme);
  }

  function initTheme(toggle) {
    const stored = localStorage.getItem("history-theme");
    const preferred = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    setTheme(stored || preferred);
    if (toggle) {
      toggle.addEventListener("click", () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
    }
  }

  function initNavigation(toggle, nav) {
    if (!toggle || !nav) return;
    const close = () => {
      toggle.setAttribute("aria-expanded", "false");
      nav.classList.remove("is-open");
    };
    toggle.addEventListener("click", () => {
      const expanded = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!expanded));
      nav.classList.toggle("is-open", !expanded);
    });
    nav.querySelectorAll("a").forEach((link) => link.addEventListener("click", close));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });
  }

  window.HistoryData = {
    FILES, escape, text, loadAll, displayName, detailHref, badge,
    completenessBadge, sourceBadge, sourceRow, officialLink, arrayLinks,
    frusCard, formatNumber, yearRange, initTheme, initNavigation
  };
})();
