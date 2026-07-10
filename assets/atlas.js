(function () {
  "use strict";

  const H = window.HistoryData;
  const $ = (id) => document.getElementById(id);
  const EMPTY_COLLECTION = { type: "FeatureCollection", features: [] };
  const LENS_IDS = ["frus-activity", "resource-geography", "historical-events"];
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
    }

    async init() {
      this.renderControls();
      this.bindControls();
      this.renderLayerControls();
      this.renderLayerTable();
      this.renderAll();
      await this.initMap();
      this.renderAll();
      return this;
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

    countryValue(country) {
      if (!this.countryExists(country) || !this.state.layers.has(this.state.mode)) return 0;
      if (this.state.mode === "frus-activity") return this.activeFrus(country).length;
      if (this.state.mode === "historical-events") return this.activeEvents(country.id).length;
      if (this.state.mode === "resource-geography") {
        if (this.state.mineral !== "all") return country.mineral_ids.includes(this.state.mineral) ? 1 : 0;
        return country.mineral_ids.length;
      }
      return 0;
    }

    selectedMineral() {
      return this.state.mineral === "all" ? null : this.data.indexes.minerals.get(this.state.mineral);
    }

    setState(patch, notify) {
      Object.assign(this.state, patch);
      this.renderAll();
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
      $("atlasLayerControls").innerHTML = `<div class="atlas-layer-group"><strong>Documentary layers</strong>${supported.map(rowHtml).join("")}</div>
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
        ["atlas-relationship-halo", "line-color", colors.halo]
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
          const count = this.state.mineral === "all" ? country.mineral_ids.length : 1;
          this.addMarker(id, "resource-geography", count, `${count} country-level material association${count === 1 ? "" : "s"}; not production`, [0, -30]);
        }
      });
    }

    renderLegend() {
      const lens = this.layer(this.state.mode);
      const labels = this.state.mode === "frus-activity" ? ["No linked record", "1", "2", "4+"] :
        this.state.mode === "historical-events" ? ["No episode", "1", "2", "3+"] : ["No link", "1", "2", "4+"];
      $("atlasLegend").innerHTML = `<span class="atlas-legend-kicker">Evidence coverage · ${H.escape(this.state.year)}</span><strong>${H.escape(lens.title)}</strong><div class="atlas-scale">${labels.map((label, index) => `<span><i data-scale="${index}"></i>${H.escape(label)}</span>`).join("")}</div><p>${H.escape(lens.value_semantics)}</p>${this.state.layers.has("access-relationships") ? '<p><i class="line-key"></i> Access line width = linked pilot FRUS records, never trade volume.</p>' : ""}${this.state.layers.has("historical-events") ? '<p><i class="event-key"></i> Dashed rust boundary = linked active pilot episode.</p>' : ""}${this.state.layers.has("resource-geography") ? '<p><i class="resource-key">◆</i> Country-level material association, not production.</p>' : ""}`;
    }

    selectedCountry() {
      return this.state.country ? this.country(this.state.country) : null;
    }

    renderInspector() {
      const country = this.selectedCountry();
      if (!country) {
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
      $("mapInspector").innerHTML = `<div class="atlas-drawer-head"><span class="atlas-folio">${H.escape(this.state.year)} · country-level precision</span><button type="button" id="atlasCloseCountry" aria-label="Close selected country">×</button></div>
        <h3>${H.escape(name)}</h3>
        ${country.present_day_name !== name ? `<p class="present-name">Present-day reference: ${H.escape(country.present_day_name)}</p>` : ""}
        <div class="atlas-status-block"><strong>Political status in the pilot</strong><p>${H.escape(latestChange ? latestChange.note : "No dated sovereignty-change note is linked for this year.")}</p></div>
        <dl class="atlas-facts"><div><dt>FRUS in selected year</dt><dd>${frus.length}</dd></div><div><dt>Dated instruments</dt><dd>${instruments.length}</dd></div><div><dt>NARA query plans</dt><dd>${archives.length}</dd></div><div><dt>Map precision</dt><dd>${H.escape(country.marker.precision)}</dd></div></dl>
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

    renderSummaryPanel() {
      const country = this.selectedCountry();
      const activeEpisodes = country ? this.activeEvents(country.id) : this.atlas.events.filter((row) => row.start <= this.state.year && row.end >= this.state.year && this.mineralMatches(row.mineral_ids, true));
      const uniqueEpisodes = [...new Map(activeEpisodes.map((row) => [row.episode_id, row])).values()];
      const relationships = this.activeRelationships().filter((row) => !country || row.country_id === country.id);
      const title = country ? `${this.historicalName(country, this.state.year)} in ${this.state.year}` : `The atlas in ${this.state.year}`;
      const mineral = this.selectedMineral();
      const trade = this.data.trade.filter((row) => row.year_start <= this.state.year && row.year_end >= this.state.year && (!mineral || row.mineral_id === mineral.id));
      const tradeDetails = this.data["trade-details"].filter((row) => row.year === this.state.year && (!mineral || row.mineral_id === mineral.id));
      const tradePrompt = mineral && (trade.length || tradeDetails.length) ? `<div class="atlas-evidence-prompt"><div><strong>Official trade evidence is available</strong><span>${trade.length} national observation${trade.length === 1 ? "" : "s"}${tradeDetails.length ? ` and ${tradeDetails.length} published category row${tradeDetails.length === 1 ? "" : "s"}` : ""} match this selection.</span></div><button type="button" data-open-atlas-tab="trade">Open U.S. Trade</button></div>` : "";
      return `<div class="atlas-summary-grid"><div><p class="eyebrow">Synchronized view</p><h3>${H.escape(title)}</h3><p>${mineral ? `Material filter: <strong>${H.escape(mineral.canonical_name)}</strong>.` : "All pilot materials are visible."} Each count reflects checked-in evidence, not total historical activity.</p><div class="atlas-summary-metrics"><div><strong>${uniqueEpisodes.length}</strong><span>active pilot episodes</span></div><div><strong>${relationships.length}</strong><span>documented access links</span></div><div><strong>${country ? this.activeFrus(country).length : this.data.countries.reduce((sum, row) => sum + this.activeFrus(row).length, 0)}</strong><span>linked FRUS records</span></div><div><strong>${trade.length + tradeDetails.length}</strong><span>trade evidence rows</span></div></div>${tradePrompt}</div><div><h4>What happened here?</h4>${uniqueEpisodes.length ? `<ol class="atlas-story-list">${uniqueEpisodes.map((row) => `<li><span>${row.start}–${row.end}</span><a href="${H.detailHref("episodes", row.episode_id)}">${H.escape(row.title)}</a>${H.completenessBadge(row.completeness)}</li>`).join("")}</ol>` : '<p class="empty-note">No pilot episode is linked to this exact selection. The absence reflects current coverage, not absence of historical activity.</p>'}</div></div>`;
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
      return `<div class="atlas-panel-heading"><div><p class="eyebrow">Verified U.S. commodity trade</p><h3>${mineral ? H.escape(mineral.canonical_name) : "Pilot strategic-resource materials"}, ${H.escape(this.state.year)}</h3></div><p>Exact-year official national imports and exports in their published units. No interpolation, dollar conversion, or partner-country attribution.</p></div>
        <div class="trade-scope-note"><strong>National aggregate</strong><span>${H.escape(selectionNote)}</span></div>
        ${this.renderTradeDetailPilot(details, research, records)}
        ${groups.length ? `<div class="table-scroll trade-table"><table><caption>Official U.S. mineral imports and exports for ${H.escape(this.state.year)}</caption><thead><tr><th>Material</th><th>Imports</th><th>Exports</th><th>Source definition</th><th>Provenance</th></tr></thead><tbody>${groups.map((group) => {
          const source = group.imports || group.exports;
          const valueCell = (row) => row ? `<strong>${H.formatNumber(row.value)}</strong><small>${H.escape(row.unit)}</small>` : '<span class="unknown-value">Not published</span>';
          return `<tr><th scope="row"><a href="${H.detailHref("minerals", group.mineral.id)}">${H.escape(group.mineral.canonical_name)}</a></th><td>${valueCell(group.imports)}</td><td>${valueCell(group.exports)}</td><td>${H.escape(source.trade_basis)}</td><td><a href="${H.escape(source.source_url)}" target="_blank" rel="noopener">USGS Data Series 140 · ${H.escape(source.table_or_page)}</a></td></tr>`;
        }).join("")}</tbody></table></div><p class="trade-source-note"><strong>Reading rule:</strong> A missing direction means no numeric cell was published in the normalized worksheet for that year; it does not mean zero trade.</p>` : `<p class="empty-note">${H.escape(emptyMessage)}</p>`}`;
    }

    renderTradeDetailPilot(details, research, aggregateRecords) {
      if (!details.length && !research.length) return "";
      const totals = new Map(details.filter((row) => row.is_total).map((row) => [row.direction, row]));
      const aggregates = new Map(aggregateRecords.map((row) => [row.direction, row]));
      const measurement = (item) => item && item.display ? `${H.escape(item.display)} <small>${H.escape(item.unit)}</small>` : '<span class="unknown-value">Not published</span>';
      const comparison = ["imports", "exports"].map((direction) => {
        const total = totals.get(direction);
        const aggregate = aggregates.get(direction);
        if (!total && !aggregate) return "";
        return `<div><span>${H.escape(direction)}</span><strong>${total ? measurement(total.quantity) : '<span class="unknown-value">Not available</span>'}</strong><small>Census-derived contemporaneous categories</small>${aggregate ? `<strong>${H.formatNumber(aggregate.value)} <small>${H.escape(aggregate.unit)}</small></strong><small>Later USGS standardized series</small>` : ""}</div>`;
      }).join("");
      const rows = details.map((row) => `<tr${row.is_total ? ' class="is-total"' : ""}><th scope="row">${H.escape(row.direction)}</th><td>${H.escape(row.category)}</td><td>${measurement(row.quantity)}</td><td>${measurement(row.trade_value)}</td><td><a href="${H.escape(row.source_url)}" target="_blank" rel="noopener">${H.escape(row.table_or_page)}</a></td></tr>`).join("");
      const queues = research.map((queue) => `<div class="trade-acquisition"><div><span class="badge badge-queue">Source acquisition</span><h4>${H.escape(queue.title)}</h4><p>${H.escape(queue.objective)}</p></div><div class="trade-report-list">${queue.reports.map((report) => `<div><strong>${H.escape(report.series)}</strong><span>${H.escape(report.title)}</span><small>${H.escape(report.role)}</small><a href="${H.escape(report.official_description_url)}" target="_blank" rel="noopener">Official Census description ↗</a></div>`).join("")}</div><ul>${queue.classification_notes.map((note) => `<li>${H.escape(note)}</li>`).join("")}</ul><a class="button-link" href="${H.escape(queue.official_request_url)}" target="_blank" rel="noopener">Find or request the legacy Census reports ↗</a></div>`).join("");
      return `<section class="trade-pilot" aria-labelledby="trade-pilot-title"><div class="trade-pilot-heading"><div><p class="eyebrow">1983 Census recovery pilot</p><h4 id="trade-pilot-title">Rare-earth trade before a stable modern category</h4></div>${H.badge("Reviewed official table", "verified")}</div><p>The contemporaneous tables and the later standardized series answer different questions. They are displayed side by side and are not merged.</p><div class="trade-comparison">${comparison}</div><div class="trade-scope-note caution"><strong>Classification boundary</strong><span>The published 1983 export total includes 2,684 metric tons of thorium ore and concentrates. Data Series 140 instead reports rare-earth-oxide equivalent. Neither total can validate country rows from FT 246 or FT 446 until those reports are reviewed in their original classifications.</span></div>${rows ? `<div class="table-scroll trade-detail-table"><table><caption>Published 1983 rare-earth categories reproduced from Census-derived USGS Statistical Compendium tables</caption><thead><tr><th>Flow</th><th>Published category</th><th>Quantity</th><th>Trade value</th><th>Official table</th></tr></thead><tbody>${rows}</tbody></table></div>` : ""}${queues}</section>`;
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
      const records = this.data.statistics.filter((row) => row.mineral_id === mineral.id && row.year === this.state.year && row.country_id === "united-states");
      const priority = ["U.S. primary production", "U.S. imports", "U.S. exports", "U.S. apparent consumption", "Unit value", "World production"];
      const selected = priority.map((metric) => records.find((row) => row.metric === metric)).filter(Boolean);
      return `<div class="atlas-panel-heading"><div><p class="eyebrow">Official statistical context</p><h3>${H.escape(mineral.canonical_name)}, ${H.escape(this.state.year)}</h3></div><p>Exact-year U.S. and world series only. No interpolation and no country supplier shares.</p></div>${selected.length ? `<div class="atlas-number-grid">${selected.map((row) => `<article><strong>${H.formatNumber(row.value)}</strong><span>${H.escape(row.metric)}</span><small>${H.escape(row.unit)}</small><a href="${H.escape(row.source_url)}" target="_blank" rel="noopener">USGS table source ↗</a></article>`).join("")}</div>` : `<p class="empty-note">No numeric USGS benchmark is checked in for ${H.escape(mineral.canonical_name)} in ${H.escape(this.state.year)}. Missing values are not interpolated.</p>`}`;
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
    }

    renderTable() {
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
      const activeCountries = this.data.countries.filter((row) => this.countryValue(row) > 0).length;
      const relationships = this.activeRelationships().length;
      const mineral = this.selectedMineral();
      $("atlasMapStatus").innerHTML = `<strong>${H.escape(this.state.year)} · ${H.escape(mineral ? mineral.canonical_name : "All pilot materials")}</strong><span>${H.escape(activeCountries)} geographies with ${H.escape(this.layer(this.state.mode).short_title)} evidence · ${H.escape(relationships)} documented access links</span>`;
    }

    renderAll() {
      $("mapYear").value = this.state.year;
      $("mapYearValue").textContent = this.state.year;
      $("mapMineral").value = this.state.mineral;
      $("atlasMode").value = this.state.mode;
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
