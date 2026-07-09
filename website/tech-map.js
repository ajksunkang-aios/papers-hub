import { escapeHtml } from "./shared.js";
import { areaPicksPageUrl } from "./picks-ui.js";
import { initViewsWidget } from "./views.js?v=3";

let mapData = null;
let locale = "en";
let viewMode = "graph";
let filterQuery = "";

const SVG_NS = "http://www.w3.org/2000/svg";

function t(obj, field) {
  const key = locale === "zh" ? `${field}_zh` : `${field}_en`;
  return obj[key] || obj[`${field}_en`] || "";
}

function topicMatchesFilter(topic) {
  const q = filterQuery.trim().toLowerCase();
  if (!q) return true;
  const hay = [
    t(topic, "label"),
    t(topic, "summary"),
    ...(topic.elements || []).flatMap((el) => [t(el, "label"), ...(el.search_terms || [])]),
  ]
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

function searchUrl(term) {
  return `search.html?q=${encodeURIComponent(term)}`;
}

function topicHref(topic) {
  if (topic.area_id) return areaPicksPageUrl("published", topic.area_id, []);
  return searchUrl(t(topic, "label"));
}

function renderElementLinks(topic) {
  return (topic.elements || [])
    .map((el) => {
      const term = (el.search_terms || [])[0] || t(el, "label");
      return `<li><a href="${escapeHtml(searchUrl(term))}">${escapeHtml(t(el, "label"))}</a></li>`;
    })
    .join("");
}

function renderGroupSection(group, gi) {
  const topics = (group.topics || []).filter(topicMatchesFilter);
  if (!topics.length) return "";

  const hubId = `hub-${group.id}`;
  const accent = escapeHtml(group.accent || "#4338ca");
  const ordinal = String(gi + 1).padStart(2, "0");
  const isPrimary = group.id === "classic-os";
  return `
    <section class="tech-map-graph-group${isPrimary ? " is-primary" : ""}" data-group="${escapeHtml(group.id)}" style="--group-accent:${accent}">
      <div class="tech-map-constellation">
        <svg class="tech-map-edges" aria-hidden="true"></svg>
        <div class="tech-map-hub-stage">
          <div class="tech-map-hub" id="${hubId}">
            <span class="tech-map-hub-ordinal" aria-hidden="true">${ordinal}</span>
            <span class="tech-map-hub-copy">
              <span class="tech-map-hub-label">${escapeHtml(t(group, "label"))}</span>
              <span class="tech-map-hub-count">${topics.length}</span>
            </span>
          </div>
        </div>
        <div class="tech-map-orbit-grid" role="list">
          ${topics
            .map(
              (topic, i) => `
            <article class="tech-map-node" role="listitem"
              data-topic="${escapeHtml(topic.id)}" data-hub="${escapeHtml(group.id)}"
              style="--node-i:${i}">
              <a class="tech-map-node-header" href="${escapeHtml(topicHref(topic))}">
                <span class="tech-map-node-label">${escapeHtml(t(topic, "label"))}</span>
              </a>
              <ul class="tech-map-node-elements">${renderElementLinks(topic)}</ul>
            </article>`
            )
            .join("")}
        </div>
      </div>
    </section>
  `;
}

function renderGraph() {
  const canvas = document.getElementById("tech-map-canvas");
  const groups = mapData?.groups || [];

  const primaryHtml = groups
    .map((group, gi) => (group.id === "classic-os" ? renderGroupSection(group, gi) : ""))
    .join("");
  const secondaryHtml = groups
    .map((group, gi) => (group.id !== "classic-os" ? renderGroupSection(group, gi) : ""))
    .join("");

  if (!primaryHtml && !secondaryHtml) {
    canvas.innerHTML = `<p class="empty">No topics match your filter.</p>`;
    return;
  }

  const legend = groups
    .map((group, gi) => {
      const topics = (group.topics || []).filter(topicMatchesFilter);
      if (!topics.length) return "";
      return `
        <button type="button" class="tech-map-legend-item" data-scroll-group="${escapeHtml(group.id)}"
          style="--group-accent:${escapeHtml(group.accent || "#4338ca")}">
          <span class="tech-map-legend-dot" aria-hidden="true">${String(gi + 1).padStart(2, "0")}</span>
          <span class="tech-map-legend-label">${escapeHtml(t(group, "label"))}</span>
        </button>`;
    })
    .join("");

  canvas.innerHTML = `
    <div class="tech-map-graph-wrap">
      <div class="tech-map-legend" role="navigation" aria-label="Pillars">${legend}</div>
      <div class="tech-map-graph-layout">
        ${primaryHtml ? `<div class="tech-map-graph-row tech-map-graph-row-primary">${primaryHtml}</div>` : ""}
        ${secondaryHtml ? `<div class="tech-map-graph-row tech-map-graph-row-secondary">${secondaryHtml}</div>` : ""}
      </div>
    </div>`;

  canvas.querySelectorAll("[data-scroll-group]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const el = canvas.querySelector(`.tech-map-graph-group[data-group="${btn.dataset.scrollGroup}"]`);
      el?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  requestAnimationFrame(() => {
    redrawGraphEdges(canvas);
    syncGraphHighlights(canvas);
  });
}

function svgEl(name, attrs = {}) {
  const el = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
  return el;
}

function edgeGradientId(groupId) {
  return `tech-map-edge-grad-${groupId}`;
}

function ensureEdgeGradient(svg, groupId, accent) {
  let defs = svg.querySelector("defs");
  if (!defs) {
    defs = svgEl("defs");
    svg.appendChild(defs);
  }
  const gradId = edgeGradientId(groupId);
  if (defs.querySelector(`#${gradId}`)) return gradId;

  const grad = svgEl("linearGradient", {
    id: gradId,
    x1: "0%",
    y1: "0%",
    x2: "100%",
    y2: "100%",
  });
  grad.appendChild(svgEl("stop", { offset: "0%", "stop-color": accent, "stop-opacity": "0.5" }));
  grad.appendChild(svgEl("stop", { offset: "100%", "stop-color": accent, "stop-opacity": "0.12" }));
  defs.appendChild(grad);
  return gradId;
}

function drawGroupEdges(groupEl) {
  const svg = groupEl.querySelector(".tech-map-edges");
  const constellation = groupEl.querySelector(".tech-map-constellation");
  const hub = groupEl.querySelector(".tech-map-hub");
  const nodes = groupEl.querySelectorAll(".tech-map-node");
  if (!svg || !constellation || !hub) return;

  const groupId = groupEl.dataset.group || "group";
  const accent = getComputedStyle(groupEl).getPropertyValue("--group-accent").trim() || "#4338ca";
  const box = constellation.getBoundingClientRect();
  const w = Math.max(1, box.width);
  const h = Math.max(1, box.height);

  svg.setAttribute("width", String(w));
  svg.setAttribute("height", String(h));
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.innerHTML = "";

  const gradId = ensureEdgeGradient(svg, groupId, accent);
  const hubRect = hub.getBoundingClientRect();
  const x1 = hubRect.left + hubRect.width / 2 - box.left;
  const y1 = hubRect.top + hubRect.height / 2 - box.top;

  nodes.forEach((node) => {
    const nr = node.getBoundingClientRect();
    const x2 = nr.left + nr.width / 2 - box.left;
    const y2 = nr.top + nr.height / 2 - box.top;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const dist = Math.hypot(dx, dy) || 1;
    const bend = Math.min(36, dist * 0.14);
    const cx = (x1 + x2) / 2 - (dy / dist) * bend;
    const cy = (y1 + y2) / 2 + (dx / dist) * bend;

    svg.appendChild(
      svgEl("path", {
        d: `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`,
        class: "tech-map-edge",
        "data-topic": node.dataset.topic || "",
        stroke: `url(#${gradId})`,
      })
    );
  });
}

function redrawGraphEdges(canvas) {
  canvas.querySelectorAll(".tech-map-graph-group").forEach(drawGroupEdges);
}

function syncGraphHighlights(canvas) {
  canvas.querySelectorAll(".tech-map-node").forEach((node) => {
    node.onmouseenter = () => setGraphEdgeHighlight(canvas, node.dataset.topic, true);
    node.onmouseleave = () => setGraphEdgeHighlight(canvas, node.dataset.topic, false);
  });
}

function setGraphEdgeHighlight(canvas, topicId, on) {
  if (!topicId) return;
  canvas.querySelectorAll(`.tech-map-edge[data-topic="${topicId}"]`).forEach((path) => {
    path.classList.toggle("is-lit-hover", on);
  });
  canvas.querySelectorAll(`.tech-map-node[data-topic="${topicId}"]`).forEach((node) => {
    node.classList.toggle("is-linked", on);
  });
}

function renderTree() {
  const canvas = document.getElementById("tech-map-canvas");
  const html = (mapData?.groups || [])
    .map((group, gi) => {
      const topics = (group.topics || []).filter(topicMatchesFilter);
      if (!topics.length) return "";
      const ordinal = String(gi + 1).padStart(2, "0");
      return `
        <section class="tech-map-tree-group" style="--group-accent:${escapeHtml(group.accent || "#4338ca")}">
          <h3 class="tech-map-tree-group-title">
            <span class="tech-map-tree-ordinal">${ordinal}</span>
            ${escapeHtml(t(group, "label"))}
          </h3>
          <ul class="tech-map-tree-root">
            ${topics
              .map(
                (topic) => `
              <li class="tech-map-tree-topic">
                <a class="tech-map-tree-topic-btn" href="${escapeHtml(topicHref(topic))}">
                  ${escapeHtml(t(topic, "label"))}
                </a>
                <ul class="tech-map-tree-elements">${renderElementLinks(topic)}</ul>
              </li>`
              )
              .join("")}
          </ul>
        </section>`;
    })
    .join("");

  canvas.innerHTML = html
    ? `<div class="tech-map-tree tech-map-tree-compact">${html}</div>`
    : `<p class="empty">No topics match your filter.</p>`;
}

function paint() {
  if (viewMode === "graph") renderGraph();
  else renderTree();
}

function applyLocale() {
  document.getElementById("page-title").textContent = t(mapData, "title");
  document.getElementById("page-subtitle").textContent = t(mapData, "subtitle");
  document.title = `${t(mapData, "title")} | OS Kernel Papers Hub`;
  paint();
}

async function loadMap() {
  const res = await fetch(`data/tech-map.json?ts=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load tech map (${res.status})`);
  return res.json();
}

function initControls() {
  document.querySelectorAll(".tech-map-view-toggle [data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      viewMode = btn.dataset.view;
      document.querySelectorAll(".tech-map-view-toggle [data-view]").forEach((b) => {
        const on = b.dataset.view === viewMode;
        b.classList.toggle("is-active", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
      paint();
    });
  });

  document.querySelectorAll(".tech-map-lang-toggle [data-lang]").forEach((btn) => {
    btn.addEventListener("click", () => {
      locale = btn.dataset.lang;
      document.querySelectorAll(".tech-map-lang-toggle [data-lang]").forEach((b) => {
        const on = b.dataset.lang === locale;
        b.classList.toggle("is-active", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
      applyLocale();
    });
  });

  const filter = document.getElementById("tech-map-filter");
  filter.addEventListener("input", () => {
    filterQuery = filter.value;
    paint();
  });

  window.addEventListener("resize", () => {
    if (viewMode !== "graph") return;
    const canvas = document.getElementById("tech-map-canvas");
    if (canvas) redrawGraphEdges(canvas);
  });
}

async function main() {
  initViewsWidget();
  initControls();
  try {
    mapData = await loadMap();
    applyLocale();
  } catch (err) {
    document.getElementById("tech-map-canvas").innerHTML = `<p class="empty">${escapeHtml(String(err))}</p>`;
  }
}

main();
