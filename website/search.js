import { escapeHtml, formatGeneratedAtUtc8 } from "./shared.js";
import { initViewsWidget } from "./views.js?v=2";

const MIN_QUERY_LEN = 2;
const MAX_RESULTS = 200;

/** @returns {{ score: number, titleHit: boolean, abstractHit: boolean } | null} */
export function scoreKeywordMatch(paper, query) {
  const q = query.trim().toLowerCase();
  if (q.length < MIN_QUERY_LEN) return null;
  const title = (paper.title || "").toLowerCase();
  const abstract = (paper.abstract || "").toLowerCase();
  const titleHit = title.includes(q);
  const abstractHit = !titleHit && abstract.includes(q);
  if (!titleHit && !abstractHit) return null;
  return {
    score: titleHit ? 2 : 1,
    titleHit,
    abstractHit,
  };
}

export function abstractSnippet(abstract, query, maxLen = 220) {
  if (!abstract) return "";
  const q = query.trim().toLowerCase();
  const lower = abstract.toLowerCase();
  const idx = lower.indexOf(q);
  if (idx < 0) {
    return abstract.length <= maxLen ? abstract : `${abstract.slice(0, maxLen - 1)}…`;
  }
  const pad = 70;
  const start = Math.max(0, idx - pad);
  const end = Math.min(abstract.length, idx + q.length + pad);
  let snip = abstract.slice(start, end);
  if (start > 0) snip = `…${snip}`;
  if (end < abstract.length) snip = `${snip}…`;
  return snip;
}

export function searchPapers(papers, query) {
  const q = query.trim();
  if (q.length < MIN_QUERY_LEN) return [];
  const scored = [];
  for (const paper of papers) {
    const match = scoreKeywordMatch(paper, q);
    if (!match) continue;
    scored.push({ paper, ...match });
  }
  scored.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    const yearA = Number(a.paper.year) || 0;
    const yearB = Number(b.paper.year) || 0;
    if (yearB !== yearA) return yearB - yearA;
    return String(a.paper.title).localeCompare(String(b.paper.title));
  });
  return scored.slice(0, MAX_RESULTS);
}

function renderResult(row, query, rank) {
  const { paper } = row;
  const href = paper.href || "#";
  const external = paper.external_url
    ? `<a href="${escapeHtml(paper.external_url)}" target="_blank" rel="noopener">${paper.source === "arxiv" ? "PDF" : "dblp"}</a>`
    : "";
  const snippet = row.abstractHit ? abstractSnippet(paper.abstract, query) : "";
  const matchLabel = row.titleHit ? "Title match" : "Abstract match";
  const venue = paper.venue ? escapeHtml(String(paper.venue)) : "";
  const year = paper.year ? escapeHtml(String(paper.year)) : "";
  const sourceBadge = paper.source === "arxiv" ? "arXiv" : "dblp";

  return `
    <li class="search-result-item">
      <span class="search-result-rank" aria-hidden="true">${rank}</span>
      <article class="search-result-body">
        <div class="search-result-head">
          <span class="badge badge-${escapeHtml(paper.source)}">${sourceBadge}</span>
          ${venue || year ? `<span class="search-result-venue">${venue}${venue && year ? " · " : ""}${year}</span>` : ""}
          <span class="search-result-match">${matchLabel}</span>
        </div>
        <h2 class="search-result-title">
          <a href="${escapeHtml(href)}" ${paper.source === "arxiv" ? 'target="_blank" rel="noopener"' : ""}>${escapeHtml(paper.title || "Untitled")}</a>
        </h2>
        ${snippet ? `<p class="search-result-snippet">${escapeHtml(snippet)}</p>` : ""}
        <p class="search-result-links">${external}</p>
      </article>
    </li>`;
}

function renderEmpty(query, loaded) {
  if (!loaded) {
    return `<p class="empty">Loading search index…</p>`;
  }
  if (query.trim().length < MIN_QUERY_LEN) {
    return `<p class="panel-note">Type at least ${MIN_QUERY_LEN} characters to search title and abstract.</p>`;
  }
  return `<p class="empty">No papers match <strong>${escapeHtml(query.trim())}</strong> in title or abstract.</p>`;
}

let indexData = null;

async function loadIndex() {
  const res = await fetch(`data/search-index.json?ts=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load search index (${res.status})`);
  return res.json();
}

function updateUrlQuery(query) {
  const url = new URL(window.location.href);
  const trimmed = query.trim();
  if (trimmed.length >= MIN_QUERY_LEN) {
    url.searchParams.set("q", trimmed);
  } else {
    url.searchParams.delete("q");
  }
  window.history.replaceState({}, "", url);
}

function runSearch(query) {
  const listEl = document.getElementById("search-results");
  const countEl = document.getElementById("search-result-count");
  const papers = indexData?.papers || [];
  const results = searchPapers(papers, query);

  if (results.length) {
    listEl.innerHTML = results.map((row, i) => renderResult(row, query, i + 1)).join("");
    countEl.textContent = `${results.length} result${results.length === 1 ? "" : "s"}${results.length >= MAX_RESULTS ? ` (first ${MAX_RESULTS})` : ""}`;
  } else {
    listEl.innerHTML = renderEmpty(query, Boolean(indexData));
    countEl.textContent = query.trim().length >= MIN_QUERY_LEN ? "0 results" : "";
  }
}

async function main() {
  initViewsWidget();
  const input = document.getElementById("search-input");
  const meta = document.getElementById("search-meta");
  const initialQuery = new URLSearchParams(window.location.search).get("q") || "";

  try {
    indexData = await loadIndex();
    const built = indexData.generated_at ? formatGeneratedAtUtc8(indexData.generated_at) : "";
    meta.textContent = `${indexData.count?.toLocaleString() || 0} papers indexed (dblp ${indexData.dblp_count || 0}, arXiv ${indexData.arxiv_count || 0})${built ? ` · updated ${built}` : ""}`;
  } catch (err) {
    meta.textContent = "Search index unavailable";
    document.getElementById("search-results").innerHTML = `<p class="empty">${escapeHtml(String(err))}</p>`;
    return;
  }

  if (initialQuery) {
    input.value = initialQuery;
    runSearch(initialQuery);
  } else {
    runSearch("");
  }

  let debounceTimer;
  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      updateUrlQuery(input.value);
      runSearch(input.value);
    }, 180);
  });
}

main();
