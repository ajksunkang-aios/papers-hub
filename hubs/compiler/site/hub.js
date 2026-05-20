import {
  escapeHtml,
  formatDateUtc8,
  formatGeneratedAt,
  formatGeneratedAtUtc8,
  formatTopArxivBadge,
} from "./shared.js";
import { todayBroadcast as bundledBroadcast } from "./today-broadcast-data.js";
import { conferenceTimeline as bundledTimeline } from "./conference-timeline-data.js";

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
  setHeading("top-heading", "top_picks");
  setHeading("conf-hub-heading", "conferences");

  const broadcastTagline = document.querySelector(".broadcast-tagline");
  if (broadcastTagline && hub.tagline) {
    const tz = hub.tagline_timezone ? ` (${hub.tagline_timezone})` : "";
    broadcastTagline.innerHTML = `${escapeHtml(hub.tagline)} <span class="broadcast-utc">${escapeHtml(tz)}</span>`;
  }

  const timelineSection = document.getElementById("timeline-section");
  if (timelineSection && sections.timeline?.enabled === false) timelineSection.hidden = true;
  const broadcastSection = document.getElementById("broadcast-section");
  if (broadcastSection && sections.broadcast?.enabled === false) broadcastSection.hidden = true;
  const topSection = document.getElementById("top-monthly-section");
  if (topSection && sections.top_picks?.enabled === false) topSection.hidden = true;
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

function tagBadges(tags, limit = 4) {
  if (!tags?.length) return "";
  return tags
    .slice(0, limit)
    .map((t) => `<span class="tag">${escapeHtml(t)}</span>`)
    .join("");
}

function renderPickRow(pick) {
  const url = pick.paper_url || pick.abs_url || pick.dblp_url || "#";
  const authorList = pick.authors || [];
  const authors = escapeHtml(authorList.slice(0, 6).join(", "));
  const more = authorList.length > 6 ? ` +${authorList.length - 6}` : "";
  const sourceLabel =
    pick.source === "conference"
      ? `${pick.venue} ${pick.year}`
      : formatTopArxivBadge(pick);
  const confLink = pick.conference_id
    ? `<a href="conference.html?id=${encodeURIComponent(pick.conference_id)}">Proceedings</a>`
    : "";
  const pdf = pick.pdf_url
    ? `<a href="${escapeHtml(pick.pdf_url)}" target="_blank" rel="noopener">PDF</a>`
    : "";
  const dblp =
    pick.dblp_url && pick.source === "conference"
      ? `<a href="${escapeHtml(pick.dblp_url)}" target="_blank" rel="noopener">dblp</a>`
      : "";
  const tags = pick.matched_tags || pick.tags || [];
  const feedMeta =
    pick.source === "arxiv" && (pick.source_feed || pick.primary_category)
      ? `<span class="top-feed">${escapeHtml(pick.source_feed || pick.primary_category)}</span>`
      : "";
  const signals =
    tags.length > 0
      ? `<p class="top-why"><span class="top-why-label">Signals</span>${tags.map((t) => escapeHtml(t)).join(" | ")}</p>`
      : "";
  const scoreAside =
    pick.category_score != null
      ? `<aside class="top-pick-aside" aria-label="Relevance score ${pick.category_score}">
          <span class="top-score-label">Score</span>
          <span class="top-score">${pick.category_score}</span>
        </aside>`
      : "";

  return `
    <li class="top-pick top-pick-rich">
      <span class="top-rank" aria-hidden="true">${pick.rank}</span>
      <div class="top-pick-main">
        <div class="top-pick-head">
          <span class="badge badge-${escapeHtml(pick.source)}">${escapeHtml(sourceLabel)}</span>
          ${feedMeta}
          ${
            pick.published
              ? `<time class="top-date" datetime="${escapeHtml(pick.published)}">${escapeHtml(formatDate(pick.published))}</time>`
              : pick.year
                ? `<span class="top-date top-date-conf">${escapeHtml(String(pick.year))} proceedings</span>`
                : ""
          }
        </div>
        <h3 class="top-title">
          <a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(pick.title)}</a>
        </h3>
        <p class="top-authors">${authors}${more}</p>
        <div class="top-tags">${tagBadges(tags, 6)}</div>
        ${signals}
        <div class="top-links meta meta-compact">
          <a href="${escapeHtml(url)}" target="_blank" rel="noopener">Paper</a>
          ${pdf}
          ${dblp}
          ${confLink}
        </div>
      </div>
      ${scoreAside}
    </li>
  `;
}


const TOP_PREVIEW_DEFAULT = 5;
const topPanelState = new Map();
let topCategoriesCtx = null;

