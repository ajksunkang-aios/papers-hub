import {
  escapeHtml,
  eventStatusUtc8,
  formatDateUtc8,
  formatGeneratedAt,
  formatGeneratedAtUtc8,
  todayIsoUtc8,
} from "./shared.js";
import {
  areaPicksPageUrl,
  filterPicksByYears,
  renderPickRow,
  sortedUniqueYears,
  withDisplayRanks,
} from "./picks-ui.js";
import { todayBroadcast as bundledBroadcast } from "./today-broadcast-data.js";
import { conferenceTimeline as bundledTimeline } from "./conference-timeline-data.js";
import { initViewsWidget } from "./views.js?v=2";

const DEFAULT_VENUE_ORDER = [
  "SOSP",
  "OSDI",
  "NSDI",
  "ASPLOS",
  "EuroSys",
  "ISCA",
  "FAST",
  "USENIX Security",
  "USENIX ATC",
  "ICSE",
];
let VENUE_ORDER = [...DEFAULT_VENUE_ORDER];
let hubConfig = null;

async function loadHubConfig() {
  try {
    const res = await fetch(`data/hub.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function applyHubBranding(hub) {
  if (!hub) return;
  hubConfig = hub;
  if (hub.venue_order?.length) VENUE_ORDER = hub.venue_order;
  if (hub.pick_years?.length) AREA_FILTER_YEARS = hub.pick_years.map(Number);

  document.title = hub.title || document.title;
  const h1 = document.querySelector(".site-header h1");
  if (h1 && hub.title) h1.textContent = hub.title;
  const lede = document.querySelector(".site-header .lede");
  if (lede && hub.lede) lede.textContent = hub.lede;

  const sections = hub.sections || {};
  const setHeading = (id, key) => {
    const title = sections[key]?.title;
    if (!title) return;
    const el = document.getElementById(id);
    if (el) el.textContent = title;
  };
  setHeading("timeline-heading", "timeline");
  setHeading("top-picks-heading", "top_picks");
  setHeading("conf-hub-heading", "conferences");

  const arxivModeBtn = document.getElementById("top-picks-mode-arxiv");
  const publishedModeBtn = document.getElementById("top-picks-mode-published");
  const arxivLabel =
    hub.categories?.arxiv_mode_label ||
    sections.picks_arxiv?.title ||
    "Recent arXiv picks by areas";
  const publishedLabel =
    hub.categories?.published_mode_label ||
    sections.picks_published?.title ||
    "Published paper picks by area";
  if (arxivModeBtn) arxivModeBtn.textContent = arxivLabel;
  if (publishedModeBtn) publishedModeBtn.textContent = publishedLabel;

  const countryLink = document.getElementById("country-analytics-link");
  if (countryLink) {
    const url = (hub.country_analytics_url || "country-analytics.html").trim();
    countryLink.href = url;
    if (url.startsWith("http")) {
      countryLink.target = "_blank";
      countryLink.rel = "noopener noreferrer";
    }
  }

  const authorLink = document.getElementById("author-analytics-link");
  if (authorLink) {
    const url = (hub.author_analytics_url || "author-analytics.html").trim();
    authorLink.href = url;
    if (url.startsWith("http")) {
      authorLink.target = "_blank";
      authorLink.rel = "noopener noreferrer";
    }
  }

  const broadcastTagline = document.querySelector(".broadcast-tagline");
  if (broadcastTagline && hub.tagline) {
    const tz = hub.tagline_timezone ? ` (${hub.tagline_timezone})` : "";
    broadcastTagline.innerHTML = `${escapeHtml(hub.tagline)} <span class="broadcast-utc">${escapeHtml(tz)}</span>`;
  }

  const timelineSection = document.getElementById("timeline-section");
  if (timelineSection && sections.timeline?.enabled === false) timelineSection.hidden = true;
  const broadcastSection = document.getElementById("broadcast-section");
  if (broadcastSection && sections.broadcast?.enabled === false) broadcastSection.hidden = true;
  const picksSection = document.getElementById("top-picks-section");
  if (picksSection && sections.top_picks?.enabled === false) picksSection.hidden = true;
  const confSection = document.querySelector(".conf-hub");
  if (confSection && sections.conferences?.enabled === false) confSection.hidden = true;
}

function groupByVenue(conferences) {
  const groups = new Map();
  for (const conf of conferences) {
    const key = conf.short_name;
    if (!groups.has(key)) {
      groups.set(key, { short_name: key, full_name: conf.full_name, editions: [] });
    }
    groups.get(key).editions.push(conf);
  }
  for (const g of groups.values()) {
    g.editions.sort((a, b) => b.year - a.year);
  }
  return groups;
}

function venueOrder(groups) {
  const ordered = [];
  for (const name of VENUE_ORDER) {
    if (groups.has(name)) ordered.push(groups.get(name));
  }
  for (const [name, g] of groups) {
    if (!VENUE_ORDER.includes(name)) ordered.push(g);
  }
  return ordered;
}

function matchesQuery(conf, q) {
  if (!q) return true;
  const hay = `${conf.short_name} ${conf.full_name} ${conf.year} ${conf.id}`.toLowerCase();
  return hay.includes(q);
}

function matchesVenueGroup(group, q) {
  if (!q) return true;
  if (group.short_name.toLowerCase().includes(q)) return true;
  if (group.full_name.toLowerCase().includes(q)) return true;
  return group.editions.some((e) => matchesQuery(e, q));
}

function editionHref(conf) {
  return `conference.html?id=${encodeURIComponent(conf.id)}`;
}

function renderLatestGrid(venues, q) {
  const grid = document.getElementById("latest-grid");
  const cards = [];

  for (const group of venues) {
    if (!matchesVenueGroup(group, q)) continue;
    const hit = q ? group.editions.find((e) => matchesQuery(e, q)) : null;
    cards.push(hit || group.editions[0]);
  }

  if (!cards.length) {
    grid.innerHTML = '<p class="empty empty-compact">No matching editions.</p>';
    return;
  }

  grid.innerHTML = cards
    .map((conf) => {
      return `
        <a class="latest-card" href="${editionHref(conf)}">
          <span class="latest-venue">${escapeHtml(conf.short_name)}</span>
          <span class="latest-year">${conf.year}</span>
          <span class="latest-count">${conf.paper_count} papers</span>
          <span class="latest-cta">View proceedings →</span>
        </a>
      `;
    })
    .join("");
}

function renderVenueList(venues, q) {
  const list = document.getElementById("venue-list");
  const visible = venues.filter((g) => matchesVenueGroup(g, q));

  if (!visible.length) {
    list.innerHTML = '<p class="empty empty-compact">No matching venues.</p>';
    return;
  }

  list.innerHTML = visible
    .map((group) => {
      const editions = group.editions.filter((e) => matchesQuery(e, q) || !q);
      const totalPapers = group.editions.reduce((n, e) => n + e.paper_count, 0);
      const yearRange = `${group.editions[group.editions.length - 1].year}–${group.editions[0].year}`;

      const pills = editions
        .map(
          (conf) => `
          <a class="year-pill" href="${editionHref(conf)}" title="${conf.paper_count} papers">
            <span class="year-pill-year">${conf.year}</span>
            <span class="year-pill-count">${conf.paper_count}</span>
          </a>
        `
        )
        .join("");

      return `
        <article class="venue-panel" data-venue="${escapeHtml(group.short_name)}">
          <header class="venue-panel-head">
            <div>
              <h3 class="venue-name">${escapeHtml(group.short_name)}</h3>
              <p class="venue-full">${escapeHtml(group.full_name)}</p>
            </div>
            <div class="venue-stats">
              <span>${group.editions.length} editions</span>
              <span>${totalPapers.toLocaleString()} papers</span>
              <span>${yearRange}</span>
            </div>
          </header>
          <div class="year-pills" role="list">${pills}</div>
        </article>
      `;
    })
    .join("");
}

function setConferenceMeta(conferences) {
  const groups = groupByVenue(conferences);
  const venues = venueOrder(groups);
  const totalPapers = conferences.reduce((n, c) => n + c.paper_count, 0);
  document.getElementById("conference-meta").textContent =
    `${venues.length} venues · ${conferences.length} editions · ${totalPapers.toLocaleString()} papers`;
}

function renderConferences(conferences, query) {
  const groups = groupByVenue(conferences);
  const venues = venueOrder(groups);
  const q = query.trim().toLowerCase();
  renderLatestGrid(venues, q);
  renderVenueList(venues, q);
}

const TOP_PREVIEW_DEFAULT = 5;
const topPanelState = new Map();
const topCategoriesCtxByScope = new Map();
const topPicksCache = { arxiv: null, published: null };
let topPicksMode = "published";
let topPicksModeWired = false;

function panelStateKey(scope, catId) {
  return `${scope}:${catId}`;
}

function topPreviewLimit(data) {
  return data?.preview_limit ?? TOP_PREVIEW_DEFAULT;
}

let AREA_FILTER_YEARS = [2023, 2024, 2025, 2026];

function defaultFilterYears(data) {
  const fromData = Array.isArray(data?.years)
    ? data.years.map(Number).filter((y) => Number.isFinite(y))
    : [];
  if (fromData.length) {
    return sortedUniqueYears(fromData);
  }
  return sortedUniqueYears([...AREA_FILTER_YEARS]);
}

function normalizePickTitle(title) {
  return (title || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function effectivePickScore(pick, ranking) {
  let score = pick.category_score ?? 0;
  if (pick.source !== "conference") return score;
  const boost = ranking?.conference_score_boost ?? 12;
  const baseYear = ranking?.recency_base_year ?? 2023;
  const perYear = ranking?.recency_boost_per_year ?? 2;
  const year = pick.year ? Number(pick.year) : 0;
  return score + boost + (year > baseYear ? (year - baseYear) * perYear : 0);
}

/** Match server-side balanced preview: mix conference + arXiv in top-N. */
function selectBalancedPreview(pool, limit, ranking) {
  if (!pool.length) return [];
  const minConf = Math.min(ranking?.min_conference_preview ?? 2, limit);

  const sortKey = (a, b) => effectivePickScore(b, ranking) - effectivePickScore(a, ranking);
  const conf = pool.filter((p) => p.source === "conference").sort(sortKey);
  const arxiv = pool
    .filter((p) => p.source === "arxiv")
    .sort((a, b) => (b.category_score ?? 0) - (a.category_score ?? 0));

  const nConf = Math.min(minConf, limit, conf.length);
  const chosen = conf.slice(0, nConf);
  const seen = new Set(chosen.map((p) => normalizePickTitle(p.title)).filter(Boolean));

  const rest = [];
  for (const item of arxiv) {
    const key = normalizePickTitle(item.title);
    if (key && seen.has(key)) continue;
    rest.push(item);
  }
  for (const item of conf.slice(nConf)) {
    const key = normalizePickTitle(item.title);
    if (key && seen.has(key)) continue;
    rest.push(item);
  }
  rest.sort(sortKey);

  while (chosen.length < limit && rest.length) {
    const item = rest.shift();
    chosen.push(item);
    const key = normalizePickTitle(item.title);
    if (key) seen.add(key);
  }

  return chosen.sort(sortKey).slice(0, limit);
}

/** Preview list for homepage panels (full list lives on area-picks.html). */
function picksForCategoryPanel(cat, state, previewLimit, ranking, mixedSources) {
  const fullPool = filterPicksByYears(
    cat.all_picks?.length ? cat.all_picks : cat.picks || [],
    state.years
  );
  if (!mixedSources) {
    return withDisplayRanks(fullPool.slice(0, previewLimit));
  }
  const serverPreview = filterPicksByYears(cat.picks || [], state.years);
  if (serverPreview.length >= Math.min(previewLimit, fullPool.length)) {
    return withDisplayRanks(serverPreview.slice(0, previewLimit));
  }
  return withDisplayRanks(selectBalancedPreview(fullPool, previewLimit, ranking));
}

function countConferencePicks(picks) {
  return picks.filter((p) => p.source === "conference").length;
}

function initPanelState(scope, catId, defaultYears) {
  const years = sortedUniqueYears(defaultYears);
  const key = panelStateKey(scope, catId);
  if (!topPanelState.has(key)) {
    topPanelState.set(key, {
      years: new Set(years),
    });
  }
  return topPanelState.get(key);
}

function renderYearFilters(scope, catId, availableYears, selectedYears) {
  const years = sortedUniqueYears(availableYears);
  return `
    <div class="top-year-filters" role="group" aria-label="Filter by year">
      <span class="top-year-label">Year</span>
      ${years
        .map((year) => {
          const active = selectedYears.has(year);
          return `<button type="button" class="top-year-btn${active ? " is-active" : ""}" data-scope="${escapeHtml(scope)}" data-cat-id="${escapeHtml(catId)}" data-year="${year}" aria-pressed="${active ? "true" : "false"}">${year}</button>`;
        })
        .join("")}
    </div>
  `;
}

function renderCategoryPanel(cat, state, previewLimit, availableYears, ranking, scope, options) {
  const { highlightConference = false, mixedSources = false } = options;
  const selectedYears = state.years;
  const fullPool = filterPicksByYears(
    cat.all_picks?.length ? cat.all_picks : cat.picks || [],
    selectedYears
  );
  const picks = picksForCategoryPanel(cat, state, previewLimit, ranking, mixedSources);
  const total = fullPool.length;
  const confInPool = countConferencePicks(fullPool);

  const list =
    picks.length === 0
      ? '<p class="empty empty-compact">No papers for the selected year(s).</p>'
      : `<ol class="top-picks-list">${picks.map((p) => renderPickRow(p, { highlightConference })).join("")}</ol>`;

  const moreLink =
    total > previewLimit
      ? `<a class="top-more-btn top-more-link" href="${escapeHtml(areaPicksPageUrl(scope, cat.id, selectedYears))}">More (${total})</a>`
      : "";

  const yearLabel = [...selectedYears].sort((a, b) => a - b).join(", ");

  return `
    <article class="top-category-panel" id="cat-${escapeHtml(cat.id)}" data-cat-id="${escapeHtml(cat.id)}">
      <header class="top-category-head">
        <h3 class="top-category-title">${escapeHtml(cat.label)}</h3>
        <span class="top-category-count" title="Years: ${escapeHtml(yearLabel)}">${picks.length} / ${total}${confInPool ? ` · ${confInPool} conference` : ""}</span>
      </header>
      ${renderYearFilters(scope, cat.id, availableYears, selectedYears)}
      ${list}
      ${moreLink}
    </article>
  `;
}

function rerenderCategoryPanel(container, cat, previewLimit, availableYears, ranking, scope, options) {
  const state = topPanelState.get(panelStateKey(scope, cat.id));
  if (!state) return;
  const panel = container.querySelector(`[data-cat-id="${CSS.escape(cat.id)}"]`);
  if (!panel) return;
  panel.outerHTML = renderCategoryPanel(
    cat,
    state,
    previewLimit,
    availableYears,
    ranking,
    scope,
    options
  );
}

function wireTopCategoryInteractions(container, scope) {
  const wireKey = `topWired:${scope}`;
  if (container.dataset[wireKey] === "1") return;
  container.dataset[wireKey] = "1";

  container.addEventListener("click", (e) => {
    const ctx = topCategoriesCtxByScope.get(scope);
    if (!ctx) return;
    const { categories, previewLimit, availableYears, ranking, options } = ctx;
    const yearList = sortedUniqueYears(availableYears);

    const yearBtn = e.target.closest(".top-year-btn");
    if (yearBtn && container.contains(yearBtn) && yearBtn.dataset.scope === scope) {
      e.preventDefault();
      const catId = yearBtn.dataset.catId;
      const year = Number(yearBtn.dataset.year);
      const cat = categories.find((c) => c.id === catId);
      if (!cat || !yearList.includes(year)) return;

      const state = topPanelState.get(panelStateKey(scope, catId));
      if (!state) return;

      if (state.years.has(year)) {
        if (state.years.size <= 1) return;
        state.years.delete(year);
      } else {
        state.years.add(year);
      }
      rerenderCategoryPanel(container, cat, previewLimit, yearList, ranking, scope, options);
    }
  });
}

function renderTopPicksSection(data, config) {
  const {
    scope,
    sectionId,
    containerId,
    metaId,
    noteId,
    headingId,
    headingFallback,
    mixedSources,
    highlightConference,
    dense = false,
  } = config;

  const section = document.getElementById(sectionId);
  const container = document.getElementById(containerId);
  const meta = document.getElementById(metaId);
  const note = document.getElementById(noteId);
  if (!section || !container || !meta) return;

  const categories = data?.categories || [];
  const hasPicks = categories.some((c) => (c.picks?.length || c.all_picks?.length));

  if (!hasPicks) {
    container.innerHTML = '<p class="empty empty-compact">No papers for this source.</p>';
    meta.textContent = "No matches";
    if (note) note.textContent = "";
    return false;
  }

  section.hidden = false;
  const period = data.period_label || data.month_label || "";
  const previewLimit = topPreviewLimit(data);
  const availableYears = sortedUniqueYears(defaultFilterYears(data));
  const ranking = data.ranking || {};
  const options = { highlightConference, mixedSources };
  const defaultYears = new Set(availableYears);

  const matched = categories.reduce(
    (n, c) => n + (c.all_picks?.length ?? c.picks?.length ?? 0),
    0
  );
  let shown = 0;
  let confShown = 0;
  for (const cat of categories) {
    const state = initPanelState(scope, cat.id, availableYears);
    const visible = picksForCategoryPanel(cat, state, previewLimit, ranking, mixedSources);
    shown += visible.length;
    confShown += countConferencePicks(visible);
  }

  const built = data.generated_at ? ` | updated ${formatGeneratedAt(data.generated_at)}` : "";
  if (highlightConference) {
    meta.textContent = `${period} | ${categories.length} areas | ${shown} published shown (${matched} total)${built}`;
  } else if (mixedSources) {
    meta.textContent = `${period} | ${categories.length} areas | ${shown} shown (${confShown} conference, ${matched} total)${built}`;
  } else {
    meta.textContent = `${period} | ${categories.length} areas | ${shown} arXiv shown (${matched} total)${built}`;
  }
  if (note) note.textContent = data.note || "";

  container.className = dense
    ? "top-categories top-categories-dense"
    : "top-categories";

  container.innerHTML = categories
    .map((cat) => {
      const state = initPanelState(scope, cat.id, availableYears);
      return renderCategoryPanel(
        cat,
        state,
        previewLimit,
        availableYears,
        ranking,
        scope,
        options
      );
    })
    .join("");
  topCategoriesCtxByScope.set(scope, {
    categories,
    previewLimit,
    availableYears,
    ranking,
    options,
  });
  wireTopCategoryInteractions(container, scope);
  return true;
}

function topPicksModeConfig(mode) {
  if (mode === "published") {
    return {
      scope: "published",
      sectionId: "top-picks-section",
      containerId: "top-picks-categories",
      metaId: "top-picks-meta",
      noteId: "top-picks-note",
      mixedSources: false,
      highlightConference: true,
      dense: true,
    };
  }
  return {
    scope: "arxiv",
    sectionId: "top-picks-section",
    containerId: "top-picks-categories",
    metaId: "top-picks-meta",
    noteId: "top-picks-note",
    mixedSources: false,
    highlightConference: false,
    dense: true,
  };
}

function updateTopPicksModeUi(mode) {
  const section = document.getElementById("top-picks-section");
  const panel = document.getElementById("top-picks-categories");
  document.querySelectorAll(".top-picks-mode-btn").forEach((btn) => {
    const active = btn.dataset.mode === mode;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
  if (section) {
    section.classList.toggle("top-hub--arxiv", mode === "arxiv");
    section.classList.toggle("top-hub--published", mode === "published");
  }
  if (panel) {
    panel.setAttribute(
      "aria-labelledby",
      mode === "published" ? "top-picks-mode-published" : "top-picks-mode-arxiv"
    );
  }
}

function topPicksHashMode() {
  const raw = (location.hash || "").replace(/^#/, "");
  if (raw === "top-picks-arxiv") return "arxiv";
  if (raw === "top-picks-published" || raw === "top-picks-section") return "published";
  return null;
}

function syncTopPicksHash(mode) {
  const next = `#top-picks-${mode}`;
  if (location.hash !== next) history.replaceState(null, "", next);
}

function setTopPicksMode(mode) {
  if (!topPicksCache[mode]) return;
  topPicksMode = mode;
  updateTopPicksModeUi(mode);
  renderTopPicksSection(topPicksCache[mode], topPicksModeConfig(mode));
  syncTopPicksHash(mode);
}

function wireTopPicksModeSwitcher() {
  if (topPicksModeWired) return;
  const bar = document.getElementById("top-picks-mode");
  if (!bar) return;
  topPicksModeWired = true;
  bar.addEventListener("click", (e) => {
    const btn = e.target.closest(".top-picks-mode-btn");
    if (!btn || !bar.contains(btn)) return;
    const mode = btn.dataset.mode;
    if (mode && topPicksCache[mode]) setTopPicksMode(mode);
  });
}

function categoryHasPicks(data) {
  return data?.categories?.some((c) => c.picks?.length || c.all_picks?.length);
}

function initTopPicks(arxivData, publishedData) {
  const section = document.getElementById("top-picks-section");
  const meta = document.getElementById("top-picks-meta");
  const container = document.getElementById("top-picks-categories");
  topPicksCache.arxiv = arxivData;
  topPicksCache.published = publishedData;

  const hasArxiv = categoryHasPicks(arxivData);
  const hasPublished = categoryHasPicks(publishedData);

  if (!hasArxiv && !hasPublished) {
    if (section) section.hidden = false;
    wireTopPicksModeSwitcher();
    if (meta) {
      meta.textContent = arxivData || publishedData ? "No papers matched" : "Could not load picks";
    }
    if (container) {
      container.innerHTML =
        '<p class="empty empty-compact">No arXiv or published picks for the selected years. Run <code>publish.sh</code> or <code>build_top_monthly.py</code> after refreshing <code>arxiv-recent.json</code>.</p>';
    }
    const arxivBtn = document.getElementById("top-picks-mode-arxiv");
    const publishedBtn = document.getElementById("top-picks-mode-published");
    if (arxivBtn) arxivBtn.disabled = true;
    if (publishedBtn) publishedBtn.disabled = true;
    return;
  }

  if (section) section.hidden = false;
  wireTopPicksModeSwitcher();

  const arxivBtn = document.getElementById("top-picks-mode-arxiv");
  const publishedBtn = document.getElementById("top-picks-mode-published");
  if (arxivBtn) {
    arxivBtn.disabled = !hasArxiv;
    arxivBtn.title = hasArxiv
      ? ""
      : "No arXiv picks in data/top-monthly.json — rebuild after crawl_arxiv_recent.py";
  }
  if (publishedBtn) publishedBtn.disabled = !hasPublished;

  if (hasPublished) setTopPicksMode("published");
  else if (hasArxiv) setTopPicksMode("arxiv");

  const fromHash = topPicksHashMode();
  if (fromHash === "arxiv" && hasArxiv) setTopPicksMode("arxiv");
  else if (fromHash === "published" && hasPublished) setTopPicksMode("published");
}

async function loadTopMonthly() {
  try {
    const res = await fetch(`data/top-monthly.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function loadTopPublished() {
  try {
    const res = await fetch(`data/top-published.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}


function dayMs(iso) {
  return new Date(`${iso}T12:00:00Z`).getTime();
}

function timelinePercent(iso, rangeStart, rangeEnd) {
  const start = dayMs(rangeStart);
  const end = dayMs(rangeEnd);
  const t = dayMs(iso);
  if (end <= start) return 0;
  return Math.max(0, Math.min(100, ((t - start) / (end - start)) * 100));
}

const TIMELINE_RAIL_LABELS = {
  "USENIX Security": "Sec",
  "USENIX ATC": "ATC",
};

function timelineRailLabel(ev) {
  return ev.rail_label || TIMELINE_RAIL_LABELS[ev.short_name] || ev.short_name;
}

/** Stagger marker labels onto two rows when venues are close on the rail. */
function layoutTimelineMarkers(events, rangeStart, rangeEnd) {
  const MIN_GAP = 4.5;
  const items = events
    .map((ev) => ({
      ev,
      pct: timelinePercent(ev.event_start, rangeStart, rangeEnd),
      label: timelineRailLabel(ev),
      row: 0,
    }))
    .sort((a, b) => a.pct - b.pct);

  let prevPct = -Infinity;
  let prevRow = 0;
  for (const item of items) {
    if (item.pct - prevPct < MIN_GAP) {
      item.row = prevRow === 0 ? 1 : 0;
    }
    prevPct = item.pct;
    prevRow = item.row;
  }
  return items;
}

function formatEventRange(start, end) {
  const s = formatDate(start);
  if (!end || end === start) return s;
  const e = formatDate(end);
  return s === e ? s : `${s} - ${e}`;
}

function renderTimelineEventCard(ev, today) {
  const status = eventStatusUtc8(ev.event_start, ev.event_end, today);
  const statusLabel =
    status === "past" ? "Past" : status === "in_progress" ? "In progress" : "Upcoming";
  const href = ev.conference_id ? `conference.html?id=${encodeURIComponent(ev.conference_id)}` : "";
  const titleInner = href
    ? `<a href="${escapeHtml(href)}">${escapeHtml(ev.short_name)}</a>`
    : escapeHtml(ev.short_name);
  const dblpBadge = ev.in_dblp
    ? `<span class="timeline-badge timeline-badge--dblp">In hub</span>`
    : `<span class="timeline-badge timeline-badge--pending">Proceedings pending</span>`;
  const papers =
    ev.paper_count != null ? `<span class="timeline-papers">${ev.paper_count} papers</span>` : "";
  const loc = ev.location ? `<span class="timeline-location">${escapeHtml(ev.location)}</span>` : "";

  return `
    <li class="timeline-event timeline-event--${escapeHtml(status)}" data-slug="${escapeHtml(ev.slug)}">
      <div class="timeline-event-head">
        <h3 class="timeline-event-name">${titleInner}</h3>
        <span class="timeline-event-status">${statusLabel}</span>
      </div>
      <p class="timeline-event-dates">
        <time datetime="${escapeHtml(ev.event_start)}">${escapeHtml(formatEventRange(ev.event_start, ev.event_end))}</time>
        ${loc}
      </p>
      <div class="timeline-event-meta">${dblpBadge}${papers}</div>
    </li>
  `;
}

function renderTimelinePastChips(events) {
  if (!events.length) return "";
  const inHub = events.filter((ev) => ev.in_dblp).length;
  const meta =
    inHub === events.length
      ? `${events.length} completed · proceedings in hub`
      : `${events.length} completed · ${inHub} in hub`;
  const chips = events
    .map((ev) => {
      const label = timelineRailLabel(ev);
      const title = `${ev.short_name}: ${formatEventRange(ev.event_start, ev.event_end)}`;
      const href = ev.conference_id
        ? `conference.html?id=${encodeURIComponent(ev.conference_id)}`
        : "";
      const inner = `
        <span class="timeline-past-chip-name">${escapeHtml(label)}</span>
        <span class="timeline-past-chip-dates">${escapeHtml(formatEventRange(ev.event_start, ev.event_end))}</span>
      `;
      if (href) {
        return `
          <a class="timeline-past-chip" href="${escapeHtml(href)}" data-slug="${escapeHtml(ev.slug)}" title="${escapeHtml(title)}">
            ${inner}
          </a>
        `;
      }
      return `
        <button type="button" class="timeline-past-chip" data-slug="${escapeHtml(ev.slug)}" title="${escapeHtml(title)}">
          ${inner}
        </button>
      `;
    })
    .join("");

  return `
    <section class="timeline-block timeline-block--past" aria-label="Past conferences">
      <header class="timeline-block-head">
        <h3 class="timeline-block-title">Past conferences</h3>
        <p class="timeline-block-meta">${escapeHtml(meta)}</p>
      </header>
      <div class="timeline-past-chips">${chips}</div>
    </section>
  `;
}

function renderTimelineUpcomingGrid(events, today) {
  if (!events.length) {
    return `
      <section class="timeline-block timeline-block--upcoming" aria-label="Upcoming conferences">
        <header class="timeline-block-head">
          <h3 class="timeline-block-title">Upcoming conferences</h3>
        </header>
        <p class="empty empty-compact">No upcoming venues on the calendar.</p>
      </section>
    `;
  }

  const next = events[0];
  const nextDate = formatDate(next.event_start);
  const cards = events.map((ev) => renderTimelineEventCard(ev, today)).join("");

  return `
    <section class="timeline-block timeline-block--upcoming" aria-label="Upcoming conferences">
      <header class="timeline-block-head">
        <h3 class="timeline-block-title">Upcoming conferences</h3>
        <p class="timeline-block-meta">Next: ${escapeHtml(next.short_name)} · ${escapeHtml(nextDate)}</p>
      </header>
      <ol class="timeline-events timeline-events--grid">${cards}</ol>
    </section>
  `;
}

function renderConferenceTimeline(data) {
  const section = document.getElementById("timeline-section");
  const railWrap = document.getElementById("timeline-rail-wrap");
  const eventsEl = document.getElementById("timeline-events");
  const meta = document.getElementById("timeline-meta");
  const note = document.getElementById("timeline-note");
  if (!section || !railWrap || !eventsEl) return;

  const events = data?.events || [];
  if (!events.length) {
    section.hidden = true;
    return;
  }

  section.hidden = false;
  const year = data.year || new Date().getFullYear();
  const rangeStart = data.range_start || `${year}-01-01`;
  const rangeEnd = data.range_end || `${year}-12-31`;
  const today = todayIsoUtc8();
  const todayMonth = today.slice(5, 7);
  const todayPct = timelinePercent(today, rangeStart, rangeEnd);

  const inDblp = events.filter((e) => e.in_dblp).length;
  const pastEvents = events.filter((ev) => eventStatusUtc8(ev.event_start, ev.event_end, today) === "past");
  const upcomingEvents = events.filter((ev) => eventStatusUtc8(ev.event_start, ev.event_end, today) !== "past");
  const built = data.generated_at ? ` | data ${formatGeneratedAt(data.generated_at)}` : "";
  meta.textContent = `Today: ${formatDateUtc8(`${today}T12:00:00Z`)} (UTC+8) | ${pastEvents.length} past · ${upcomingEvents.length} upcoming | ${inDblp} in hub${built}`;
  note.textContent = data.note || "";

  const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    .map((label, i) => {
      const monthNum = String(i + 1).padStart(2, "0");
      const monthStart = `${year}-${monthNum}-01`;
      const left = timelinePercent(monthStart, rangeStart, rangeEnd);
      const currentClass = monthNum === todayMonth ? " timeline-month--current" : "";
      return `<span class="timeline-month${currentClass}" style="left:${left}%">${label}</span>`;
    })
    .join("");

  const markers = layoutTimelineMarkers(events, rangeStart, rangeEnd)
    .map(({ ev, pct, label, row }) => {
      const status = eventStatusUtc8(ev.event_start, ev.event_end, today);
      const dblp = ev.in_dblp ? "timeline-marker--dblp" : "";
      const rowClass = row === 1 ? " timeline-marker--row-1" : "";
      const title = `${ev.short_name}: ${formatEventRange(ev.event_start, ev.event_end)}`;
      return `
        <button
          type="button"
          class="timeline-marker timeline-marker--${escapeHtml(status)} ${dblp}${rowClass}"
          style="left:${pct}%"
          title="${escapeHtml(title)}"
          data-slug="${escapeHtml(ev.slug)}"
          aria-label="${escapeHtml(title)}"
        >
          <span class="timeline-marker-dot" aria-hidden="true"></span>
          <span class="timeline-marker-label">${escapeHtml(label)}</span>
        </button>
      `;
    })
    .join("");

  railWrap.innerHTML = `
    <div class="timeline-rail" role="img" aria-label="2026 conference schedule">
      <div class="timeline-track" aria-hidden="true">
        <div class="timeline-track-past" style="width:${todayPct}%"></div>
        <div class="timeline-track-upcoming" style="left:${todayPct}%;width:${100 - todayPct}%"></div>
      </div>
      <div class="timeline-today" style="left:${todayPct}%" aria-hidden="true">
        <span class="timeline-today-label">Today</span>
        <span class="timeline-today-pin"></span>
      </div>
      <div class="timeline-markers">${markers}</div>
      <div class="timeline-months" aria-hidden="true">${monthLabels}</div>
    </div>
  `;

  eventsEl.innerHTML = `
    <div class="timeline-events-stack">
      ${renderTimelinePastChips(pastEvents)}
      <hr class="timeline-divider" aria-hidden="true" />
      ${renderTimelineUpcomingGrid(upcomingEvents, today)}
    </div>
  `;

  railWrap.querySelectorAll(".timeline-marker").forEach((btn) => {
    btn.addEventListener("click", () => {
      const slug = btn.dataset.slug;
      const row = eventsEl.querySelector(
        `.timeline-event[data-slug="${CSS.escape(slug)}"], .timeline-past-chip[data-slug="${CSS.escape(slug)}"]`
      );
      row?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "nearest",
      });
      row?.classList.add("timeline-event--focus");
      setTimeout(() => row?.classList.remove("timeline-event--focus"), 1200);
    });
  });
}

async function loadConferenceTimeline() {
  try {
    const res = await fetch(`data/conference-timeline.json?ts=${Date.now()}`, { cache: "no-store" });
    if (res.ok) {
      const live = await res.json();
      if (live?.events?.length) return live;
    }
  } catch {
    /* use bundled fallback */
  }
  if (bundledTimeline?.events?.length) return bundledTimeline;
  return null;
}


function renderBroadcastCard(pick) {
  const url = pick.abs_url || "#";
  const authors = escapeHtml((pick.authors || []).slice(0, 3).join(", "));
  const more = (pick.authors || []).length > 3 ? ` +${pick.authors.length - 3}` : "";
  const feed = escapeHtml(pick.source_feed || "arXiv");
  const areaBadge = pick.category_label
    ? `<span class="broadcast-area" title="Best-matching area">${escapeHtml(pick.category_label)}</span>`
    : "";
  const tags = (pick.matched_tags || [])
    .slice(0, 3)
    .map((tag) => `<span class="broadcast-tag">${escapeHtml(tag)}</span>`)
    .join("");
  const pdf = pick.pdf_url
    ? `<a href="${escapeHtml(pick.pdf_url)}" target="_blank" rel="noopener">PDF</a>`
    : "";
  const date = pick.published
    ? `<time class="broadcast-date" datetime="${escapeHtml(pick.published)}">${escapeHtml(formatDateUtc8(pick.published))} UTC+8</time>`
    : "";
  const abstract = (pick.abstract || "").trim()
    ? `<p class="broadcast-abstract">${escapeHtml(pick.abstract.trim())}</p>`
    : "";

  return `
    <li class="broadcast-card">
      <span class="broadcast-rank" aria-hidden="true">${pick.rank}</span>
      <div class="broadcast-card-body">
        <div class="broadcast-card-head">
          <span class="badge badge-arxiv">${feed}</span>
          ${areaBadge}
          ${date}
        </div>
        <h3 class="broadcast-title">
          <a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(pick.title)}</a>
        </h3>
        <p class="broadcast-authors">${authors}${more}</p>
        ${abstract}
        ${tags ? `<div class="broadcast-tags">${tags}</div>` : ""}
        <div class="top-links meta meta-compact">
          <a href="${escapeHtml(url)}" target="_blank" rel="noopener">arXiv</a>
          ${pdf}
        </div>
      </div>
    </li>
  `;
}

function renderTodayBroadcast(data) {
  const section = document.getElementById("broadcast-section");
  const list = document.getElementById("broadcast-list");
  const meta = document.getElementById("broadcast-meta");
  const note = document.getElementById("broadcast-note");
  if (!section || !list) return;

  const payload = data && typeof data === "object" ? data : {};
  const previewLimit = payload.preview_limit ?? payload.picks?.length ?? 3;
  const allPicks =
    payload.all_picks?.length > 0
      ? payload.all_picks
      : payload.picks?.length
        ? payload.picks
        : [];
  const dateLabel = payload.date_label || "Recent";
  const totalCount = payload.total_count ?? allPicks.length;
  let expanded = false;

  let actions = section.querySelector(".broadcast-actions");
  if (!actions) {
    actions = document.createElement("div");
    actions.className = "broadcast-actions";
    actions.innerHTML =
      '<button type="button" class="broadcast-more-btn top-more-btn" id="broadcast-more-btn" hidden></button>';
    list.after(actions);
  }
  const moreBtn = actions.querySelector("#broadcast-more-btn");

  section.hidden = false;
  const built = payload.generated_at ? ` | updated ${formatGeneratedAtUtc8(payload.generated_at)}` : "";

  function updateMeta(shownCount) {
    if (!allPicks.length) {
      meta.textContent = `No recent matches (UTC+8)${built}`;
      return;
    }
    if (totalCount > previewLimit) {
      meta.textContent = `${dateLabel} | showing ${shownCount} of ${totalCount} papers${built}`;
    } else {
      meta.textContent = `${dateLabel} | ${totalCount} paper${totalCount === 1 ? "" : "s"}${built}`;
    }
  }

  function paintList() {
    const shown = expanded ? allPicks : allPicks.slice(0, previewLimit);
    list.innerHTML = shown.map((p) => renderBroadcastCard(p)).join("");
    updateMeta(shown.length);

    const hasMore = totalCount > previewLimit;
    if (!moreBtn) return;
    if (!hasMore) {
      moreBtn.hidden = true;
      return;
    }
    moreBtn.hidden = false;
    moreBtn.textContent = expanded ? "Show less" : `More (${totalCount})`;
    moreBtn.setAttribute("aria-expanded", expanded ? "true" : "false");
  }

  if (!allPicks.length) {
    list.innerHTML = '<p class="empty empty-compact">No strong papers for the recent day (UTC+8).</p>';
    note.textContent = payload.pool_note || payload.note || "";
    if (moreBtn) moreBtn.hidden = true;
    updateMeta(0);
    return;
  }

  note.textContent = payload.note || "";
  paintList();

  if (moreBtn && !moreBtn.dataset.wired) {
    moreBtn.dataset.wired = "1";
    moreBtn.addEventListener("click", () => {
      expanded = !expanded;
      paintList();
      if (expanded) {
        moreBtn.scrollIntoView({
          behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "auto"
            : "smooth",
          block: "nearest",
        });
      }
    });
  }
}

async function loadTodayBroadcast() {
  try {
    const res = await fetch(`data/today-broadcast.json?ts=${Date.now()}`, { cache: "no-store" });
    if (res.ok) {
      const live = await res.json();
      if (live && typeof live === "object") {
        console.info("[papers-hub] broadcast:", live.generated_at || live.date_label || "(empty)");
        return live;
      }
    } else {
      console.warn("[papers-hub] broadcast JSON HTTP", res.status, "— using bundled fallback");
    }
  } catch (err) {
    console.warn("[papers-hub] broadcast fetch failed — using bundled fallback", err);
  }
  if (bundledBroadcast && typeof bundledBroadcast === "object") {
    console.info("[papers-hub] broadcast bundled:", bundledBroadcast.generated_at);
    return bundledBroadcast;
  }
  return { date_label: "Recent", picks: [], all_picks: [], note: "" };
}

async function loadConferences() {
  const res = await fetch(`data/conferences.json?ts=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Could not load conference manifest");
  const manifest = await res.json();
  return manifest.conferences || [];
}

async function main() {
  const confSearch = document.getElementById("conf-search");
  const hub = await loadHubConfig();
  applyHubBranding(hub);
  initViewsWidget({ apiUrl: hub?.views_api_url });

  const [timelineRes, broadcastRes, arxivRes, publishedRes, confRes] = await Promise.allSettled([
    loadConferenceTimeline(),
    loadTodayBroadcast(),
    loadTopMonthly(),
    loadTopPublished(),
    loadConferences(),
  ]);

  if (timelineRes.status === "fulfilled") renderConferenceTimeline(timelineRes.value);
  if (broadcastRes.status === "fulfilled") renderTodayBroadcast(broadcastRes.value);
  initTopPicks(
    arxivRes.status === "fulfilled" ? arxivRes.value : null,
    publishedRes.status === "fulfilled" ? publishedRes.value : null
  );

  if (confRes.status === "fulfilled") {
    const conferences = confRes.value;
    setConferenceMeta(conferences);
    const updateConf = () => renderConferences(conferences, confSearch.value);
    confSearch.addEventListener("input", updateConf);
    updateConf();
  } else {
    document.getElementById("conference-meta").textContent = "Failed to load proceedings index";
    document.getElementById("latest-grid").innerHTML =
      '<p class="empty empty-compact">Could not load conference list.</p>';
    document.getElementById("venue-list").innerHTML = "";
  }
}

main().catch((err) => {
  const picksSection = document.getElementById("top-picks-section");
  if (picksSection) picksSection.hidden = true;
  const topCat = document.getElementById("top-picks-categories");
  if (topCat) topCat.innerHTML = `<p class="empty empty-compact">${escapeHtml(String(err))}</p>`;
  document.getElementById("latest-grid").innerHTML =
    `<p class="empty empty-compact">${escapeHtml(String(err))}</p>`;
  document.getElementById("venue-list").innerHTML =
    `<p class="empty empty-compact">${escapeHtml(String(err))}</p>`;
  const broadcastSection = document.getElementById("broadcast-section");
  if (broadcastSection) broadcastSection.hidden = true;
  const timelineSection = document.getElementById("timeline-section");
  if (timelineSection) timelineSection.hidden = true;
});
