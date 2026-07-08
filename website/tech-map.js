import { escapeHtml } from "./shared.js";
import { areaPicksPageUrl } from "./picks-ui.js";
import { initViewsWidget } from "./views.js?v=2";

let mapData = null;
let locale = "en";
let viewMode = "graph";
let selectedTopicId = null;
let filterQuery = "";

function t(obj, field) {
  const key = locale === "zh" ? `${field}_zh` : `${field}_en`;
  return obj[key] || obj[`${field}_en`] || "";
}

function allTopics() {
  const rows = [];
  for (const group of mapData?.groups || []) {
    for (const topic of group.topics || []) {
      rows.push({ group, topic });
    }
  }
  return rows;
}

function findTopic(topicId) {
  for (const { group, topic } of allTopics()) {
    if (topic.id === topicId) return { group, topic };
  }
  return null;
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

function renderElementLinks(topic, { compact = false } = {}) {
  return (topic.elements || [])
    .map((el) => {
      const term = (el.search_terms || [])[0] || t(el, "label");
      const label = escapeHtml(t(el, "label"));
      const href = escapeHtml(searchUrl(term));
      if (compact) {
        return `<li><a href="${href}">${label}</a></li>`;
      }
      return `
        <li class="tech-map-element">
          <a href="${href}">${label}</a>
          <span class="tech-map-element-terms">${escapeHtml((el.search_terms || []).slice(0, 3).join(" · "))}</span>
        </li>`;
    })
    .join("");
}

function renderDetail(topicId) {
  const mount = document.getElementById("tech-map-detail");
  const hit = findTopic(topicId);
  if (!hit) {
    mount.innerHTML = `<p class="panel-note">Select a Tier-1 topic to explore technical elements.</p>`;
    return;
  }
  const { group, topic } = hit;
  const picksLink = topic.area_id
    ? `<a class="tech-map-area-link" href="${escapeHtml(areaPicksPageUrl("published", topic.area_id, []))}">View area picks →</a>`
    : "";
  const elements = renderElementLinks(topic);

  mount.innerHTML = `
    <p class="tech-map-detail-group" style="color:${escapeHtml(group.accent || "#4338ca")}">${escapeHtml(t(group, "label"))}</p>
    <h3 class="tech-map-detail-title">${escapeHtml(t(topic, "label"))}</h3>
    <p class="tech-map-detail-summary">${escapeHtml(t(topic, "summary"))}</p>
    ${picksLink}
    <h4 class="tech-map-elements-heading">Technical elements</h4>
    <ul class="tech-map-elements">${elements}</ul>
  `;
}

function renderGraph() {
  const canvas = document.getElementById("tech-map-canvas");
  const groups = mapData?.groups || [];
  const parts = [];
  const edges = [];

  groups.forEach((group, gi) => {
    const topics = (group.topics || []).filter(topicMatchesFilter);
    if (!topics.length) return;

    const hubId = `hub-${group.id}`;
    parts.push(`
      <section class="tech-map-graph-group" data-group="${escapeHtml(group.id)}" style="--group-accent:${escapeHtml(group.accent || "#4338ca")}">
        <button type="button" class="tech-map-hub" id="${hubId}" data-hub="${escapeHtml(group.id)}">
          <span class="tech-map-hub-label">${escapeHtml(t(group, "label"))}</span>
          <span class="tech-map-hub-count">${topics.length} topics</span>
        </button>
        <div class="tech-map-graph-grid" role="list">
          ${topics
            .map((topic) => {
              const active = selectedTopicId === topic.id ? " is-active" : "";
              return `
            <article class="tech-map-node${active}" role="listitem"
              data-topic="${escapeHtml(topic.id)}" data-hub="${escapeHtml(group.id)}">
              <button type="button" class="tech-map-node-header tech-map-topic-select"
                data-topic="${escapeHtml(topic.id)}"
                aria-pressed="${selectedTopicId === topic.id ? "true" : "false"}">
                <span class="tech-map-node-label">${escapeHtml(t(topic, "label"))}</span>
              </button>
              <ul class="tech-map-node-elements">${renderElementLinks(topic, { compact: true })}</ul>
            </article>`;
            })
            .join("")}
        </div>
      </section>
    `);

    topics.forEach((topic) => {
      edges.push({ from: hubId, to: topic.id, groupId: group.id });
    });
  });

  if (!parts.length) {
    canvas.innerHTML = `<p class="empty">No topics match your filter.</p>`;
    return;
  }

  canvas.innerHTML = `
    <div class="tech-map-graph-wrap">
      <svg class="tech-map-edges" aria-hidden="true"></svg>
      <div class="tech-map-graph-groups">${parts.join("")}</div>
    </div>
  `;

  wireTopicButtons(canvas);
  requestAnimationFrame(() => drawEdges(canvas, edges));
}

function drawEdges(canvas, edges) {
  const svg = canvas.querySelector(".tech-map-edges");
  const wrap = canvas.querySelector(".tech-map-graph-wrap");
  if (!svg || !wrap) return;

  const wrapRect = wrap.getBoundingClientRect();
  svg.setAttribute("width", String(wrapRect.width));
  svg.setAttribute("height", String(wrapRect.height));
  svg.innerHTML = "";

  for (const edge of edges) {
    const fromEl = document.getElementById(edge.from);
    const toEl = canvas.querySelector(`[data-topic="${edge.to}"][data-hub="${edge.groupId}"]`);
    if (!fromEl || !toEl) continue;
    const fr = fromEl.getBoundingClientRect();
    const tr = toEl.getBoundingClientRect();
    const x1 = fr.left + fr.width / 2 - wrapRect.left;
    const y1 = fr.bottom - wrapRect.top;
    const x2 = tr.left + tr.width / 2 - wrapRect.left;
    const y2 = tr.top - wrapRect.top;
    const midY = (y1 + y2) / 2;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute(
      "d",
      `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`
    );
    path.setAttribute("class", "tech-map-edge");
    path.setAttribute("stroke", getComputedStyle(fromEl.closest(".tech-map-graph-group")).getPropertyValue("--group-accent").trim() || "#94a3b8");
    svg.appendChild(path);
  }
}

function renderTree() {
  const canvas = document.getElementById("tech-map-canvas");
  const html = (mapData?.groups || [])
    .map((group) => {
      const topics = (group.topics || []).filter(topicMatchesFilter);
      if (!topics.length) return "";
      return `
        <section class="tech-map-tree-group" style="--group-accent:${escapeHtml(group.accent || "#4338ca")}">
          <h3 class="tech-map-tree-group-title">${escapeHtml(t(group, "label"))}</h3>
          <ul class="tech-map-tree-root">
            ${topics
              .map((topic) => {
                const active = selectedTopicId === topic.id ? " is-active" : "";
                return `
              <li class="tech-map-tree-topic${active}">
                <button type="button" class="tech-map-tree-topic-btn tech-map-topic-select" data-topic="${escapeHtml(topic.id)}">
                  ${escapeHtml(t(topic, "label"))}
                </button>
                <ul class="tech-map-tree-elements">
                  ${renderElementLinks(topic, { compact: true })}
                </ul>
              </li>`;
              })
              .join("")}
          </ul>
        </section>`;
    })
    .join("");

  canvas.innerHTML = html ? `<div class="tech-map-tree">${html}</div>` : `<p class="empty">No topics match your filter.</p>`;
  wireTopicButtons(canvas);
}

function wireTopicButtons(root) {
  root.querySelectorAll(".tech-map-topic-select").forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedTopicId = btn.dataset.topic;
      renderDetail(selectedTopicId);
      paint();
    });
  });
}

function paint() {
  if (viewMode === "graph") renderGraph();
  else renderTree();
  if (selectedTopicId) renderDetail(selectedTopicId);
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
    if (viewMode === "graph") paint();
  });
}

async function main() {
  initViewsWidget();
  initControls();
  try {
    mapData = await loadMap();
    const first = allTopics()[0];
    selectedTopicId = first?.topic.id || null;
    applyLocale();
    if (selectedTopicId) renderDetail(selectedTopicId);
  } catch (err) {
    document.getElementById("tech-map-canvas").innerHTML = `<p class="empty">${escapeHtml(String(err))}</p>`;
  }
}

main();