function topPreviewLimit(data) {
  return data?.preview_limit ?? TOP_PREVIEW_DEFAULT;
}

let AREA_FILTER_YEARS = [2024, 2025, 2026];

function defaultFilterYears(data) {
  const fromData = Array.isArray(data?.years) ? data.years.map(Number) : [];
  const merged = sortedUniqueYears([...AREA_FILTER_YEARS, ...fromData]);
  return merged.length ? merged : [...AREA_FILTER_YEARS];
}

function sortedUniqueYears(years) {
  return [...new Set(years.filter((y) => Number.isFinite(y)))].sort((a, b) => a - b);
}

function pickCalendarYear(pick) {
  if (pick?.year) return Number(pick.year);
  if (pick?.published) {
    const d = new Date(pick.published);
    if (!Number.isNaN(d.getTime())) return d.getFullYear();
  }
  return null;
}

function filterPicksByYears(picks, selectedYears) {
  const years = selectedYears instanceof Set ? selectedYears : new Set(selectedYears);
  return picks.filter((p) => {
    const y = pickCalendarYear(p);
    return y === null || years.has(y);
  });
}

function withDisplayRanks(picks) {
  return picks.map((p, i) => ({ ...p, rank: i + 1 }));
}

function initPanelState(catId, defaultYears) {
  const years = sortedUniqueYears(defaultYears);
  if (!topPanelState.has(catId)) {
    topPanelState.set(catId, {
      expanded: false,
      years: new Set(years),
    });
  }
  return topPanelState.get(catId);
}

function renderYearFilters(catId, availableYears, selectedYears) {
  const years = sortedUniqueYears(availableYears);
  return `
    <div class="top-year-filters" role="group" aria-label="Filter by year">
      <span class="top-year-label">Year</span>
      ${years
        .map((year) => {
          const active = selectedYears.has(year);
          return `<button type="button" class="top-year-btn${active ? " is-active" : ""}" data-cat-id="${escapeHtml(catId)}" data-year="${year}" aria-pressed="${active ? "true" : "false"}">${year}</button>`;
        })
        .join("")}
    </div>
  `;
}

function renderCategoryPanel(cat, state, previewLimit, availableYears) {
  const selectedYears = state.years;
  const expanded = state.expanded;
  const filtered = withDisplayRanks(
    filterPicksByYears(cat.all_picks?.length ? cat.all_picks : cat.picks || [], selectedYears)
  );
  const picks = expanded ? filtered : filtered.slice(0, previewLimit);
  const total = filtered.length;

  const list =
    picks.length === 0
      ? '<p class="empty empty-compact">No papers for the selected year(s).</p>'
      : `<ol class="top-picks-list" data-expanded="${expanded ? "true" : "false"}">${picks.map((p) => renderPickRow(p)).join("")}</ol>`;

  const moreBtn =
    total > previewLimit
      ? `<button type="button" class="top-more-btn" data-cat-id="${escapeHtml(cat.id)}" aria-expanded="${expanded ? "true" : "false"}">${expanded ? "Show less" : `More (${total})`}</button>`
      : "";

  const yearLabel = [...selectedYears].sort((a, b) => a - b).join(", ");

  return `
    <article class="top-category-panel" id="cat-${escapeHtml(cat.id)}" data-cat-id="${escapeHtml(cat.id)}">
      <header class="top-category-head">
        <h3 class="top-category-title">${escapeHtml(cat.label)}</h3>
        <span class="top-category-count" title="Years: ${escapeHtml(yearLabel)}">${expanded ? total : Math.min(previewLimit, total)} / ${total}</span>
      </header>
      ${renderYearFilters(cat.id, availableYears, selectedYears)}
      ${list}
      ${moreBtn}
    </article>
  `;
}

function rerenderCategoryPanel(container, cat, previewLimit, availableYears) {
  const state = topPanelState.get(cat.id);
  if (!state) return;
  const panel = container.querySelector(`[data-cat-id="${CSS.escape(cat.id)}"]`);
  if (!panel) return;
  panel.outerHTML = renderCategoryPanel(cat, state, previewLimit, availableYears);
}

