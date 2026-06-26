(function () {
  "use strict";

  // --- Dataset (embedded by the view) -------------------------------------
  var measures = JSON.parse(document.getElementById("measures-data").textContent || "[]");

  // Stable order for the kind wedges / legend.
  var KIND_ORDER = ["nature-based", "technical", "digital", "cooperative"];
  var FALLBACK_COLOR = "#9aa6a6";

  // --- Map setup ----------------------------------------------------------
  var map = L.map("map");
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19
  }).addTo(map);

  // Plain layer group — markers are never clustered.
  var markersLayer = L.layerGroup().addTo(map);

  // --- Pie / wedge marker icon --------------------------------------------
  function pieSVG(colors, size) {
    var r = size / 2 - 1, c = size / 2, stroke = "#161924";
    if (colors.length <= 1) {
      var fill = colors[0] || FALLBACK_COLOR;
      return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '">' +
        '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="' + fill + '" stroke="' + stroke + '" stroke-width="1.5"/></svg>';
    }
    var n = colors.length, paths = "";
    for (var i = 0; i < n; i++) {
      var a0 = (i / n) * 2 * Math.PI - Math.PI / 2;
      var a1 = ((i + 1) / n) * 2 * Math.PI - Math.PI / 2;
      var x0 = c + r * Math.cos(a0), y0 = c + r * Math.sin(a0);
      var x1 = c + r * Math.cos(a1), y1 = c + r * Math.sin(a1);
      var large = (a1 - a0) > Math.PI ? 1 : 0;
      paths += '<path d="M ' + c + ' ' + c + ' L ' + x0.toFixed(2) + ' ' + y0.toFixed(2) +
        ' A ' + r + ' ' + r + ' 0 ' + large + ' 1 ' + x1.toFixed(2) + ' ' + y1.toFixed(2) +
        ' Z" fill="' + colors[i] + '" stroke="' + stroke + '" stroke-width="0.75"/>';
    }
    return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '">' + paths +
      '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="none" stroke="' + stroke + '" stroke-width="1.5"/></svg>';
  }
  function pieIcon(colors) {
    var size = 24;
    return L.divIcon({
      html: pieSVG(colors, size),
      className: "pie-marker",
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
      tooltipAnchor: [0, -size / 2]
    });
  }
  // Kind colours of a measure, in the stable order.
  function kindColors(m) {
    var byKind = {};
    m.tags.forEach(function (t) { if (t.category === "kind") byKind[t.slug] = t.color || FALLBACK_COLOR; });
    return KIND_ORDER.filter(function (s) { return byKind[s]; }).map(function (s) { return byKind[s]; });
  }

  // --- Build markers + table rows (once) ----------------------------------
  var tbody = document.querySelector("#measure-table tbody");
  var entries = measures.map(function (m) {
    var marker = L.marker([m.lat, m.lng], { icon: pieIcon(kindColors(m)) });
    var preview =
      '<div class="map-preview">' +
      (m.preview_url ? '<img src="' + m.preview_url + '" alt="">' : "") +
      '<div class="title">' + escapeHtml(m.title) + "</div>" +
      (m.summary ? '<div class="summary">' + escapeHtml(m.summary) + "</div>" : "") +
      "</div>";
    marker.bindTooltip(preview, { direction: "top", opacity: 1, className: "preview-tooltip" });
    marker.on("click", function () { window.location.href = m.detail_url; });

    var tr = document.createElement("tr");
    tr.innerHTML =
      '<td class="col-title"><a href="' + m.detail_url + '">' + escapeHtml(m.title) + "</a></td>" +
      '<td class="col-tags"><div class="row-tags">' +
      m.tags.map(function (t) { return '<span class="row-tag">' + escapeHtml(t.name) + "</span>"; }).join("") +
      "</div></td>" +
      '<td class="col-summary">' + escapeHtml(m.summary || "") + "</td>";
    tbody.appendChild(tr);

    return { data: m, tagSlugs: m.tags.map(function (t) { return t.slug; }), marker: marker, row: tr };
  });

  // --- Filtering (facets: OR within a category, AND across categories) ----
  var checkboxes = Array.prototype.slice.call(document.querySelectorAll(".tag-filter"));
  var resultCount = document.getElementById("result-count");
  var measuresLabel = resultCount.dataset.label || "measures";

  function selectionByCategory() {
    var sel = {};
    checkboxes.forEach(function (c) {
      if (c.checked) {
        var cat = c.dataset.category || "other";
        (sel[cat] = sel[cat] || []).push(c.value);
      }
    });
    return sel;
  }
  function matches(entry, sel) {
    return Object.keys(sel).every(function (cat) {
      return sel[cat].some(function (s) { return entry.tagSlugs.indexOf(s) !== -1; });
    });
  }

  function applyFilter() {
    var sel = selectionByCategory();
    var shown = [];
    entries.forEach(function (entry) {
      var show = matches(entry, sel);
      entry.row.style.display = show ? "" : "none";
      if (show) shown.push(entry.marker);
    });
    markersLayer.clearLayers();
    shown.forEach(function (mk) { markersLayer.addLayer(mk); });
    resultCount.textContent = shown.length + " / " + entries.length + " " + measuresLabel;
    fitToMarkers(shown);
  }

  function fitToMarkers(markers) {
    if (markers.length === 0) { map.setView([20, 0], 2); return; }
    map.fitBounds(L.featureGroup(markers).getBounds().pad(0.2));
  }

  checkboxes.forEach(function (c) { c.addEventListener("change", applyFilter); });
  document.getElementById("clear-filters").addEventListener("click", function () {
    checkboxes.forEach(function (c) { c.checked = false; });
    applyFilter();
  });

  // Pre-select tags from URL (?tags=slug1,slug2) — used by detail-page tag links.
  var fromUrl = (new URLSearchParams(window.location.search).get("tags") || "").split(",").filter(Boolean);
  if (fromUrl.length) {
    checkboxes.forEach(function (c) { if (fromUrl.indexOf(c.value) !== -1) c.checked = true; });
  }

  // --- Legend (kind colours) ----------------------------------------------
  (function buildLegend() {
    var el = document.getElementById("map-legend");
    if (!el) return;
    var kinds = {};
    measures.forEach(function (m) {
      m.tags.forEach(function (t) {
        if (t.category === "kind" && !kinds[t.slug]) kinds[t.slug] = { name: t.name, color: t.color || FALLBACK_COLOR };
      });
    });
    var ordered = KIND_ORDER.filter(function (s) { return kinds[s]; });
    el.innerHTML = ordered.map(function (s) {
      return '<span class="legend-item">' +
        '<span class="legend-swatch" style="background:' + kinds[s].color + '"></span>' +
        escapeHtml(kinds[s].name) + "</span>";
    }).join("");
  })();

  applyFilter();

  // --- Helpers ------------------------------------------------------------
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
})();
