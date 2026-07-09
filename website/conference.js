import {
  escapeHtml,
  formatGeneratedAt,
  preparePapers,
  renderPaperList,
  renderStats,
} from "./shared.js";
import { initViewsWidget } from "./views.js?v=3";

function getConferenceId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id");
}

function setSourceLinks(meta) {
  const urls = meta.source_urls || [meta.source_url];
  const container = document.getElementById("source-links");
  container.innerHTML = urls
    .map((url, i) => {
      const label = urls.length > 1 ? `dblp volume ${i + 1}` : "dblp proceedings";
      return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${label}</a>`;
    })
    .join(" · ");
}

function renderLoadingSkeleton(listEl, rows = 8) {
  listEl.innerHTML = Array.from({ length: rows }, () => `
      <div class="paper-row paper-row-skeleton" aria-hidden="true">
        <div class="paper-row-body">
          <div class="skeleton-line skeleton-title"></div>
          <div class="skeleton-line skeleton-authors"></div>
        </div>
        <div class="skeleton-line skeleton-meta"></div>
      </div>
    `).join("");
  listEl.setAttribute("aria-busy", "true");
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

async function loadBuildInfo() {
  try {
    const res = await fetch("data/build-info.json", { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function main() {
  initViewsWidget();

  const confId = getConferenceId();
  if (!confId) {
    window.location.href = "index.html";
    return;
  }

  const listEl = document.getElementById("paper-list");
  const countEl = document.getElementById("result-count");
  const search = document.getElementById("search");
  const generatedEl = document.getElementById("generated-at");

  renderLoadingSkeleton(listEl);
  countEl.textContent = "Loading papers...";

  const [editionRes, buildInfo] = await Promise.all([
    fetch(`data/${confId}.json`),
    loadBuildInfo(),
  ]);

  if (!editionRes.ok) {
    listEl.removeAttribute("aria-busy");
    listEl.innerHTML = `<p class="empty">Could not find proceedings for <code>${escapeHtml(confId)}</code>. <a href="index.html">Back to all conferences</a></p>`;
    countEl.textContent = "";
    return;
  }

  const data = await editionRes.json();
  const edition = data.edition ? `${data.edition} ` : "";
  const short = data.short_name || data.venue.toUpperCase();
  document.title = `${short} ${data.year} Papers | OS Kernel Papers Hub`;
  document.getElementById("page-title").textContent = `${edition}${short} ${data.year}`;
  document.getElementById("page-subtitle").textContent = data.full_name || "";
  document.getElementById("back-link").href = "index.html";

  const papers = preparePapers(data);
  renderStats(papers, data, document.getElementById("stats"));
  setSourceLinks(data);

  const when = buildInfo?.generated_at ? formatGeneratedAt(buildInfo.generated_at) : "";
  generatedEl.textContent = when || "from dblp index";

  const update = () => {
    const shown = renderPaperList(papers, data, listEl, search.value);
    listEl.removeAttribute("aria-busy");
    const q = search.value.trim();
    countEl.textContent =
      q === "" ? `Showing all ${shown} papers` : `${shown} of ${papers.length} papers`;
  };

  search.addEventListener("input", debounce(update, 180));
  update();
}

main().catch((err) => {
  const listEl = document.getElementById("paper-list");
  listEl.removeAttribute("aria-busy");
  listEl.innerHTML = `<p class="empty">Failed to load papers: ${escapeHtml(String(err))}</p>`;
});