function wireTopCategoryInteractions(container) {
  if (container.dataset.topWired === "1") return;
  container.dataset.topWired = "1";

  container.addEventListener("click", (e) => {
    const ctx = topCategoriesCtx;
    if (!ctx) return;
    const { categories, previewLimit, availableYears } = ctx;
    const yearList = sortedUniqueYears(availableYears);

    const yearBtn = e.target.closest(".top-year-btn");
    if (yearBtn && container.contains(yearBtn)) {
      e.preventDefault();
      const catId = yearBtn.dataset.catId;
      const year = Number(yearBtn.dataset.year);
      const cat = categories.find((c) => c.id === catId);
      if (!cat || !yearList.includes(year)) return;

      const state = topPanelState.get(catId);
      if (!state) return;

      if (state.years.has(year)) {
        if (state.years.size <= 1) return;
        state.years.delete(year);
      } else {
        state.years.add(year);
      }
      rerenderCategoryPanel(container, cat, previewLimit, yearList);
      return;
    }

    const moreBtn = e.target.closest(".top-more-btn");
    if (!moreBtn || !container.contains(moreBtn)) return;
    e.preventDefault();
    const catId = moreBtn.dataset.catId;
    const cat = categories.find((c) => c.id === catId);
    if (!cat) return;
    const state = topPanelState.get(catId);
    if (!state) return;
    state.expanded = !state.expanded;
    rerenderCategoryPanel(container, cat, previewLimit, yearList);
  });
}

