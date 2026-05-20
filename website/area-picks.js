import {
  areaPicksPageUrl,
  filterPicksByYears,
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
  const area = q.get("area") || "";
  const years = parseYearsParam(q.get("years"));
  return { mode, area, years };
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

async function main() {
  const { mode, area, years: yearsParam } = parseQuery();
  const highlightConference = mode === "published";

  const back = document.getElementById("back-link");
  if (back) {
    back.href = `index.html#top-picks-${mode}`;
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

  document.title = `${cat.label} | OS Kernel Papers Hub`;
  document.getElementById("area-title").textContent = cat.label;
  document.getElementById("area-subtitle").textContent = modeLabel(mode);
  const period = data.period_label || data.month_label || "";
  const built = data.generated_at ? `Updated ${formatGeneratedAt(data.generated_at)}` : "";
  document.getElementById("area-meta").textContent = `${period}  ${visible.length} papers  ${modeLabel(mode)}${built ? `  ${built}` : ""}`;
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
