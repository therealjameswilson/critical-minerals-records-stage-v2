(function () {
  "use strict";

  const H = window.HistoryData;
  const $ = (id) => document.getElementById(id);
  const EMPTY_COLLECTION = { type: "FeatureCollection", features: [] };
  const LENS_IDS = ["frus-activity", "resource-geography", "historical-events", "quantitative-trade-flows"];
  const DEFAULT_LAYERS = [
    "frus-activity", "access-relationships", "agreements",
    "stockpile-policy", "historical-events", "nara-discovery", "resource-geography"
  ];
  const MARKER_LABELS = {
    agreements: "§",
    "stockpile-policy": "S",
    "nara-discovery": "A",
    "resource-geography": "◆"
  };
  const COVERAGE_LABELS = {
    "document-plus-context": "FRUS + official context",
    "documentary-only": "FRUS evidence",
    "context-only": "Context only",
    sparse: "Research gap"
  };
  const GAP_LABELS = {
    frus: "No checked-in FRUS pilot record matches this exact selection.",
    geography: "No country is linked by year-specific checked-in evidence.",
    statistics: "No exact-year commodity statistic or trade row is normalized.",
    policy: "No dated agreement, law, or stockpile pathway is linked.",
    archives: "No structured NARA query plan matches this exact selection."
  };

  function option(value, label, selected) {
    return `<option value="${H.escape(value)}"${String(value) === String(selected) ? " selected" : ""}>${H.escape(label)}</option>`;
  }

  function yearFromDate(value) {
    return value ? Number(String(value).slice(0, 4)) : null;
  }

  function catalogUrl(query) {
    return `https://catalog.archives.gov/search?q=${encodeURIComponent(query)}`;
  }

  class HistoricalAtlas {
    constructor(options) {
      this.data = options.data;
      this.atlas = options.data.atlas;
      this.onChange = options.onChange || function () {};
      const supportedLayers = new Set(this.atlas.layers.filter((row) => row.availability === "supported").map((row) => row.id));
      const requestedLayers = options.state.layers && options.state.layers.length ? options.state.layers : DEFAULT_LAYERS;
      this.state = {
        year: Number(options.state.year) || this.atlas.meta.default_year,
        mineral: options.state.mineral || this.atlas.meta.default_mineral,
        country: options.state.country || null,
        mode: LENS_IDS.includes(options.state.mode) ? options.state.mode : "frus-activity",
        layers: new Set(requestedLayers.filter((id) => supportedLayers.has(id))),
        tab: "summary"
      };
      this.map = null;
      this.mapReady = false;
      this.orientation = null;
      this.markers = [];
      this.popup = null;
      this.timer = null;
      this.bound = false;
      this.themeObserver = null;
      this.dataWebLoaded = this.data["dataweb-trade"].length > 0;
      this.dataWebLoading = null;
      this.comtradeLoaded = this.data["comtrade-rare-earth"].length > 0;
      this.comtradeLoading = null;
      this.strategicComtradeLoaded = this.data["comtrade-strategic-materials"].length > 0;
      this.strategicComtradeLoading = null;
      this.annualSnapshotsLoaded = this.data["annual-snapshots"].length > 0;
      this.annualSnapshotsLoading = null;
    }

    async init() {
      await this.ensureAnnualSnapshots();
      if (this.state.year >= 1989) await this.ensureDataWebTrade();
      if (this.state.year >= 1962 && ["rare-earth-elements", "all"].includes(this.state.mineral)) await this.ensureComtrade();
      if (this.state.year >= 1962 && this.state.mineral !== "rare-earth-elements") await this.ensureStrategicComtrade();
      this.renderControls();
      this.bindControls();
      this.renderLayerControls();
      this.renderLayerTable();
      this.renderAll();
      await this.initMap();
      this.renderAll();
      return this;
    }

    async ensureAnnualSnapshots() {
      if (this.annualSnapshotsLoaded) return this.data["annual-snapshots"];
      if (!this.annualSnapshotsLoading) {
        this.annualSnapshotsLoading = H.loadJson("annual-snapshots").then((rows) => {
          this.data["annual-snapshots"] = rows;
          this.data.indexes["annual-snapshots"] = new Map(rows.map((row) => [row.id, row]));
          this.annualSnapshotsLoaded = true;
          return rows;
        }).catch((error) => {
          this.annualSnapshotsLoading = null;
          throw error;
        });
      }
      return this.annualSnapshotsLoading;
    }

    async ensureDataWebTrade() {
      if (this.dataWebLoaded) return this.data["dataweb-trade"];
      if (!this.dataWebLoading) {
        this.dataWebLoading = H.loadJson("dataweb-trade").then((rows) => {
          this.data["dataweb-trade"] = rows;
          this.data.indexes["dataweb-trade"] = new Map(rows.map((row) => [row.id, row]));
          this.dataWebLoaded = true;
          return rows;
        }).catch((error) => {
          this.dataWebLoading = null;
          throw error;
        });
      }
      return this.dataWebLoading;
    }

    async ensureComtrade() {
      if (this.comtradeLoaded) return this.data["comtrade-rare-earth"];
      if (!this.comtradeLoading) {
        this.comtradeLoading = H.loadJson("comtrade-rare-earth").then((rows) => {
          this.data["comtrade-rare-earth"] = rows;
          this.data.indexes["comtrade-rare-earth"] = new Map(rows.map((row) => [row.id, row]));
          this.comtradeLoaded = true;
          return rows;
        }).catch((error) => {
          this.comtradeLoading = null;
          throw error;
        });
      }
      return this.comtradeLoading;
    }

    async ensureStrategicComtrade() {
      if (this.strategicComtradeLoaded) return this.data["comtrade-strategic-materials"];
      if (!this.strategicComtradeLoading) {
        this.strategicComtradeLoading = H.loadJson("comtrade-strategic-materials").then((rows) => {
          this.data["comtrade-strategic-materials"] = rows;
          this.data.indexes["comtrade-strategic-materials"] = new Map(rows.map((row) => [row.id, row]));
          this.strategicComtradeLoaded = true;
          return rows;
        }).catch((error) => {
          this.strategicComtradeLoading = null;
          throw error;
        });
      }
      return this.strategicComtradeLoading;
    }

    country(id) {
      return this.data.indexes.countries.get(id);
    }

    atlasCountry(id) {
      return this.atlas.countries.find((row) => row.id === id);
    }

    layer(id) {
      return this.atlas.layers.find((row) => row.id === id);
    }

    historicalName(country, year) {
      const period = (country.names_by_period || []).find((row) => row.start <= year && row.end >= year);
      return period ? period.name : country.canonical_historical_name;
    }

    countryExists(country) {
      return (country.names_by_period || []).some((row) => row.start <= this.state.year && row.end >= this.state.year);
    }

    mineralMatches(ids, emptyMatches) {
      if (this.state.mineral === "all") return true;
      if (!ids || !ids.length) return Boolean(emptyMatches);
      return ids.includes(this.state.mineral);
    }

    activeFrus(country) {
      return (country.frus_document_ids || [])
        .map((id) => this.data.indexes["frus-documents"].get(id))
        .filter(Boolean)
        .filter((row) => row.volume_year_start <= this.state.year && row.volume_year_end >= this.state.year)
        .filter((row) => this.mineralMatches(row.mineral_ids, false));
    }

    activeEvents(countryId) {
      return this.atlas.events.filter((row) =>
        row.country_id === countryId && row.start <= this.state.year && row.end >= this.state.year &&
        this.mineralMatches(row.mineral_ids, true)
      );
    }

    activeInstruments(countryId) {
      return this.atlas.instruments.filter((row) =>
        row.country_id === countryId && row.year === this.state.year && this.mineralMatches(row.mineral_ids, true)
      );
    }

    activeRelationships() {
      if (!this.state.layers.has("access-relationships")) return [];
      return this.atlas.relationships.filter((row) =>
        row.year === this.state.year && this.mineralMatches(row.mineral_ids, true)
      );
    }

    activeNara(countryId) {
      return this.atlas.archival_plans.filter((row) =>
        row.country_ids.includes(countryId) && row.start <= this.state.year && row.end >= this.state.year &&
        this.mineralMatches(row.mineral_ids, true)
      );
    }

    activeStockpile(countryId) {
      return this.atlas.stockpile_policy.filter((row) =>
        row.country_id === countryId && row.start <= this.state.year && row.end >= this.state.year &&
        this.mineralMatches(row.mineral_ids, true)
      );
    }

    activeDataWebTrade(direction) {
      if (this.state.year < 1989 || this.state.year > 1992) return [];
      return this.data["dataweb-trade"].filter((row) =>
        row.year === this.state.year && (!direction || row.direction === direction) &&
        (this.state.mineral === "all" || row.mineral_id === this.state.mineral)
      );
    }

    activeComtrade() {
      if (!["rare-earth-elements", "all"].includes(this.state.mineral) || this.state.year < 1962 || this.state.year > 1992) return [];
      return this.data["comtrade-rare-earth"].filter((row) => row.year === this.state.year);
    }

    activeStrategicComtrade() {
      if (this.state.year < 1962 || this.state.year > 1992 || this.state.mineral === "rare-earth-elements") return [];
      return this.data["comtrade-strategic-materials"].filter((row) =>
        row.year === this.state.year && (this.state.mineral === "all" || row.mineral_id === this.state.mineral)
      );
    }

    annualSnapshot() {
      return this.data.indexes["annual-snapshots"].get(`annual-${this.state.year}`);
    }

    annualSlice() {
      const snapshot = this.annualSnapshot();
      if (!snapshot) return null;
      return this.state.mineral === "all" ? snapshot.overall : snapshot.materials[this.state.mineral];
    }

    countryValue(country) {
      if (!this.countryExists(country) || !this.state.layers.has(this.state.mode)) return 0;
      if (this.state.mode === "frus-activity") return this.activeFrus(country).length;
      if (this.state.mode === "historical-events") return this.activeEvents(country.id).length;
      if (this.state.mode === "resource-geography") {
        const annual = this.annualSlice();
        const evidenceCount = annual?.country_evidence_counts[country.id] || 0;
        const hasProfileContext = annual?.profile_context_country_ids.includes(country.id);
        return evidenceCount ? Math.min(4, evidenceCount + 1) : hasProfileContext ? 1 : 0;
      }
      if (this.state.mode === "quantitative-trade-flows") {
        const atlasCountry = this.atlasCountry(country.id);
        return this.partnerTradeTotals("imports").get(atlasCountry?.a3)?.value || 0;
      }
      return 0;
    }

    selectedMineral() {
      return this.state.mineral === "all" ? null : this.data.indexes.minerals.get(this.state.mineral);
    }

    setState(patch, notify) {
      Object.assign(this.state, patch);
      this.renderAll();
      if (this.state.year >= 1989 && !this.dataWebLoaded) {
        this.ensureDataWebTrade().then(() => this.renderAll()).catch((error) => {
          $("atlasMapStatus").textContent = `DataWeb context could not be loaded: ${error.message}`;
        });
      }
      if (this.state.year >= 1962 && ["rare-earth-elements", "all"].includes(this.state.mineral) && !this.comtradeLoaded) {
        this.ensureComtrade().then(() => this.renderAll()).catch((error) => {
          $("atlasMapStatus").textContent = `Comtrade context could not be loaded: ${error.message}`;
        });
      }
      if (this.state.year >= 1962 && this.state.mineral !== "rare-earth-elements" && !this.strategicComtradeLoaded) {
        this.ensureStrategicComtrade().then(() => this.renderAll()).catch((error) => {
          $("atlasMapStatus").textContent = `Comtrade context could not be loaded: ${error.message}`;
        });
      }
      if (notify !== false) {
        this.onChange({
          year: this.state.year,
          mineral: this.state.mineral,
          country: this.state.country,
          mode: this.state.mode,
          layers: [...this.state.layers]
        });
      }
    }

    renderControls() {
      $("mapYear").value = this.state.year;
      $("mapYearValue").textContent = this.state.year;
      $("mapMineral").innerHTML = option("all", "All pilot materials", this.state.mineral) +
        this.data.minerals.map((row) => option(row.id, row.canonical_name, this.state.mineral)).join("");
      $("atlasMode").innerHTML = LENS_IDS.map((id) => {
        const row = this.layer(id);
        return option(id, row.title, this.state.mode);
      }).join("");
    }

    bindControls() {
      if (this.bound) return;
      this.bound = true;
      $("mapYear").addEventListener("input", (event) => this.setState({ year: Number(event.target.value), country: null }));
      $("mapMineral").addEventListener("change", (event) => this.setState({ mineral: event.target.value, country: null }));
      $("atlasMode").addEventListener("change", (event) => {
        const layers = new Set(this.state.layers);
        layers.add(event.target.value);
        this.setState({ mode: event.target.value, layers });
        this.renderLayerControls();
      });
      $("atlasPrevYear").addEventListener("click", () => this.setState({ year: Math.max(1861, this.state.year - 1), country: null }));
      $("atlasNextYear").addEventListener("click", () => this.setState({ year: Math.min(1992, this.state.year + 1), country: null }));
      $("atlasResetView").addEventListener("click", () => this.fitWorld());
      $("atlasPlay").addEventListener("click", () => this.togglePlayback());
      const tabs = [...document.querySelectorAll("[data-atlas-tab]")];
      tabs.forEach((button, index) => {
        button.addEventListener("click", () => {
          this.state.tab = button.dataset.atlasTab;
          this.renderTabs();
          this.renderPanel();
        });
        button.addEventListener("keydown", (event) => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          let next = index;
          if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
          if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
          if (event.key === 'Home') next = 0;
          if (event.key === 'End') next = tabs.length - 1;
          tabs[next].focus();
          tabs[next].click();
        });
      });
      $("atlasLayerControls").addEventListener("change", (event) => {
        const checkbox = event.target.closest("[data-atlas-layer]");
        if (!checkbox || checkbox.disabled) return;
        const layers = new Set(this.state.layers);
        if (checkbox.checked) layers.add(checkbox.value);
        else layers.delete(checkbox.value);
        this.setState({ layers });
      });
      $("atlasLayerControls").addEventListener("click", (event) => {
        const button = event.target.closest("[data-layer-info]");
        if (!button) return;
        this.renderLayerNote(button.dataset.layerInfo);
      });
      document.addEventListener("visibilitychange", () => {
        if (document.hidden && this.timer) this.stopPlayback();
      });
    }

    togglePlayback() {
      if (this.timer) {
        this.stopPlayback();
        return;
      }
      $("atlasPlay").setAttribute("aria-pressed", "true");
      $("atlasPlay").classList.add("is-active");
      $("atlasPlay").querySelector("[aria-hidden]").textContent = "Ⅱ";
      $("atlasPlay").querySelector(".visually-hidden").textContent = "Pause timeline";
      this.timer = window.setInterval(() => {
        const year = this.state.year >= 1992 ? 1861 : this.state.year + 1;
        this.setState({ year, country: null });
      }, 700);
    }

    stopPlayback() {
      window.clearInterval(this.timer);
      this.timer = null;
      $("atlasPlay").setAttribute("aria-pressed", "false");
      $("atlasPlay").classList.remove("is-active");
      $("atlasPlay").querySelector("[aria-hidden]").textContent = "▶";
      $("atlasPlay").querySelector(".visually-hidden").textContent = "Play timeline";
    }

    renderLayerControls() {
      const supported = this.atlas.layers.filter((row) => row.availability === "supported");
      const locked = this.atlas.layers.filter((row) => row.availability === "locked");
      const rowHtml = (row) => `<div class="atlas-layer-row${row.availability === "locked" ? " is-locked" : ""}">
        <label>
          <input type="checkbox" data-atlas-layer value="${H.escape(row.id)}"${this.state.layers.has(row.id) ? " checked" : ""}${row.availability === "locked" ? " disabled" : ""}>
          <span class="atlas-layer-key" data-layer-key="${H.escape(row.id)}" aria-hidden="true">${H.escape(row.short_title.slice(0, 2).toUpperCase())}</span>
          <span><strong>${H.escape(row.title)}</strong><small>${row.availability === "locked" ? "Awaiting official data" : H.escape(row.geometry.replaceAll("-", " "))}</small></span>
        </label>
        <button type="button" data-layer-info="${H.escape(row.id)}" aria-label="Explain ${H.escape(row.title)}">i</button>
      </div>`;
      $("atlasLayerControls").innerHTML = `<div class="atlas-layer-group"><strong>Available evidence layers</strong>${supported.map(rowHtml).join("")}</div>
        <details class="atlas-locked-layers"><summary>Layers awaiting official data (${locked.length})</summary>${locked.map(rowHtml).join("")}</details>`;
      this.renderLayerNote(this.state.mode);
    }

    renderLayerNote(id) {
      const row = this.layer(id);
      if (!row) return;
      const sources = row.source_ids.map((sourceId) => this.data.indexes.sources.get(sourceId)).filter(Boolean);
      $("atlasLayerNote").innerHTML = `<strong>${H.escape(row.title)}</strong>
        <p>${H.escape(row.value_semantics || row.required_data || "Layer definition pending.")}</p>
        <p class="caveat">${H.escape(row.caveat)}</p>
        <div class="tag-row">${sources.map(H.sourceBadge).join("")}</div>`;
    }

    renderLayerTable() {
      $("atlasLayerTable").innerHTML = `<h3>Layer definitions and availability</h3><div class="table-scroll"><table><thead><tr><th>Layer</th><th>Status</th><th>Meaning or requirement</th><th>Caveat</th></tr></thead><tbody>${this.atlas.layers.map((row) => `<tr><td>${H.escape(row.title)}</td><td>${H.escape(row.availability === "supported" ? "Available" : "Awaiting data")}</td><td>${H.escape(row.value_semantics || row.required_data)}</td><td>${H.escape(row.caveat)}</td></tr>`).join("")}</tbody></table></div>`;
    }

    async initMap() {
      if (!window.maplibregl || (typeof window.maplibregl.supported === "function" && !window.maplibregl.supported())) {
        this.showMapFallback("MapLibre or WebGL is unavailable in this browser.");
        return;
      }
      try {
        const response = await fetch("data/atlas/world-orientation.geojson", { cache: "force-cache" });
        if (!response.ok) throw new Error(`orientation geometry: HTTP ${response.status}`);
        this.orientation = await response.json();
        this.map = new window.maplibregl.Map({
          container: "atlasMap",
          style: { version: 8, sources: {}, layers: [{ id: "background", type: "background", paint: { "background-color": "#d6e1e1" } }] },
          center: [-15, 14],
          zoom: 0.8,
          minZoom: -1.25,
          maxZoom: 6,
          renderWorldCopies: false,
          attributionControl: false,
          cooperativeGestures: true
        });
        this.map.addControl(new window.maplibregl.NavigationControl({ showCompass: false }), "top-right");
        this.map.addControl(new window.maplibregl.ScaleControl({ maxWidth: 120, unit: "imperial" }), "bottom-left");
        this.map.addControl(new window.maplibregl.AttributionControl({
          compact: true,
          customAttribution: '<a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener">Natural Earth orientation geometry</a>'
        }));
        const mapLoaded = new Promise((resolve) => {
          let settled = false;
          let initialized = false;
          const finish = () => {
            if (settled) return;
            settled = true;
            window.clearTimeout(timeout);
            resolve();
          };
          const initialize = () => {
            if (initialized) return;
            initialized = true;
            this.onMapLoad();
            finish();
          };
          const timeout = window.setTimeout(finish, 12000);
          this.map.once("load", initialize);
          if (this.map.loaded()) initialize();
        });
        this.map.on("error", (event) => {
          if (event && event.error) $("atlasMapStatus").textContent = `Atlas map notice: ${event.error.message}`;
        });
        this.themeObserver = new MutationObserver(() => this.applyMapTheme());
        this.themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
        await mapLoaded;
      } catch (error) {
        this.showMapFallback(error.message);
      }
    }

    showMapFallback(message) {
      $("atlasMap").hidden = true;
      $("atlasMapFallback").hidden = false;
      $("atlasMapStatus").textContent = message;
    }

    onMapLoad() {
      this.map.addSource("atlas-graticule", { type: "geojson", data: this.graticuleGeoJson() });
      this.map.addLayer({
        id: "atlas-graticule", type: "line", source: "atlas-graticule",
        paint: { "line-color": "#91a5a6", "line-width": 0.6, "line-opacity": 0.34 }
      });
      this.map.addSource("orientation", { type: "geojson", data: this.orientation });
      this.map.addLayer({ id: "orientation-land", type: "fill", source: "orientation", paint: { "fill-color": "#e8e4d8", "fill-opacity": 0.96 } });
      this.map.addLayer({ id: "orientation-borders", type: "line", source: "orientation", paint: { "line-color": "#748383", "line-width": 0.7, "line-opacity": 0.74 } });
      this.map.addSource("atlas-trade-countries", { type: "geojson", data: EMPTY_COLLECTION });
      this.map.addLayer({
        id: "atlas-trade-fill", type: "fill", source: "atlas-trade-countries",
        paint: {
          "fill-color": ["interpolate", ["linear"], ["get", "trade_value"], 1, "#dce5d8", 100000, "#b8d2ca", 1000000, "#70a79f", 10000000, "#2e716d", 100000000, "#153650"],
          "fill-opacity": 0.86
        }
      });
      this.map.addSource("atlas-countries", { type: "geojson", data: EMPTY_COLLECTION });
      this.map.addLayer({
        id: "atlas-country-fill", type: "fill", source: "atlas-countries",
        paint: {
          "fill-color": ["case", ["get", "selected"], "#d2aa54", ["interpolate", ["linear"], ["get", "atlas_value"], 0, "#e8e4d8", 1, "#b8d2ca", 2, "#70a79f", 4, "#2e716d", 8, "#153650"]],
          "fill-opacity": ["case", ["get", "selected"], 0.92, [">", ["get", "atlas_value"], 0], 0.84, 0.08]
        }
      });
      this.map.addSource("atlas-events", { type: "geojson", data: EMPTY_COLLECTION });
      this.map.addLayer({
        id: "atlas-event-outline", type: "line", source: "atlas-events",
        paint: { "line-color": "#9b4937", "line-width": 2.2, "line-dasharray": [1.2, 1.2], "line-opacity": 0.9 }
      });
      this.map.addLayer({
        id: "atlas-country-outline", type: "line", source: "atlas-countries",
        paint: {
          "line-color": ["case", ["get", "selected"], "#f6d889", "#284f59"],
          "line-width": ["case", ["get", "selected"], 3.2, 1.15],
          "line-opacity": 0.9
        }
      });
      this.map.addSource("atlas-relationships", { type: "geojson", data: EMPTY_COLLECTION });
      this.map.addLayer({
        id: "atlas-relationship-halo", type: "line", source: "atlas-relationships",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#fff7df",
          "line-opacity": 0.72,
          "line-width": ["interpolate", ["linear"], ["get", "line_value"], 1, 4.5, 4, 8]
        }
      });
      this.map.addLayer({
        id: "atlas-relationship-lines", type: "line", source: "atlas-relationships",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#a87122",
          "line-opacity": 0.9,
          "line-dasharray": [2.4, 1.6],
          "line-width": ["interpolate", ["linear"], ["get", "line_value"], 1, 1.6, 4, 4.6]
        }
      });
      this.map.addSource("atlas-trade-flows", { type: "geojson", data: EMPTY_COLLECTION });
      this.map.addLayer({
        id: "atlas-trade-flow-halo", type: "line", source: "atlas-trade-flows",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#fff7df", "line-opacity": 0.68,
          "line-width": ["interpolate", ["linear"], ["get", "trade_value"], 1, 2.8, 1000000, 4.2, 100000000, 8.5]
        }
      });
      this.map.addLayer({
        id: "atlas-trade-flow-lines", type: "line", source: "atlas-trade-flows",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#b57a1f", "line-opacity": 0.82,
          "line-width": ["interpolate", ["linear"], ["get", "trade_value"], 1, 0.9, 1000000, 2.1, 100000000, 5.2]
        }
      });
      this.popup = new window.maplibregl.Popup({ closeButton: false, closeOnClick: false, maxWidth: "310px" });
      this.map.on("click", "atlas-country-fill", (event) => {
        const id = event.features && event.features[0] && event.features[0].properties.atlas_id;
        if (id) this.selectCountry(id);
      });
      this.map.on("mousemove", "atlas-country-fill", (event) => this.showCountryPopup(event));
      this.map.on("mouseleave", "atlas-country-fill", () => this.popup.remove());
      this.map.on("mouseenter", "atlas-country-fill", () => { this.map.getCanvas().style.cursor = "pointer"; });
      this.map.on("mouseleave", "atlas-country-fill", () => { this.map.getCanvas().style.cursor = ""; });
      this.map.on("mousemove", "atlas-relationship-lines", (event) => this.showRelationshipPopup(event));
      this.map.on("mouseleave", "atlas-relationship-lines", () => this.popup.remove());
      this.map.on("click", "atlas-trade-fill", (event) => {
        const id = event.features && event.features[0] && event.features[0].properties.atlas_id;
        if (id) this.selectCountry(id);
      });
      this.map.on("mousemove", "atlas-trade-fill", (event) => this.showTradePopup(event));
      this.map.on("mouseleave", "atlas-trade-fill", () => this.popup.remove());
      this.map.on("mouseenter", "atlas-trade-fill", () => { this.map.getCanvas().style.cursor = "pointer"; });
      this.map.on("mouseleave", "atlas-trade-fill", () => { this.map.getCanvas().style.cursor = ""; });
      this.map.on("mousemove", "atlas-trade-flow-lines", (event) => this.showTradePopup(event));
      this.map.on("mouseleave", "atlas-trade-flow-lines", () => this.popup.remove());
      this.mapReady = true;
      this.renderMap();
      this.applyMapTheme();
      window.setTimeout(() => {
        this.map.resize();
        this.fitWorld();
        this.renderMap();
      }, 100);
    }

    graticuleGeoJson() {
      const features = [];
      for (let longitude = -150; longitude <= 150; longitude += 30) {
        features.push({
          type: "Feature",
          properties: {},
          geometry: { type: "LineString", coordinates: Array.from({ length: 31 }, (_, index) => [longitude, -75 + index * 5]) }
        });
      }
      for (let latitude = -60; latitude <= 60; latitude += 20) {
        features.push({
          type: "Feature",
          properties: {},
          geometry: { type: "LineString", coordinates: Array.from({ length: 73 }, (_, index) => [-180 + index * 5, latitude]) }
        });
      }
      return { type: "FeatureCollection", features };
    }

    mapPalette() {
      return document.documentElement.dataset.theme === "dark" ? {
        ocean: "#102936", land: "#34484b", border: "#829497", grid: "#7d9297", halo: "#173744"
      } : {
        ocean: "#d6e1e1", land: "#e8e4d8", border: "#748383", grid: "#91a5a6", halo: "#fff7df"
      };
    }

    applyMapTheme() {
      if (!this.mapReady) return;
      const colors = this.mapPalette();
      [
        ["background", "background-color", colors.ocean],
        ["atlas-graticule", "line-color", colors.grid],
        ["orientation-land", "fill-color", colors.land],
        ["orientation-borders", "line-color", colors.border],
        ["atlas-relationship-halo", "line-color", colors.halo],
        ["atlas-trade-flow-halo", "line-color", colors.halo]
      ].forEach(([layer, property, value]) => {
        if (this.map.getLayer(layer)) this.map.setPaintProperty(layer, property, value);
      });
    }

    fitWorld() {
      if (!this.mapReady) return;
      const container = this.map.getContainer();
      const widthZoom = Math.log2(Math.max(320, container.clientWidth) / 540);
      const heightZoom = Math.log2(Math.max(360, container.clientHeight) / 400);
      const zoom = Math.max(-1.1, Math.min(1.25, widthZoom, heightZoom));
      this.map.easeTo({
        center: [0, 14],
        zoom,
        duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 450
      });
    }

    showCountryPopup(event) {
      const feature = event.features && event.features[0];
      if (!feature) return;
      const row = feature.properties;
      const lens = this.layer(this.state.mode);
      this.popup.setLngLat(event.lngLat).setHTML(`<strong>${H.escape(row.historical_name)}</strong><br><span>${H.escape(this.state.year)} · ${H.escape(lens.short_title)}: ${H.escape(row.atlas_value)}</span><br><small>${H.escape(lens.caveat)}</small>`).addTo(this.map);
    }

    showRelationshipPopup(event) {
      const feature = event.features && event.features[0];
      if (!feature) return;
      const row = feature.properties;
      this.popup.setLngLat(event.lngLat).setHTML(`<strong>${H.escape(row.title)}</strong><br><span>${H.escape(row.year)} · ${H.escape(row.line_value)} ${H.escape(row.line_value_semantics)}</span><br><small>Width does not represent trade volume.</small>`).addTo(this.map);
    }

    showTradePopup(event) {
      const feature = event.features && event.features[0];
      if (!feature) return;
      const row = feature.properties;
      this.popup.setLngLat(event.lngLat).setHTML(`<strong>${H.escape(row.partner_name)}</strong><br><span>${H.escape(this.state.year)} reported imports: ${H.escape(H.formatNumber(row.trade_value))} current dollars</span><br><small>${H.escape(row.commodity_count)} selected ${H.escape(row.commodity_label)}${Number(row.commodity_count) === 1 ? "" : "s"} · ${H.escape(row.source_name)}</small>`).addTo(this.map);
    }

    selectCountry(id) {
      this.setState({ country: id });
      const row = this.atlasCountry(id);
      if (this.mapReady && row) {
        this.map.easeTo({
          center: row.coordinates,
          zoom: Math.max(this.map.getZoom(), 2.15),
          duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 450
        });
      }
    }

    arcCoordinates(from, to) {
      const points = [];
      const bend = Math.min(18, Math.max(5, Math.abs(to[0] - from[0]) * 0.12));
      for (let index = 0; index <= 24; index += 1) {
        const t = index / 24;
        const longitude = (1 - t) * from[0] + t * to[0];
        const latitude = (1 - t) * from[1] + t * to[1] + Math.sin(Math.PI * t) * bend;
        points.push([longitude, Math.min(82, latitude)]);
      }
      return points;
    }

    countryGeoJson() {
      if (this.state.mode === "quantitative-trade-flows") return EMPTY_COLLECTION;
      const byA3 = new Map(this.atlas.countries.map((row) => [row.a3, row.id]));
      return {
        type: "FeatureCollection",
        features: this.orientation.features.filter((feature) => byA3.has(feature.properties.ADM0_A3)).map((feature) => {
          const id = byA3.get(feature.properties.ADM0_A3);
          const country = this.country(id);
          return {
            type: "Feature",
            geometry: feature.geometry,
            properties: {
              atlas_id: id,
              historical_name: this.historicalName(country, this.state.year),
              atlas_value: this.countryValue(country),
              selected: id === this.state.country
            }
          };
        })
      };
    }

    relationshipGeoJson() {
      const us = this.atlasCountry("united-states");
      return {
        type: "FeatureCollection",
        features: this.activeRelationships().map((row) => {
          const origin = this.atlasCountry(row.from_country_id);
          return {
            type: "Feature",
            geometry: { type: "LineString", coordinates: this.arcCoordinates(origin.coordinates, us.coordinates) },
            properties: {
              id: row.id,
              title: row.title,
              year: row.year,
              line_value: row.line_value,
              line_value_semantics: row.line_value_semantics
            }
          };
        })
      };
    }

    featureCenter(feature) {
      const points = [];
      const visit = (coordinates) => {
        if (!Array.isArray(coordinates)) return;
        if (coordinates.length >= 2 && typeof coordinates[0] === "number" && typeof coordinates[1] === "number") {
          points.push(coordinates);
          return;
        }
        coordinates.forEach(visit);
      };
      visit(feature?.geometry?.coordinates);
      if (!points.length) return null;
      const longitudes = points.map((point) => point[0]);
      const latitudes = points.map((point) => point[1]);
      return [
        (Math.min(...longitudes) + Math.max(...longitudes)) / 2,
        (Math.min(...latitudes) + Math.max(...latitudes)) / 2
      ];
    }

    dataWebPartnerTotals(direction) {
      const totals = new Map();
      this.activeDataWebTrade(direction).forEach((row) => {
        if (!row.partner_iso3 || !row.trade_value.value) return;
        const current = totals.get(row.partner_iso3) || {
          iso3: row.partner_iso3,
          name: row.source_partner_name,
          value: 0,
          codes: new Set(),
          rows: 0,
          source_name: "USITC DataWeb / Census",
          commodity_label: "HS6 heading"
        };
        current.value += row.trade_value.value;
        current.codes.add(row.commodity_code);
        current.rows += 1;
        totals.set(row.partner_iso3, current);
      });
      return totals;
    }

    comtradePartnerTotals(direction) {
      const flowCode = direction === "exports" ? "X" : "M";
      const rows = [...this.activeStrategicComtrade(), ...this.activeComtrade()].filter((row) =>
        row.reporter_iso3 === "USA" && row.flow_code === flowCode && row.partner_iso3
      );
      const totals = new Map();
      rows.forEach((row) => {
        const current = totals.get(row.partner_iso3) || {
          iso3: row.partner_iso3,
          name: row.partner_name,
          value: 0,
          codes: new Set(),
          rows: 0,
          source_name: "UN Comtrade / UN Statistics Division",
          commodity_label: `${row.classification_code} heading`
        };
        current.value += row.primary_value || 0;
        current.codes.add(`${row.classification_code}:${row.commodity_code}`);
        current.rows += 1;
        totals.set(row.partner_iso3, current);
      });
      return totals;
    }

    partnerTradeTotals(direction) {
      if (this.state.year >= 1989 && this.dataWebLoaded) return this.dataWebPartnerTotals(direction);
      return this.comtradePartnerTotals(direction);
    }

    partnerTradeSource() {
      return this.state.year >= 1989 && this.dataWebLoaded
        ? "USITC DataWeb / Census"
        : "UN Comtrade / UN Statistics Division";
    }

    tradeCountryGeoJson() {
      if (!this.state.layers.has("quantitative-trade-flows") || this.state.mode !== "quantitative-trade-flows") return EMPTY_COLLECTION;
      const totals = this.partnerTradeTotals("imports");
      const atlasByA3 = new Map(this.atlas.countries.map((row) => [row.a3, row.id]));
      return {
        type: "FeatureCollection",
        features: this.orientation.features.filter((feature) => totals.has(feature.properties.ADM0_A3)).map((feature) => {
          const total = totals.get(feature.properties.ADM0_A3);
          return {
            type: "Feature",
            geometry: feature.geometry,
            properties: {
              atlas_id: atlasByA3.get(total.iso3) || "",
              partner_name: total.name,
              partner_iso3: total.iso3,
              trade_value: total.value,
              commodity_count: total.codes.size,
              row_count: total.rows,
              source_name: total.source_name,
              commodity_label: total.commodity_label
            }
          };
        })
      };
    }

    tradeFlowGeoJson() {
      if (!this.state.layers.has("quantitative-trade-flows") || this.state.mode !== "quantitative-trade-flows") return EMPTY_COLLECTION;
      const us = this.atlasCountry("united-states");
      const featuresByA3 = new Map(this.orientation.features.map((feature) => [feature.properties.ADM0_A3, feature]));
      const totals = [...this.partnerTradeTotals("imports").values()]
        .sort((a, b) => b.value - a.value)
        .slice(0, 18);
      return {
        type: "FeatureCollection",
        features: totals.map((row) => {
          const center = this.featureCenter(featuresByA3.get(row.iso3));
          if (!center) return null;
          return {
            type: "Feature",
            geometry: { type: "LineString", coordinates: this.arcCoordinates(center, us.coordinates) },
            properties: {
              partner_name: row.name,
              partner_iso3: row.iso3,
              trade_value: row.value,
              commodity_count: row.codes.size,
              year: this.state.year,
              source_name: row.source_name,
              commodity_label: row.commodity_label
            }
          };
        }).filter(Boolean)
      };
    }

    eventGeoJson() {
      if (!this.state.layers.has("historical-events")) return EMPTY_COLLECTION;
      const activeIds = new Set(this.atlas.events.filter((row) =>
        row.start <= this.state.year && row.end >= this.state.year && this.mineralMatches(row.mineral_ids, true)
      ).map((row) => row.country_id));
      const byA3 = new Map(this.atlas.countries.filter((row) => activeIds.has(row.id)).map((row) => [row.a3, row.id]));
      return {
        type: "FeatureCollection",
        features: this.orientation.features.filter((feature) => byA3.has(feature.properties.ADM0_A3)).map((feature) => ({
          type: "Feature",
          geometry: feature.geometry,
          properties: { atlas_id: byA3.get(feature.properties.ADM0_A3) }
        }))
      };
    }

    renderMap() {
      if (!this.mapReady) return;
      this.map.getSource("atlas-countries").setData(this.countryGeoJson());
      this.map.getSource("atlas-events").setData(this.eventGeoJson());
      this.map.getSource("atlas-relationships").setData(this.relationshipGeoJson());
      this.map.getSource("atlas-trade-countries").setData(this.tradeCountryGeoJson());
      this.map.getSource("atlas-trade-flows").setData(this.tradeFlowGeoJson());
      this.renderMarkers();
    }

    clearMarkers() {
      this.markers.forEach((marker) => marker.remove());
      this.markers = [];
    }

    addMarker(countryId, kind, count, title, offset) {
      const row = this.atlasCountry(countryId);
      if (!row) return;
      const element = document.createElement("button");
      element.type = "button";
      element.className = `atlas-marker marker-${kind}`;
      element.innerHTML = `<span aria-hidden="true">${H.escape(MARKER_LABELS[kind] || "◆")}</span><b aria-hidden="true">${H.escape(count)}</b>`;
      element.setAttribute("aria-label", `${title}. Select ${this.historicalName(this.country(countryId), this.state.year)}.`);
      element.title = title;
      element.addEventListener("click", () => this.selectCountry(countryId));
      const marker = new window.maplibregl.Marker({ element, anchor: "center", offset: offset || [0, 0] }).setLngLat(row.coordinates).addTo(this.map);
      this.markers.push(marker);
    }

    renderMarkers() {
      this.clearMarkers();
      const countryIds = this.atlas.countries.map((row) => row.id);
      countryIds.forEach((id) => {
        const country = this.country(id);
        if (!this.countryExists(country)) return;
        if (this.state.layers.has("agreements")) {
          const rows = this.activeInstruments(id);
          if (rows.length) this.addMarker(id, "agreements", rows.length, `${rows.length} linked instrument${rows.length === 1 ? "" : "s"}`, [-14, -12]);
        }
        if (this.state.layers.has("nara-discovery")) {
          const rows = this.activeNara(id);
          if (rows.length) this.addMarker(id, "nara-discovery", rows.length, `${rows.length} NARA query plan${rows.length === 1 ? "" : "s"}`, [14, -12]);
        }
        if (this.state.layers.has("stockpile-policy")) {
          const rows = this.activeStockpile(id);
          if (rows.length) this.addMarker(id, "stockpile-policy", rows.length, `${rows.length} stockpile policy pathway${rows.length === 1 ? "" : "s"}`, [0, 14]);
        }
        if (this.state.layers.has("resource-geography") && (this.state.mineral === "all" ? country.mineral_ids.length : country.mineral_ids.includes(this.state.mineral))) {
          const annual = this.annualSlice();
          const evidenceCount = annual?.country_evidence_counts[id] || 0;
          const count = evidenceCount || "C";
          const title = evidenceCount
            ? `${evidenceCount} year-linked evidence connection${evidenceCount === 1 ? "" : "s"}; not production`
            : "Profile context only; no year-linked evidence";
          this.addMarker(id, "resource-geography", count, title, [0, -30]);
        }
      });
    }

    renderLegend() {
      const lens = this.layer(this.state.mode);
      if (this.state.mode === "quantitative-trade-flows") {
        const totals = this.partnerTradeTotals("imports");
        const count = [...totals.values()].reduce((sum, row) => sum + row.rows, 0);
        $("atlasLegend").innerHTML = `<span class="atlas-legend-kicker">Official trade context · ${H.escape(this.state.year)}</span><strong>${H.escape(lens.title)}</strong><div class="atlas-scale"><span><i data-scale="0"></i>$0</span><span><i data-scale="1"></i>$100K</span><span><i data-scale="2"></i>$1M</span><span><i data-scale="3"></i>$100M+</span></div><p>${H.escape(lens.value_semantics)}</p><p><i class="line-key"></i> Top partner lines use the same reported import-value measure.</p><p>${H.escape(count)} positive partner-product rows from ${H.escape(this.partnerTradeSource())} match this selection. ${H.escape(lens.caveat)}</p>`;
        return;
      }
      const labels = this.state.mode === "frus-activity" ? ["No linked record", "1", "2", "4+"] :
        this.state.mode === "historical-events" ? ["No episode", "1", "2", "3+"] :
          this.state.mode === "resource-geography" ? ["No association", "Profile context", "Year-linked", "Multiple links"] : ["No link", "1", "2", "4+"];
      $("atlasLegend").innerHTML = `<span class="atlas-legend-kicker">Evidence coverage · ${H.escape(this.state.year)}</span><strong>${H.escape(lens.title)}</strong><div class="atlas-scale">${labels.map((label, index) => `<span><i data-scale="${index}"></i>${H.escape(label)}</span>`).join("")}</div><p>${H.escape(lens.value_semantics)}</p>${this.state.layers.has("access-relationships") ? '<p><i class="line-key"></i> Access line width = linked pilot FRUS records, never trade volume.</p>' : ""}${this.state.layers.has("historical-events") ? '<p><i class="event-key"></i> Dashed rust boundary = linked active pilot episode.</p>' : ""}${this.state.layers.has("resource-geography") ? '<p><i class="resource-key">◆</i> C = profile context only; numbers = year-linked evidence connections. Neither measures production.</p>' : ""}`;
    }

    selectedCountry() {
      return this.state.country ? this.country(this.state.country) : null;
    }

    renderInspector() {
      const country = this.selectedCountry();
      if (!country) {
        if (this.state.mode === "quantitative-trade-flows") {
          const active = this.partnerTradeTotals("imports").size;
          $("mapInspector").innerHTML = `<div class="atlas-drawer-empty"><span class="atlas-folio">Selected geography</span><h3>Choose a reported partner</h3><p>At ${H.escape(this.state.year)}, ${H.escape(active)} partner geographies carry positive import-value evidence in the selected commodity headings.</p><p>Hover over a shaded country or line for its ${H.escape(this.partnerTradeSource())} value. A full History Stack opens only where the portal has a curated country record.</p><div class="atlas-drawer-key"><span><b>Fill</b> Reported import value</span><span><b>Line</b> Top partner values to the United States</span></div></div>`;
          return;
        }
        const active = this.data.countries.filter((row) => this.countryValue(row) > 0);
        $("mapInspector").innerHTML = `<div class="atlas-drawer-empty"><span class="atlas-folio">Selected geography</span><h3>Choose a country</h3><p>At ${H.escape(this.state.year)}, ${active.length} pilot geographies carry evidence in the selected lens.</p><p>Select a shaded country, documentary line, or square evidence marker to open its History Stack.</p><div class="atlas-drawer-key"><span><b>§</b> Agreement or instrument</span><span><b>A</b> NARA query plan</span><span><b>S</b> Stockpile policy</span><span><b>◆</b> Resource association</span></div></div>`;
        return;
      }
      const name = this.historicalName(country, this.state.year);
      const latestChange = (country.sovereignty_changes || []).filter((row) => row.year <= this.state.year).sort((a, b) => b.year - a.year)[0];
      const minerals = country.mineral_ids.map((id) => this.data.indexes.minerals.get(id)?.canonical_name || id);
      const frus = this.activeFrus(country);
      const instruments = this.activeInstruments(country.id);
      const archives = this.activeNara(country.id);
      const annual = this.annualSlice();
      const yearLinkedEvidence = annual?.country_evidence_counts[country.id] || 0;
      const profileContext = annual?.profile_context_country_ids.includes(country.id);
      $("mapInspector").innerHTML = `<div class="atlas-drawer-head"><span class="atlas-folio">${H.escape(this.state.year)} · country-level precision</span><button type="button" id="atlasCloseCountry" aria-label="Close selected country">×</button></div>
        <h3>${H.escape(name)}</h3>
        ${country.present_day_name !== name ? `<p class="present-name">Present-day reference: ${H.escape(country.present_day_name)}</p>` : ""}
        <div class="atlas-status-block"><strong>Political status in the pilot</strong><p>${H.escape(latestChange ? latestChange.note : "No dated sovereignty-change note is linked for this year.")}</p></div>
        <dl class="atlas-facts"><div><dt>Year-linked evidence</dt><dd>${H.escape(yearLinkedEvidence)}</dd></div><div><dt>FRUS in selected year</dt><dd>${frus.length}</dd></div><div><dt>Dated instruments</dt><dd>${instruments.length}</dd></div><div><dt>NARA query plans</dt><dd>${archives.length}</dd></div><div><dt>Profile context</dt><dd>${profileContext ? "Yes" : "No"}</dd></div><div><dt>Map precision</dt><dd>${H.escape(country.marker.precision)}</dd></div></dl>
        <div><strong>Linked materials</strong><div class="tag-row">${minerals.map((item) => H.badge(item, "neutral")).join("") || H.badge("Context entity", "neutral")}</div></div>
        <div class="atlas-outcome"><strong>What happened next?</strong><p>Outcome annotation has not yet been verified for this country-year view. This remains a visible research queue.</p></div>
        <p class="caveat">${H.escape(country.data_gaps[0] || "Coverage remains incomplete.")}</p>
        <a class="button-link" href="${H.detailHref("countries", country.id)}">Open country History Stack</a>`;
      $("atlasCloseCountry").addEventListener("click", () => this.setState({ country: null }));
    }

    renderTabs() {
      document.querySelectorAll("[data-atlas-tab]").forEach((button) => {
        const selected = button.dataset.atlasTab === this.state.tab;
        button.setAttribute("aria-selected", String(selected));
        button.tabIndex = selected ? 0 : -1;
      });
      const active = document.querySelector(`[data-atlas-tab="${this.state.tab}"]`);
      $("atlasPanel").setAttribute("aria-labelledby", active.id);
    }

    renderAnnualLedger() {
      const annual = this.annualSlice();
      const mineral = this.selectedMineral();
      if (!annual) {
        $("atlasYearLedger").innerHTML = '<p class="empty-note">The annual evidence ledger could not be loaded.</p>';
        return;
      }
      const counts = annual.counts;
      const statisticalRows = counts.official_statistics + counts.commodity_trade_rows + counts.broad_trade_context_rows;
      const policyRows = counts.dated_instruments + counts.laws_enacted + counts.stockpile_pathways;
      const kind = {
        "document-plus-context": "verified",
        "documentary-only": "source",
        "context-only": "discovery",
        sparse: "neutral"
      }[annual.coverage_status];
      const scope = mineral ? mineral.canonical_name : "All pilot materials";
      $("atlasYearLedger").innerHTML = `<div class="atlas-year-ledger-heading"><div><span class="atlas-folio">Annual evidence ledger</span><strong>${H.escape(this.state.year)} · ${H.escape(scope)}</strong></div>${H.badge(COVERAGE_LABELS[annual.coverage_status], kind)}</div>
        <div class="atlas-year-ledger-metrics">
          <span><strong>${H.escape(counts.frus_documents)}</strong> FRUS</span>
          <span><strong>${H.escape(counts.year_linked_geographies)}</strong> year-linked geographies</span>
          <span><strong>${H.escape(statisticalRows)}</strong> statistical/trade rows</span>
          <span><strong>${H.escape(policyRows)}</strong> policy records</span>
          <span><strong>${H.escape(counts.nara_query_plans)}</strong> NARA plans</span>
        </div>
        <p>Generated from checked-in evidence for this exact year and material selection. Profile context remains visible on the map but is not counted as year-specific evidence.</p>`;
    }

    renderSummaryPanel() {
      const country = this.selectedCountry();
      const activeEpisodes = country ? this.activeEvents(country.id) : this.atlas.events.filter((row) => row.start <= this.state.year && row.end >= this.state.year && this.mineralMatches(row.mineral_ids, true));
      const uniqueEpisodes = [...new Map(activeEpisodes.map((row) => [row.episode_id, row])).values()];
      const relationships = this.activeRelationships().filter((row) => !country || row.country_id === country.id);
      const title = country ? `${this.historicalName(country, this.state.year)} in ${this.state.year}` : `The atlas in ${this.state.year}`;
      const mineral = this.selectedMineral();
      const trade = this.data.trade.filter((row) => row.year_start <= this.state.year && row.year_end >= this.state.year && (!mineral || row.mineral_id === mineral.id));
      const tradeDetails = this.data["trade-details"].filter((row) => row.year === this.state.year && (!mineral || row.mineral_id === mineral.id));
      const dataWeb = this.activeDataWebTrade().filter((row) => !mineral || row.mineral_id === mineral.id);
      const comtrade = this.activeComtrade();
      const strategicComtrade = this.activeStrategicComtrade();
      const comtradeCount = comtrade.length + strategicComtrade.length;
      const annual = this.annualSlice();
      const counts = annual?.counts || {};
      const missing = (annual?.missing_lanes || []).map((id) => GAP_LABELS[id]);
      const tradePrompt = mineral && (trade.length || tradeDetails.length || dataWeb.length || comtradeCount) ? `<div class="atlas-evidence-prompt"><div><strong>Official trade evidence is available</strong><span>${trade.length} national observation${trade.length === 1 ? "" : "s"}${tradeDetails.length ? `, ${tradeDetails.length} published category row${tradeDetails.length === 1 ? "" : "s"}` : ""}${comtradeCount ? `, ${comtradeCount} Comtrade partner-product row${comtradeCount === 1 ? "" : "s"}` : ""}${dataWeb.length ? `, and ${dataWeb.length} DataWeb partner row${dataWeb.length === 1 ? "" : "s"}` : ""} match this selection.</span></div><button type="button" data-open-atlas-tab="trade">Open U.S. Trade</button></div>` : "";
      return `<div class="atlas-summary-grid"><div><p class="eyebrow">Annual evidence brief</p><h3>${H.escape(title)}</h3><p>${mineral ? `Material filter: <strong>${H.escape(mineral.canonical_name)}</strong>.` : "All pilot materials are visible."} FRUS remains the documentary spine; official statistics, policy records, and archival plans supply context without filling documentary gaps by inference.</p><div class="atlas-summary-metrics"><div><strong>${H.escape(counts.frus_documents || 0)}</strong><span>FRUS records</span></div><div><strong>${H.escape(counts.year_linked_geographies || 0)}</strong><span>year-linked geographies</span></div><div><strong>${H.escape((counts.official_statistics || 0) + (counts.commodity_trade_rows || 0))}</strong><span>exact-year data rows</span></div><div><strong>${H.escape((counts.dated_instruments || 0) + (counts.laws_enacted || 0) + (counts.stockpile_pathways || 0))}</strong><span>policy records</span></div></div>${tradePrompt}</div><div><h4>Historical record</h4>${uniqueEpisodes.length ? `<ol class="atlas-story-list">${uniqueEpisodes.map((row) => `<li><span>${row.start}–${row.end}</span><a href="${H.detailHref("episodes", row.episode_id)}">${H.escape(row.title)}</a>${H.completenessBadge(row.completeness)}</li>`).join("")}</ol>` : '<p class="empty-note">No pilot episode is linked to this exact selection. The absence reflects current coverage, not absence of historical activity.</p>'}<h4 class="atlas-gap-heading">Research needed</h4>${missing.length ? `<ul class="atlas-gap-list">${missing.map((item) => `<li>${H.escape(item)}</li>`).join("")}</ul>` : '<p class="coverage-complete-note">All five annual evidence lanes contain at least one checked-in record. Coverage is still selective rather than comprehensive.</p>'}</div></div>`;
    }

    renderFrusPanel() {
      const country = this.selectedCountry();
      const records = country ? this.activeFrus(country) : this.data["frus-documents"].filter((row) => row.volume_year_start <= this.state.year && row.volume_year_end >= this.state.year && this.mineralMatches(row.mineral_ids, false));
      return `<div class="atlas-panel-heading"><div><p class="eyebrow">FRUS narrative</p><h3>${H.escape(records.length)} linked pilot record${records.length === 1 ? "" : "s"} in ${H.escape(this.state.year)}</h3></div><p>Volume spans are discovery context when document-level dates have not been reviewed.</p></div><div class="atlas-card-grid">${records.slice(0, 4).map((row) => H.frusCard(row, true)).join("") || '<p class="empty-note">No linked pilot FRUS record matches this exact year, material, and country selection.</p>'}</div>`;
    }

    renderBroadTradePanel(records) {
      const valueOrder = ["exports", "imports"];
      const cards = valueOrder.flatMap((direction) => ["value", "share"].map((measure) => records.find((row) => row.direction === direction && row.metric.endsWith(measure)))).filter(Boolean);
      const period = records[0]?.year_label || String(this.state.year);
      return `<div class="atlas-panel-heading"><div><p class="eyebrow">Verified U.S. trade context</p><h3>Crude materials, ${H.escape(period)}</h3></div><p>The selected year falls within a published Census multi-year average. This broad economic class includes minerals and non-mineral raw materials.</p></div>
        <div class="trade-scope-note"><strong>Evidence boundary</strong><span>These are U.S. merchandise totals by economic class, not mineral-specific or bilateral trade. No annual value is inferred for ${H.escape(this.state.year)}.</span></div>
        <div class="atlas-number-grid trade-number-grid">${cards.map((row) => `<article><strong>${H.formatNumber(row.value)}</strong><span>${H.escape(row.metric)}</span><small>${H.escape(row.unit)}<br>${H.escape(row.trade_basis)}</small><a href="${H.escape(row.source_url)}" target="_blank" rel="noopener">Census ${H.escape(row.table_or_page)} ↗</a></article>`).join("")}</div>
        <div class="table-scroll trade-table"><table><caption>Published Census crude-material trade context covering ${H.escape(period)}</caption><thead><tr><th>Direction</th><th>Measure</th><th>Value</th><th>Unit</th><th>Time basis</th><th>Provenance</th></tr></thead><tbody>${cards.map((row) => `<tr><th scope="row">${H.escape(row.direction)}</th><td>${H.escape(row.metric.endsWith("share") ? "Share of total merchandise trade" : "Published yearly-average value")}</td><td>${H.formatNumber(row.value)}</td><td>${H.escape(row.unit)}</td><td>${H.escape(row.temporal_precision)} · ${H.escape(row.year_label)}</td><td><a href="${H.escape(row.source_url)}" target="_blank" rel="noopener">${H.escape(row.agency)}, ${H.escape(row.table_or_page)}</a></td></tr>`).join("")}</tbody></table></div>`;
    }

    renderCommodityTradePanel(records, allYearRecords) {
      const mineral = this.selectedMineral();
      const country = this.selectedCountry();
      const details = this.data["trade-details"].filter((row) => row.year === this.state.year && (!mineral || row.mineral_id === mineral.id));
      const research = this.data["trade-research"].filter((row) => row.year === this.state.year && (!mineral || row.mineral_id === mineral.id));
      const grouped = new Map();
      records.forEach((row) => {
        const group = grouped.get(row.mineral_id) || { mineral: this.data.indexes.minerals.get(row.mineral_id), imports: null, exports: null };
        group[row.direction] = row;
        grouped.set(row.mineral_id, group);
      });
      const groups = [...grouped.values()].sort((a, b) => (a.mineral?.canonical_name || "").localeCompare(b.mineral?.canonical_name || ""));
      const availableMaterials = new Set(allYearRecords.map((row) => row.mineral_id)).size;
      const selectionNote = country ? `Country selection does not filter these national totals; no partner-country flow is inferred for ${this.historicalName(country, this.state.year)}.` : "Partner countries are not identified in these national totals.";
      const emptyMessage = mineral
        ? `No annual USGS import or export row is normalized for ${mineral.canonical_name} in ${this.state.year}. ${availableMaterials} other pilot material series have exact-year trade evidence; choose All pilot materials to inspect them.`
        : `No annual USGS commodity trade row is normalized for ${this.state.year}. Missing values are not treated as zero.`;
      return `<div class="atlas-panel-heading"><div><p class="eyebrow">Verified U.S. commodity trade</p><h3>${mineral ? H.escape(mineral.canonical_name) : "Pilot strategic-resource materials"}, ${H.escape(this.state.year)}</h3></div><p>The long-run USGS rows are exact-year national imports and exports. UN Comtrade adds classification-bounded partner context from 1962; DataWeb remains the U.S.-reported verification layer for 1989–1992.</p></div>
        <div class="trade-scope-note"><strong>National aggregate</strong><span>${H.escape(selectionNote)}</span></div>
        ${this.renderComtradeRareEarthPanel()}
        ${this.renderComtradeStrategicPanel()}
        ${this.renderDataWebPartnerPanel()}
        ${this.renderTradeDetailPilot(details, research, records)}
        ${groups.length ? `<div class="table-scroll trade-table"><table><caption>Official U.S. mineral imports and exports for ${H.escape(this.state.year)}</caption><thead><tr><th>Material</th><th>Imports</th><th>Exports</th><th>Source definition</th><th>Provenance</th></tr></thead><tbody>${groups.map((group) => {
          const source = group.imports || group.exports;
          const valueCell = (row) => row ? `<strong>${H.formatNumber(row.value)}</strong><small>${H.escape(row.unit)}</small>` : '<span class="unknown-value">Not published</span>';
          return `<tr><th scope="row"><a href="${H.detailHref("minerals", group.mineral.id)}">${H.escape(group.mineral.canonical_name)}</a></th><td>${valueCell(group.imports)}</td><td>${valueCell(group.exports)}</td><td>${H.escape(source.trade_basis)}</td><td><a href="${H.escape(source.source_url)}" target="_blank" rel="noopener">USGS Data Series 140 · ${H.escape(source.table_or_page)}</a></td></tr>`;
        }).join("")}</tbody></table></div><p class="trade-source-note"><strong>Reading rule:</strong> A missing direction means no numeric cell was published in the normalized worksheet for that year; it does not mean zero trade.</p>` : `<p class="empty-note">${H.escape(emptyMessage)}</p>`}`;
    }

    renderComtradeRareEarthPanel() {
      if (this.state.mineral !== "rare-earth-elements" || this.state.year < 1962) return "";
      const rows = this.activeComtrade();
      const manifests = this.data["comtrade-query-manifest"].filter((row) => row.year === this.state.year);
      const classification = manifests[0]?.classification_code || (this.state.year <= 1975 ? "S1" : this.state.year <= 1987 ? "S2" : "S3");
      const classificationLabel = { S1: "SITC Revision 1", S2: "SITC Revision 2", S3: "SITC Revision 3" }[classification];
      if (!rows.length) {
        return `<section class="trade-pilot comtrade-continuity" aria-labelledby="comtrade-title"><div class="trade-pilot-heading"><div><p class="eyebrow">UN Comtrade · contextual continuity series</p><h4 id="comtrade-title">Rare-earth proxy trade, ${H.escape(this.state.year)}</h4></div>${H.badge("Tier 2 context", "discovery")}</div><p>The checked ${H.escape(classificationLabel)} reporter queries returned no matching row for this year. This is a visible coverage gap, not proof of zero trade.</p></section>`;
      }
      const familyLabels = {
        "metals-proxy": "Metals proxy",
        "compounds-proxy": "Compounds proxy",
        compounds: "Rare-earth compounds",
        "magnet-system-proxy": "Magnet-system proxy",
        "pyrophoric-alloy-proxy": "Pyrophoric-alloy proxy"
      };
      const value = (row) => row ? `$${H.formatNumber(row.primary_value)}` : "Not reported";
      const weight = (row) => row?.net_weight_kg == null ? "Weight not reported" : `${H.formatNumber(row.net_weight_kg)} kg net weight${row.net_weight_estimated ? " (estimated)" : ""}`;
      const families = [...new Set(rows.map((row) => row.product_family))];
      const mirror = families.map((family) => {
        const us = rows.find((row) => row.product_family === family && row.reporter_iso3 === "USA" && row.flow_code === "M" && row.partner_iso3 === "CHN");
        const china = rows.find((row) => row.product_family === family && row.reporter_iso3 === "CHN" && row.flow_code === "X" && row.partner_iso3 === "USA");
        if (!us && !china) return "";
        return `<article><div><span>${H.escape(familyLabels[family] || family)}</span>${H.badge((us || china).scope_confidence === "high" ? "Narrower scope" : "Broad proxy", (us || china).scope_confidence === "high" ? "verified" : "queue")}</div><dl><div><dt>U.S.-reported imports from China</dt><dd>${H.escape(value(us))}<small>${H.escape(weight(us))}</small></dd></div><div><dt>China-reported exports to the United States</dt><dd>${H.escape(value(china))}<small>${H.escape(weight(china))}</small></dd></div></dl><p>${H.escape((us || china).scope_caveat)}</p></article>`;
      }).filter(Boolean).join("");
      const tableRows = rows.map((row) => `<tr><th scope="row">${H.escape(familyLabels[row.product_family] || row.product_family)}</th><td>${H.escape(row.reporter_name)}</td><td>${H.escape(row.flow)}</td><td>${H.escape(row.partner_name)}</td><td>${H.escape(row.classification_code)} ${H.escape(row.commodity_code)}<small>${H.escape(row.commodity_description)}</small></td><td>$${H.escape(H.formatNumber(row.primary_value))}<small>${H.escape(row.valuation_basis)}</small></td><td>${row.net_weight_kg == null ? '<span class="unknown-value">Not reported</span>' : `${H.escape(H.formatNumber(row.net_weight_kg))} kg${row.net_weight_estimated ? " <small>estimated</small>" : ""}`}</td><td>${row.is_original_classification ? H.badge("As reported", "verified") : H.badge("Converted classification", "queue")}</td></tr>`).join("");
      return `<section class="trade-pilot comtrade-continuity" aria-labelledby="comtrade-title"><div class="trade-pilot-heading"><div><p class="eyebrow">UN Comtrade · contextual continuity series</p><h4 id="comtrade-title">Rare-earth proxy trade, ${H.escape(this.state.year)}</h4></div>${H.badge("Tier 2 context", "discovery")}</div>
        <p>FRUS remains the documentary spine. Comtrade extends the measurable reporter-partner setting back toward 1962; USITC DataWeb remains the authoritative U.S.-reported verification layer for 1989–1992.</p>
        <div class="trade-scope-note caution"><strong>Classification boundary</strong><span>${H.escape(classificationLabel)} is displayed as its own vintage. Broad proxy families are not summed, spliced to another revision, or treated as a stable definition of rare-earth trade.</span></div>
        ${mirror ? `<div class="comtrade-mirror-heading"><strong>Reporter mirror comparison</strong><span>Mirror values are parallel reports, not duplicates. Import and export valuation, timing, routing, and origin rules differ.</span></div><div class="comtrade-mirror-grid">${mirror}</div>` : '<p class="empty-note">No bilateral U.S.–China mirror pair is available for this year. World and one-sided reporter records remain below.</p>'}
        <div class="table-scroll trade-detail-table"><table><caption>UN Comtrade ${H.escape(classificationLabel)} records for ${H.escape(this.state.year)}; product families remain separate</caption><thead><tr><th>Product family</th><th>Reporter</th><th>Flow</th><th>Partner</th><th>Classification and commodity</th><th>Current value</th><th>Net weight</th><th>Classification status</th></tr></thead><tbody>${tableRows}</tbody></table></div>
        <p class="trade-source-note"><strong>Provenance:</strong> United Nations Statistics Division, UN Comtrade public annual preview API, accessed July 10, 2026. The checked-in manifest retains each reporter-year query URL, code basket, result count, and query hash.</p></section>`;
    }

    renderComtradeStrategicPanel() {
      if (this.state.year < 1962 || this.state.mineral === "rare-earth-elements") return "";
      const country = this.selectedCountry();
      const atlasCountry = country ? this.atlasCountry(country.id) : null;
      const allRows = this.activeStrategicComtrade();
      const rows = atlasCountry ? allRows.filter((row) => row.partner_iso3 === atlasCountry.a3) : allRows;
      const manifest = this.data["comtrade-strategic-query-manifest"].find((row) => row.year === this.state.year);
      const classification = manifest?.classification_code || (this.state.year <= 1975 ? "S1" : this.state.year <= 1987 ? "S2" : "S3");
      const classificationLabel = { S1: "SITC Revision 1", S2: "SITC Revision 2", S3: "SITC Revision 3" }[classification];
      const mineral = this.selectedMineral();
      const scope = country ? `${this.historicalName(country, this.state.year)} and the United States` : mineral ? mineral.canonical_name : "pilot strategic materials";
      if (!rows.length) {
        return `<section class="trade-pilot comtrade-continuity" aria-labelledby="comtrade-strategic-title"><div class="trade-pilot-heading"><div><p class="eyebrow">UN Comtrade · official international context</p><h4 id="comtrade-strategic-title">Reported partner trade, ${H.escape(this.state.year)}</h4></div>${H.badge("Tier 2 context", "discovery")}</div><p>The checked ${H.escape(classificationLabel)} query returned no matching U.S.-reported row for ${H.escape(scope)}. This is a visible coverage gap, not proof of zero trade.</p></section>`;
      }
      const partnerTotals = new Map();
      rows.filter((row) => row.flow_code === "M" && row.partner_iso3).forEach((row) => {
        const current = partnerTotals.get(row.partner_iso3) || { name: row.partner_name, value: 0, codes: new Set() };
        current.value += row.primary_value || 0;
        current.codes.add(row.commodity_code);
        partnerTotals.set(row.partner_iso3, current);
      });
      const topPartners = [...partnerTotals.values()].sort((a, b) => b.value - a.value).slice(0, 4);
      const topRows = [...rows].sort((a, b) => b.primary_value - a.primary_value).slice(0, 40);
      const tableRows = topRows.map((row) => {
        const material = this.data.indexes.minerals.get(row.mineral_id)?.canonical_name || row.mineral_id;
        const confidenceKind = row.scope_confidence === "high" ? "verified" : row.scope_confidence === "medium" ? "discovery" : "queue";
        const weight = row.net_weight_kg == null ? '<span class="unknown-value">Not reported</span>' : `${H.escape(H.formatNumber(row.net_weight_kg))} kg${row.net_weight_estimated ? " <small>estimated</small>" : ""}`;
        return `<tr>${mineral ? "" : `<th scope="row">${H.escape(material)}</th>`}<td>${H.escape(row.flow)}</td><td>${H.escape(row.partner_name)}</td><td>${H.escape(row.classification_code)} ${H.escape(row.commodity_code)}<small>${H.escape(row.supply_chain_stage.replaceAll("-", " "))} · ${H.escape(row.commodity_description)}</small></td><td>$${H.escape(H.formatNumber(row.primary_value))}<small>${H.escape(row.valuation_basis)}</small></td><td>${weight}</td><td>${H.badge(`${row.scope_confidence} scope`, confidenceKind)}<small>${H.escape(row.scope_caveat)}</small></td></tr>`;
      }).join("");
      return `<section class="trade-pilot comtrade-continuity" aria-labelledby="comtrade-strategic-title"><div class="trade-pilot-heading"><div><p class="eyebrow">UN Comtrade · official international context</p><h4 id="comtrade-strategic-title">Reported partner trade, ${H.escape(this.state.year)}</h4></div>${H.badge("Tier 2 context", "discovery")}</div>
        <p>FRUS remains the documentary spine. These are U.S.-reported merchandise values for selected upstream and primary-material headings, not proof of mine origin, dependence, strategic importance, or contained-mineral quantity.</p>
        <div class="trade-scope-note caution"><strong>Classification boundary</strong><span>${H.escape(classificationLabel)} is displayed as its own statistical vintage. Ores, compounds, ferroalloys, intermediates, unwrought metals, alloys, waste, and articles remain separately labeled.</span></div>
        ${topPartners.length ? `<div class="atlas-number-grid trade-number-grid">${topPartners.map((row) => `<article><strong>$${H.escape(H.formatNumber(row.value))}</strong><span>${H.escape(row.name)}</span><small>U.S.-reported imports · ${H.escape(row.codes.size)} selected heading${row.codes.size === 1 ? "" : "s"}</small></article>`).join("")}</div>` : '<p class="empty-note">Only world-total or export rows are available for this selection; no partner ranking is inferred.</p>'}
        <div class="trade-map-action"><span>${H.escape(rows.length)} positive Comtrade partner-product record${rows.length === 1 ? "" : "s"} match ${H.escape(scope)}.</span><button type="button" data-enable-dataweb-map>Map reported import value</button></div>
        <details class="trade-detail-disclosure"><summary>Open ${H.escape(rows.length)} Comtrade partner-product rows</summary><div class="table-scroll trade-detail-table"><table><caption>Largest ${H.escape(classificationLabel)} rows for ${H.escape(scope)} in ${H.escape(this.state.year)}</caption><thead><tr>${mineral ? "" : "<th>Material</th>"}<th>Flow</th><th>Partner</th><th>Classification, stage, and commodity</th><th>Current value</th><th>Net weight</th><th>Scope</th></tr></thead><tbody>${tableRows}</tbody></table></div></details>
        <p class="trade-source-note"><strong>Provenance:</strong> United Nations Statistics Division, <a href="https://comtradeplus.un.org/" target="_blank" rel="noopener">UN Comtrade</a> public annual API, accessed July 10, 2026. The <a href="https://www.unccd.int/resources/knowledge-sharing-system/united-nations-commodity-trade-statistics-database-un-comtrade" target="_blank" rel="noopener">UNCCD Knowledge Hub entry</a> is retained as a discovery pointer, not the statistical publisher.</p></section>`;
    }

    renderDataWebPartnerPanel() {
      if (this.state.year < 1989 || this.state.year > 1992) return "";
      const mineral = this.selectedMineral();
      const country = this.selectedCountry();
      const atlasCountry = country ? this.atlasCountry(country.id) : null;
      const allRows = this.activeDataWebTrade();
      const rows = atlasCountry ? allRows.filter((row) => row.partner_iso3 === atlasCountry.a3) : allRows;
      const directions = ["imports", "exports"].map((direction) => {
        const matches = rows.filter((row) => row.direction === direction);
        return {
          direction,
          rows: matches.length,
          value: matches.reduce((sum, row) => sum + (row.trade_value.value || 0), 0),
          partners: new Set(matches.map((row) => row.partner_iso3)).size,
          codes: new Set(matches.map((row) => row.commodity_code)).size
        };
      });
      const scope = country ? `${this.historicalName(country, this.state.year)} and the United States` : mineral ? mineral.canonical_name : "the selected strategic-resource headings";
      if (!rows.length) {
        return `<section class="trade-pilot dataweb-trade" aria-labelledby="dataweb-trade-title"><div class="trade-pilot-heading"><div><p class="eyebrow">USITC DataWeb / Census</p><h4 id="dataweb-trade-title">Partner-country trade, ${H.escape(this.state.year)}</h4></div>${H.badge("Official statistics", "source")}</div><p>No positive DataWeb value or first-quantity row matches ${H.escape(scope)} in the checked six-digit headings. This does not prove that no trade occurred.</p></section>`;
      }
      const topRows = [...rows].sort((a, b) => (b.trade_value.value || 0) - (a.trade_value.value || 0)).slice(0, 30);
      const measurement = (row) => row.value == null ? '<span class="unknown-value">Not reported</span>' : `${H.escape(row.display)} <small>${H.escape(row.unit)}</small>`;
      return `<section class="trade-pilot dataweb-trade" aria-labelledby="dataweb-trade-title"><div class="trade-pilot-heading"><div><p class="eyebrow">USITC DataWeb / Census · official statistical context</p><h4 id="dataweb-trade-title">Partner-country trade, ${H.escape(this.state.year)}</h4></div>${H.badge("1989-1992 series", "verified")}</div>
        <p>FRUS remains the documentary spine. These official merchandise statistics show part of the measurable trade environment around the record.</p>
        <div class="atlas-number-grid trade-number-grid">${directions.map((row) => `<article><strong>${H.escape(H.formatNumber(row.value))}</strong><span>${H.escape(row.direction === "imports" ? "Import customs value" : "Export F.A.S. value")}</span><small>${H.escape(row.partners)} partner${row.partners === 1 ? "" : "s"} · ${H.escape(row.codes)} HS6 heading${row.codes === 1 ? "" : "s"}</small><a href="https://dataweb.usitc.gov/" target="_blank" rel="noopener">Open USITC DataWeb ↗</a></article>`).join("")}</div>
        <div class="trade-scope-note caution"><strong>How to read this layer</strong><span>Values are sums of the selected six-digit headings, not a complete mineral-trade total or an import-dependence measure. Country means reported origin for imports and destination for exports. It does not establish mine origin, ownership, route, end use, or strategic importance.</span></div>
        <div class="trade-map-action"><span>${H.escape(rows.length)} positive partner-product record${rows.length === 1 ? "" : "s"} match ${H.escape(scope)}.</span><button type="button" data-enable-dataweb-map>Map reported import value</button></div>
        <div class="table-scroll trade-detail-table"><table><caption>Largest reported partner-product values for ${H.escape(scope)} in ${H.escape(this.state.year)}</caption><thead><tr><th>Flow</th><th>Partner</th>${mineral ? "" : "<th>Material</th>"}<th>HS6</th><th>Historical commodity description</th><th>Value</th><th>First quantity</th></tr></thead><tbody>${topRows.map((row) => `<tr><th scope="row">${H.escape(row.trade_flow)}</th><td>${H.escape(row.source_partner_name)}</td>${mineral ? "" : `<td>${H.escape(this.data.indexes.minerals.get(row.mineral_id)?.canonical_name || row.mineral_id)}</td>`}<td>${H.escape(row.commodity_code)}</td><td>${H.escape(row.commodity_description)}<small>Research scope: ${H.escape(row.commodity_scope_note)}</small></td><td>${measurement(row.trade_value)}<small>${H.escape(row.trade_value.valuation_basis)}</small></td><td>${measurement(row.quantity)}</td></tr>`).join("")}</tbody></table></div>
        <p class="trade-source-note"><strong>Provenance:</strong> Compiled using USITC DataWeb from official U.S. merchandise trade statistics published by the U.S. Department of Commerce, Census Bureau; accessed July 10, 2026. The checked-in query manifest records years, headings, filters, and a payload hash.</p></section>`;
    }

    renderTradeDetailPilot(details, research, aggregateRecords) {
      if (!details.length && !research.length) return "";
      const pilotYear = details[0]?.year || research[0]?.year || this.state.year;
      const totals = new Map(details.filter((row) => row.is_total).map((row) => [row.direction, row]));
      const aggregates = new Map(aggregateRecords.map((row) => [row.direction, row]));
      const thorium = details.find((row) => row.direction === "exports" && row.category === "Thorium ore and concentrates");
      const measurement = (item) => item && item.display ? `${H.escape(item.display)} <small>${H.escape(item.unit)}</small>` : '<span class="unknown-value">Not published</span>';
      const comparison = ["imports", "exports"].map((direction) => {
        const total = totals.get(direction);
        const aggregate = aggregates.get(direction);
        if (!total && !aggregate) return "";
        return `<div><span>${H.escape(direction)}</span><strong>${total ? measurement(total.quantity) : '<span class="unknown-value">Not available</span>'}</strong><small>Census-derived contemporaneous categories</small>${aggregate ? `<strong>${H.formatNumber(aggregate.value)} <small>${H.escape(aggregate.unit)}</small></strong><small>Later USGS standardized series</small>` : ""}</div>`;
      }).join("");
      const rows = details.map((row) => `<tr${row.is_total ? ' class="is-total"' : ""}><th scope="row">${H.escape(row.direction)}</th><td>${H.escape(row.category)}</td><td>${measurement(row.quantity)}</td><td>${measurement(row.trade_value)}</td><td><a href="${H.escape(row.source_url)}" target="_blank" rel="noopener">${H.escape(row.table_or_page)}</a></td></tr>`).join("");
      const queues = research.map((queue) => `<div class="trade-acquisition"><div><span class="badge badge-queue">Source acquisition</span><h4>${H.escape(queue.title)}</h4><p>${H.escape(queue.objective)}</p></div><div class="trade-report-list">${queue.reports.map((report) => `<div><strong>${H.escape(report.series)}</strong><span>${H.escape(report.title)}</span><small>${H.escape(report.role)}</small><a href="${H.escape(report.official_description_url)}" target="_blank" rel="noopener">Official Census description ↗</a></div>`).join("")}</div><ul>${queue.classification_notes.map((note) => `<li>${H.escape(note)}</li>`).join("")}</ul><a class="button-link" href="${H.escape(queue.official_request_url)}" target="_blank" rel="noopener">Find or request the legacy Census reports ↗</a></div>`).join("");
      const thoriumBoundary = thorium?.quantity?.value != null ? `The published ${pilotYear} export total includes ${thorium.quantity.display} metric tons of thorium ore and concentrates.` : `The ${pilotYear} export table lists thorium ore and concentrates as ${thorium?.quantity?.display || "not available"}.`;
      const htsBoundary = pilotYear >= 1989 ? " The source warns that 1989 and 1990 categories are not necessarily comparable with previous years after implementation of the Harmonized Tariff System." : "";
      return `<section class="trade-pilot" aria-labelledby="trade-pilot-title"><div class="trade-pilot-heading"><div><p class="eyebrow">${H.escape(pilotYear)} Census recovery pilot</p><h4 id="trade-pilot-title">Rare-earth trade before a stable modern category</h4></div>${H.badge("Reviewed official table", "verified")}</div><p>The contemporaneous tables and the later standardized series answer different questions. They are displayed side by side and are not merged.</p><div class="trade-comparison">${comparison}</div><div class="trade-scope-note caution"><strong>Classification boundary</strong><span>${H.escape(thoriumBoundary)} Data Series 140 reports rare-earth-oxide equivalent. Neither total can validate country rows from FT 246 or FT 446 until those reports are reviewed in their original classifications.${H.escape(htsBoundary)}</span></div>${rows ? `<div class="table-scroll trade-detail-table"><table><caption>Published ${H.escape(pilotYear)} rare-earth categories reproduced from Census-derived USGS Statistical Compendium tables</caption><thead><tr><th>Flow</th><th>Published category</th><th>Quantity</th><th>Trade value</th><th>Official table</th></tr></thead><tbody>${rows}</tbody></table></div><p class="trade-source-note"><strong>Published symbols:</strong> “Not available,” “published dash,” and “less than 0.5” are retained as distinct source states. None is converted to zero.</p>` : ""}${queues}</section>`;
    }

    renderTradePanel() {
      const active = this.data.trade.filter((row) => row.year_start <= this.state.year && row.year_end >= this.state.year);
      const broad = active.filter((row) => row.material_scope === "broad-economic-class");
      const annual = active.filter((row) => row.temporal_precision === "annual");
      const mineral = this.selectedMineral();
      const filteredAnnual = mineral ? annual.filter((row) => row.mineral_id === mineral.id) : annual;
      if (this.state.year < 1900) return this.renderBroadTradePanel(broad);
      return this.renderCommodityTradePanel(filteredAnnual, annual);
    }

    renderNumbersPanel() {
      const mineral = this.selectedMineral();
      if (!mineral) return '<p class="empty-note">Select a material to inspect exact-year official statistics.</p>';
      const records = this.data.statistics.filter((row) => row.mineral_id === mineral.id && row.year === this.state.year && ["united-states", null].includes(row.country_id));
      const priority = ["U.S. primary production", "U.S. mine production", "U.S. production", "U.S. imports", "U.S. exports", "U.S. apparent consumption", "U.S. Government stocks", "U.S. stocks", "World mine production", "World production", "Unit value", "Real unit value"];
      const selected = priority.map((metric) => records.find((row) => row.metric === metric)).filter(Boolean);
      const ds140Materials = new Set(["aluminum", "bauxite", "chromium", "cobalt", "copper", "manganese", "rare-earth-elements", "tin", "tungsten"]);
      const annualNote = ds140Materials.has(mineral.id)
        ? "Every numeric annual cell in the linked USGS worksheet is indexed through 1992."
        : "This material does not yet have a normalized Data Series 140 worksheet in the atlas.";
      return `<div class="atlas-panel-heading"><div><p class="eyebrow">Official statistical context</p><h3>${H.escape(mineral.canonical_name)}, ${H.escape(this.state.year)}</h3></div><p>Exact-year U.S. and world series only. No interpolation and no country supplier shares. ${H.escape(annualNote)}</p></div>${selected.length ? `<div class="atlas-number-grid atlas-number-grid-complete">${selected.map((row) => `<article><strong>${H.formatNumber(row.value)}</strong><span>${H.escape(row.metric)}</span><small>${H.escape(row.unit)}</small><small>${H.escape(row.table_or_page)}</small><a href="${H.escape(row.source_url)}" target="_blank" rel="noopener">USGS table source ↗</a></article>`).join("")}</div>` : `<p class="empty-note">No numeric USGS observation is checked in for ${H.escape(mineral.canonical_name)} in ${H.escape(this.state.year)}. Missing, withheld, and nonnumeric source cells are not interpolated or treated as zero.</p>`}`;
    }

    renderInstrumentPanel() {
      const country = this.selectedCountry();
      const records = this.atlas.instruments.filter((row) => row.year === this.state.year && (!country || row.country_id === country.id) && this.mineralMatches(row.mineral_ids, true));
      return `<div class="atlas-panel-heading"><div><p class="eyebrow">Treaties and policy instruments</p><h3>${H.escape(records.length)} dated pilot record${records.length === 1 ? "" : "s"}</h3></div><p>Date precision remains visible; many records are negotiation pathways rather than formal treaties.</p></div><div class="atlas-card-grid">${records.map((row) => {
        const agreement = this.data.indexes.agreements.get(row.agreement_id);
        return `<article class="atlas-evidence-card"><div>${H.badge(agreement.record_type.replaceAll("-", " "), "concept")} ${H.completenessBadge(agreement.completeness)}</div><h4><a href="${H.detailHref("agreements", agreement.id)}">${H.escape(agreement.official_title)}</a></h4><p>${H.escape(agreement.summary)}</p><small>${H.escape(row.year)} · ${H.escape(row.date_precision.replaceAll("-", " "))}</small></article>`;
      }).join("") || '<p class="empty-note">No pilot instrument is dated to this exact selection.</p>'}</div>`;
    }

    renderArchivesPanel() {
      const country = this.selectedCountry();
      const records = this.atlas.archival_plans.filter((row) => row.start <= this.state.year && row.end >= this.state.year && (!country || row.country_ids.includes(country.id)) && this.mineralMatches(row.mineral_ids, true));
      return `<div class="atlas-panel-heading"><div><p class="eyebrow">NARA archival discovery</p><h3>${H.escape(records.length)} structured query plan${records.length === 1 ? "" : "s"}</h3></div><p>These are discovery plans, not reviewed Catalog results. In-page API responses are never stored.</p></div><div class="atlas-card-grid">${records.slice(0, 8).map((row) => `<article class="atlas-evidence-card"><div>${H.badge("NARA query plan", "discovery")}</div><h4>${H.escape(row.title)}</h4><p>RG ${H.escape(row.record_groups.join(", "))} · ${row.start}–${row.end}</p><a href="${H.escape(catalogUrl(row.query))}" target="_blank" rel="noopener">Search official Catalog ↗</a></article>`).join("") || '<p class="empty-note">No structured NARA query plan matches this exact selection.</p>'}</div>`;
    }

    renderPanel() {
      const renderers = {
        summary: () => this.renderSummaryPanel(),
        frus: () => this.renderFrusPanel(),
        trade: () => this.renderTradePanel(),
        numbers: () => this.renderNumbersPanel(),
        instruments: () => this.renderInstrumentPanel(),
        archives: () => this.renderArchivesPanel()
      };
      $("atlasPanel").innerHTML = renderers[this.state.tab]();
      $("atlasPanel").querySelectorAll("[data-open-atlas-tab]").forEach((button) => button.addEventListener("click", () => {
        const target = document.querySelector(`[data-atlas-tab="${button.dataset.openAtlasTab}"]`);
        if (target) target.click();
      }));
      $("atlasPanel").querySelectorAll("[data-enable-dataweb-map]").forEach((button) => button.addEventListener("click", () => {
        const layers = new Set(this.state.layers);
        layers.add("quantitative-trade-flows");
        this.setState({ mode: "quantitative-trade-flows", layers });
        this.renderLayerControls();
      }));
    }

    renderTable() {
      const headerCells = [...document.querySelectorAll(".atlas-accessible-table thead th")];
      const tableNote = document.querySelector(".atlas-accessible-table > p");
      if (this.state.mode === "quantitative-trade-flows") {
        const headers = ["Reported partner", "ISO3", "Reported import value", "Selected commodity scope", "Source", "Precision"];
        headerCells.forEach((cell, index) => { cell.textContent = headers[index]; });
        if (tableNote) tableNote.textContent = "This table reproduces the selected-year reported-import layer without requiring the map. Values cover only the selected commodity headings and do not measure production, mine origin, import dependence, or strategic weight.";
        const atlasByA3 = new Map(this.atlas.countries.map((row) => [row.a3, row.id]));
        const totals = [...this.partnerTradeTotals("imports").values()].sort((a, b) => b.value - a.value);
        $("mapTableBody").innerHTML = totals.map((row) => {
          const atlasId = atlasByA3.get(row.iso3);
          const name = atlasId ? `<button class="table-country-button" type="button" data-table-country="${H.escape(atlasId)}">${H.escape(row.name)}</button>` : H.escape(row.name);
          return `<tr><td>${name}</td><td>${H.escape(row.iso3)}</td><td>${H.escape(H.formatNumber(row.value))} current U.S. dollars</td><td>${H.escape(row.codes.size)} ${H.escape(row.commodity_label)}${row.codes.size === 1 ? "" : "s"}</td><td>${H.escape(row.source_name)}</td><td>country-level generalized geometry</td></tr>`;
        }).join("");
        $("mapTableBody").querySelectorAll("[data-table-country]").forEach((button) => button.addEventListener("click", () => this.selectCountry(button.dataset.tableCountry)));
        return;
      }
      const headers = ["Country or territory", "Historical name", "Selected-year evidence", "Linked materials", "FRUS records", "Precision"];
      headerCells.forEach((cell, index) => { cell.textContent = headers[index]; });
      if (tableNote) tableNote.textContent = "The table presents the same selected-year evidence without requiring the map. Counts are documentary coverage, not production or strategic weight.";
      const countries = this.data.countries.filter((row) => this.countryExists(row) && (this.state.mineral === "all" || row.mineral_ids.includes(this.state.mineral)));
      $("mapTableBody").innerHTML = countries.map((country) => {
        const frus = this.activeFrus(country);
        const events = this.activeEvents(country.id);
        const instruments = this.activeInstruments(country.id);
        const archives = this.activeNara(country.id);
        const evidence = [`${frus.length} FRUS`, `${events.length} episodes`, `${instruments.length} instruments`, `${archives.length} NARA plans`].join(" · ");
        const minerals = country.mineral_ids.map((id) => this.data.indexes.minerals.get(id)?.canonical_name || id);
        return `<tr><td><button class="table-country-button" type="button" data-table-country="${H.escape(country.id)}">${H.escape(country.canonical_historical_name)}</button></td><td>${H.escape(this.historicalName(country, this.state.year))}</td><td>${H.escape(evidence)}</td><td>${H.escape(minerals.join(", ") || "Context only")}</td><td>${frus.length}</td><td>${H.escape(country.marker.precision)}</td></tr>`;
      }).join("");
      $("mapTableBody").querySelectorAll("[data-table-country]").forEach((button) => button.addEventListener("click", () => this.selectCountry(button.dataset.tableCountry)));
    }

    renderStatus() {
      const activeCountries = this.state.mode === "quantitative-trade-flows" ? this.partnerTradeTotals("imports").size : this.data.countries.filter((row) => this.countryValue(row) > 0).length;
      const relationships = this.activeRelationships().length;
      const mineral = this.selectedMineral();
      const annual = this.annualSlice();
      $("atlasMapStatus").innerHTML = `<strong>${H.escape(this.state.year)} · ${H.escape(mineral ? mineral.canonical_name : "All pilot materials")}</strong><span>${H.escape(activeCountries)} geographies in this lens · ${H.escape(annual?.counts.year_linked_geographies || 0)} with year-linked evidence · ${H.escape(relationships)} documented access links</span>`;
    }

    renderAll() {
      $("mapYear").value = this.state.year;
      $("mapYearValue").textContent = this.state.year;
      $("mapMineral").value = this.state.mineral;
      $("atlasMode").value = this.state.mode;
      this.renderAnnualLedger();
      this.renderLegend();
      this.renderInspector();
      this.renderTabs();
      this.renderPanel();
      this.renderTable();
      this.renderStatus();
      this.renderMap();
    }
  }

  window.HistoricalAtlas = {
    init(options) {
      const atlas = new HistoricalAtlas(options);
      return atlas.init();
    }
  };
})();