function renderTopMonthly(data) {
  const section = document.getElementById("top-monthly-section");
  const container = document.getElementById("top-categories");
  const meta = document.getElementById("top-meta");
  const note = document.getElementById("top-note");

  const categories = data?.categories || [];
  const hasPicks = categories.some((c) => (c.picks?.length || c.all_picks?.length));

  if (!hasPicks) {
    section.hidden = true;
    return;
  }

  section.hidden = false;
  const period = data.period_label || data.month_label || "";
  const previewLimit = topPreviewLimit(data);
  const availableYears = sortedUniqueYears(defaultFilterYears(data));
  topPanelState.clear();

  const matched = categories.reduce(
    (n, c) => n + (c.all_picks?.length ?? c.picks?.length ?? 0),
    0
  );
  const shown = categories.reduce((n, c) => {
    const all = c.all_picks?.length ? c.all_picks : c.picks || [];
    const filtered = filterPicksByYears(all, new Set(availableYears));
    return n + Math.min(previewLimit, filtered.length);
  }, 0);

  const built = data.generated_at ? ` | updated ${formatGeneratedAt(data.generated_at)}` : "";
  meta.textContent = `${period} | ${categories.length} areas | ${shown} shown (${matched} total)${built}`;
  note.textContent = data.note || "";

  const heading = document.getElementById("top-heading");
  if (heading && period) {
    const base =
      hubConfig?.categories?.section_heading ||
      hubConfig?.sections?.top_picks?.title ||
      "Top picks by areas";
    heading.textContent = `${base} (${period})`;
  }

  container.className = "top-categories top-categories-dense";

  container.innerHTML = categories
    .map((cat) => {
      const state = initPanelState(cat.id, availableYears);
      return renderCategoryPanel(cat, state, previewLimit, availableYears);
    })
    .join("");
  topCategoriesCtx = { categories, previewLimit, availableYears };
  wireTopCategoryInteractions(container);
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

function formatEventRange(start, end) {
  const s = formatDate(start);
  if (!end || end === start) return s;
  const e = formatDate(end);
  return s === e ? s : `${s} - ${e}`;
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
  const today = data.today || new Date().toISOString().slice(0, 10);
  const todayPct = timelinePercent(today, rangeStart, rangeEnd);

  const inDblp = events.filter((e) => e.in_dblp).length;
  const built = data.generated_at ? ` | data ${formatGeneratedAt(data.generated_at)}` : "";
  meta.textContent = `Today: ${formatDate(today)} | ${events.length} venues | ${inDblp} in hub${built}`;
  note.textContent = data.note || "";

  const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    .map((label, i) => {
      const mid = `${year}-${String(i + 1).padStart(2, "0")}-15`;
      const left = timelinePercent(mid, rangeStart, rangeEnd);
      return `<span class="timeline-month" style="left:${left}%">${label}</span>`;
    })
    .join("");

  const markers = events
    .map((ev) => {
      const pct = timelinePercent(ev.event_start, rangeStart, rangeEnd);
      const status = ev.status || "upcoming";
      const dblp = ev.in_dblp ? "timeline-marker--dblp" : "";
      const title = `${ev.short_name}: ${formatEventRange(ev.event_start, ev.event_end)}`;
      return `
        <button
          type="button"
          class="timeline-marker timeline-marker--${escapeHtml(status)} ${dblp}"
          style="left:${pct}%"
          title="${escapeHtml(title)}"
          data-slug="${escapeHtml(ev.slug)}"
          aria-label="${escapeHtml(title)}"
        >
          <span class="timeline-marker-dot" aria-hidden="true"></span>
          <span class="timeline-marker-label">${escapeHtml(ev.short_name)}</span>
        </button>
      `;
    })
    .join("");

  railWrap.innerHTML = `
    <div class="timeline-rail" role="img" aria-label="2026 conference schedule">
      <div class="timeline-track" aria-hidden="true"></div>
      <div class="timeline-today" style="left:${todayPct}%" aria-hidden="true">
        <span class="timeline-today-label">Today</span>
        <span class="timeline-today-pin"></span>
      </div>
      <div class="timeline-markers">${markers}</div>
      <div class="timeline-months" aria-hidden="true">${monthLabels}</div>
    </div>
  `;

  eventsEl.innerHTML = events
    .map((ev) => {
      const status = ev.status || "upcoming";
      const statusLabel =
        status === "past" ? "Past" : status === "in_progress" ? "In progress" : "Upcoming";
      const href = ev.conference_id
        ? `conference.html?id=${encodeURIComponent(ev.conference_id)}`
        : "";
      const titleInner = href
        ? `<a href="${escapeHtml(href)}">${escapeHtml(ev.short_name)}</a>`
        : escapeHtml(ev.short_name);
      const dblpBadge = ev.in_dblp
        ? `<span class="timeline-badge timeline-badge--dblp">In hub</span>`
        : `<span class="timeline-badge timeline-badge--pending">Proceedings pending</span>`;
      const papers =
        ev.paper_count != null
          ? `<span class="timeline-papers">${ev.paper_count} papers</span>`
          : "";
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
    })
    .join("");

  railWrap.querySelectorAll(".timeline-marker").forEach((btn) => {
    btn.addEventListener("click", () => {
      const slug = btn.dataset.slug;
      const row = eventsEl.querySelector(`.timeline-event[data-slug="${CSS.escape(slug)}"]`);
      row?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
      row?.classList.add("timeline-event--focus");
      setTimeout(() => row?.classList.remove("timeline-event--focus"), 1200);
    });
  });
}

async function loadConferenceTimeline() {
  if (bundledTimeline?.events?.length) return bundledTimeline;
  try {
    const res = await fetch(`data/conference-timeline.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}


function renderBroadcastCard(pick) {
  const url = pick.abs_url || "#";
  const authors = escapeHtml((pick.authors || []).slice(0, 3).join(", "));
  const more = (pick.authors || []).length > 3 ? ` +${pick.authors.length - 3}` : "";
  const feed = escapeHtml(pick.source_feed || "arXiv");
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

  return `
    <li class="broadcast-card">
      <span class="broadcast-rank" aria-hidden="true">${pick.rank}</span>
      <div class="broadcast-card-body">
        <div class="broadcast-card-head">
          <span class="badge badge-arxiv">${feed}</span>
          ${date}
        </div>
        <h3 class="broadcast-title">
          <a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(pick.title)}</a>
        </h3>
        <p class="broadcast-authors">${authors}${more}</p>
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

  const picks = data?.picks || [];
  const dateLabel = data.date_label || "Recent";

  section.hidden = false;
  const built = data?.generated_at ? ` | updated ${formatGeneratedAtUtc8(data.generated_at)}` : "";
  meta.textContent =
    picks.length > 0
      ? `${dateLabel} | top ${picks.length} paper${picks.length === 1 ? "" : "s"}${built}`
      : `No recent matches (UTC+8)${built}`;

  if (!picks.length) {
    list.innerHTML = '<p class="empty empty-compact">No strong papers for the recent day (UTC+8).</p>';
    note.textContent = data.pool_note || data.note || "";
    return;
  }

  note.textContent = data.note || "";
  list.innerHTML = picks.map((p) => renderBroadcastCard(p)).join("");
}

async function loadTodayBroadcast() {
  if (bundledBroadcast?.picks?.length) return bundledBroadcast;
  const res = await fetch(`data/today-broadcast.json?ts=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
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

  const [timelineRes, broadcastRes, topRes, confRes] = await Promise.allSettled([
    loadConferenceTimeline(),
    loadTodayBroadcast(),
    loadTopMonthly(),
    loadConferences(),
  ]);

  if (timelineRes.status === "fulfilled") renderConferenceTimeline(timelineRes.value);
  if (broadcastRes.status === "fulfilled") renderTodayBroadcast(broadcastRes.value);
  if (topRes.status === "fulfilled") renderTopMonthly(topRes.value);

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
  const topSection = document.getElementById("top-monthly-section");
  if (topSection) topSection.hidden = true;
  const topCat = document.getElementById("top-categories");
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
