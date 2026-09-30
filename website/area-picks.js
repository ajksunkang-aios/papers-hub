import {
  areaPicksPageUrl,
  filterPicksByYears,
  pickCalendarYear,
  renderPickRow,
  sortedUniqueYears,
  withDisplayRanks,
} from "./picks-ui.js";
import { escapeHtml, formatGeneratedAt } from "./shared.js";

function parseYearsParam(raw) {
  if (!raw) return [];
  return sortedUniqueYears(
    raw
      .split(",")
      .map((p) => Number(p.trim()))
      .filter((y) => Number.isFinite(y))
  );
}

function parseQuery() {
  const q = new URLSearchParams(window.location.search);
  const mode = q.get("mode") === "published" ? "published" : "arxiv";
  // `topic` selects a custom topic (surfaced via the sidebar Custom topics
  // group); `area` selects one of the homepage areas. Both resolve to a
  // category id in the picks data, so treat them as the same selector.
  const topic = q.get("topic") || "";
  const area = q.get("area") || topic;
  const years = parseYearsParam(q.get("years"));
  return { mode, area, topic, years };
}

function dataUrlForMode(mode) {
  return mode === "published" ? "data/top-published.json" : "data/top-monthly.json";
}

function modeLabel(mode) {
  return mode === "published" ? "Published paper picks by area" : "Recent arXiv picks by areas";
}

async function loadPicksData(mode) {
  const res = await fetch(`${dataUrlForMode(mode)}?ts=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Could not load picks data");
  return res.json();
}

function renderYearFilterButtons(years, selectedYears, areaId, mode) {
  const el = document.getElementById("area-year-filters");
  if (!el) return;
  el.innerHTML = `
    <span class="top-year-label">Year</span>
    ${years
      .map((year) => {
        const active = selectedYears.has(year);
        return `<button type="button" class="top-year-btn${active ? " is-active" : ""}" data-year="${year}" aria-pressed="${active ? "true" : "false"}">${year}</button>`;
      })
      .join("")}`;
  el.querySelectorAll(".top-year-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const year = Number(btn.dataset.year);
      if (!years.includes(year)) return;
      if (selectedYears.has(year)) {
        if (selectedYears.size <= 1) return;
        selectedYears.delete(year);
      } else {
        selectedYears.add(year);
      }
      const next = sortedUniqueYears([...selectedYears]);
      const url = areaPicksPageUrl(mode, areaId, new Set(next));
      window.location.href = url;
    });
  });
}

function matchesSearch(pick, query) {
  if (!query) return true;
  const hay = `${pick.title} ${(pick.authors || []).join(" ")}`.toLowerCase();
  return hay.includes(query);
}

function renderList(picks, highlightConference) {
  const list = document.getElementById("area-picks-list");
  const countEl = document.getElementById("area-result-count");
  if (!list) return;
  if (!picks.length) {
    list.innerHTML = "";
    if (countEl) countEl.textContent = "No papers match your filters.";
    return;
  }
  if (countEl) countEl.textContent = `${picks.length} paper${picks.length === 1 ? "" : "s"}`;
  list.innerHTML = picks.map((p) => renderPickRow(p, { highlightConference })).join("");
}

/**
 * Timeline view for custom topics: group all papers by calendar year,
 * newest first (2026 → 2025 → … → oldest), ignoring the homepage's
 * year-window. Each year is a section heading with its paper count, and
 * the list beneath repeats the standard pick row markup.
 */
function renderTimeline(picks, highlightConference) {
  const list = document.getElementById("area-picks-list");
  const countEl = document.getElementById("area-result-count");
  if (!list) return;
  if (!picks.length) {
    list.innerHTML = "";
    if (countEl) countEl.textContent = "No papers match your filters.";
    return;
  }

  // Group by year (null/unknown lumped under "Undated"), sort newest first.
  const byYear = new Map();
  for (const p of picks) {
    const y = pickCalendarYear(p);
    const key = y === null ? null : y;
    if (!byYear.has(key)) byYear.set(key, []);
    byYear.get(key).push(p);
  }
  const yearsDesc = [...byYear.keys()].sort((a, b) => {
    if (a === null) return 1;
    if (b === null) return -1;
    return b - a;
  });

  if (countEl) countEl.textContent = `${picks.length} paper${picks.length === 1 ? "" : "s"} · ${yearsDesc.length} years`;

  const parts = [];
  for (const y of yearsDesc) {
    const group = byYear.get(y);
    const label = y === null ? "Undated" : String(y);
    parts.push(
      `<li class="timeline-year-group">` +
        `<h2 class="timeline-year-heading">${escapeHtml(label)} <span class="timeline-year-count">${group.length}</span></h2>` +
        `<ol class="timeline-year-picks">` +
          group.map((p) => renderPickRow(p, { highlightConference })).join("") +
        `</ol>` +
      `</li>`
    );
  }
  list.innerHTML = parts.join("");
}

async function main() {

  const { mode, area, topic, years: yearsParam } = parseQuery();
  const highlightConference = mode === "published";
  const isCustomTopic = Boolean(topic);

  const back = document.getElementById("back-link");
  if (back) {
    back.href = isCustomTopic ? "index.html" : `index.html#top-picks-${mode}`;
    back.textContent = isCustomTopic ? "Home" : back.textContent;
  }

  if (!area) {
    document.getElementById("area-title").textContent = "Area not specified";
    return;
  }

  let data;
  try {
    data = await loadPicksData(mode);
  } catch (err) {
    document.getElementById("area-title").textContent = "Failed to load";
    document.getElementById("area-meta").textContent = String(err);
    return;
  }

  const cat = (data.categories || []).find((c) => c.id === area);
  if (!cat) {
    document.getElementById("area-title").textContent = "Unknown area";
    document.getElementById("area-meta").textContent = `No category "${area}" in ${mode} data.`;
    return;
  }

  // Custom topics render as a full-history timeline (newest year first),
  // ignoring the homepage's pick-year window, so the full back-filled
  // history is visible rather than only the current 2025–2026 slice.
  if (isCustomTopic) {
    const allPicks = cat.all_picks?.length ? cat.all_picks : cat.picks || [];
    const visible = withDisplayRanks(allPicks);

    document.title = `${cat.label} | AgentOS Papers Hub`;
    document.getElementById("area-title").textContent = cat.label;
    document.getElementById("area-subtitle").textContent = `Custom topic · ${modeLabel(mode).toLowerCase()} timeline`;
    const built = data.generated_at ? `Updated ${formatGeneratedAt(data.generated_at)}` : "";
    const ys = visible.map(pickCalendarYear).filter((y) => y !== null);
    const yearSpan = ys.length ? (Math.min(...ys) === Math.max(...ys) ? `${Math.max(...ys)}` : `${Math.max(...ys)}–${Math.min(...ys)}`) : "";
    document.getElementById("area-meta").textContent =
      `${visible.length} papers${yearSpan ? ` · ${yearSpan}` : ""} · ${modeLabel(mode)}${built ? ` · ${built}` : ""}`;
    document.getElementById("area-note").textContent = data.note || "";

    // No year filter buttons in timeline view; the timeline is the filter.
    const yearFilters = document.getElementById("area-year-filters");
    if (yearFilters) yearFilters.innerHTML = "";

    const searchInput = document.getElementById("area-search");
    const applySearch = () => {
      const q = searchInput.value.trim().toLowerCase();
      const filtered = q ? visible.filter((p) => matchesSearch(p, q)) : visible;
      renderTimeline(filtered, highlightConference);
    };
    searchInput.addEventListener("input", applySearch);
    applySearch();
    return;
  }

  const availableYears = sortedUniqueYears(
    yearsParam.length ? yearsParam : data.years?.map(Number) || []
  );
  const selectedYears = new Set(
    yearsParam.length ? yearsParam : availableYears
  );

  const pool = filterPicksByYears(
    cat.all_picks?.length ? cat.all_picks : cat.picks || [],
    selectedYears
  );
  let visible = withDisplayRanks(pool);

  document.title = `${cat.label} | AgentOS Papers Hub`;
  document.getElementById("area-title").textContent = cat.label;
  document.getElementById("area-subtitle").textContent = isCustomTopic
    ? `Custom topic · ${modeLabel(mode).toLowerCase()}`
    : modeLabel(mode);
  const period = data.period_label || data.month_label || "";
  const built = data.generated_at ? `Updated ${formatGeneratedAt(data.generated_at)}` : "";
  document.getElementById("area-meta").textContent = `${period} � ${visible.length} papers � ${modeLabel(mode)}${built ? ` � ${built}` : ""}`;
  document.getElementById("area-note").textContent = data.note || "";

  renderYearFilterButtons(availableYears, selectedYears, area, mode);

  const searchInput = document.getElementById("area-search");
  const applySearch = () => {
    const q = searchInput.value.trim().toLowerCase();
    const filtered = q ? visible.filter((p) => matchesSearch(p, q)) : visible;
    renderList(filtered, highlightConference);
  };
  searchInput.addEventListener("input", applySearch);
  applySearch();
}

main().catch((err) => {
  document.getElementById("area-picks-list").innerHTML =
    `<p class="empty">${escapeHtml(String(err))}</p>`;
});
