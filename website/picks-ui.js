import { escapeHtml, formatTopArxivBadge } from "./shared.js";

export function formatPickDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function tagBadges(tags, limit = 4) {
  if (!tags?.length) return "";
  return tags
    .slice(0, limit)
    .map((t) => `<span class="tag">${escapeHtml(t)}</span>`)
    .join("");
}

export function renderPickRow(pick, { highlightConference = false } = {}) {
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

  const rawScore = pick.category_score ?? 0;
  const displayScore = pick.display_score ?? rawScore;
  const boost = pick.score_boost ?? 0;
  let scoreAside = "";
  if (pick.category_score != null) {
    if (highlightConference && pick.source === "conference" && boost > 0) {
      scoreAside = `<aside class="top-pick-aside top-pick-aside--published" aria-label="Relevance score ${displayScore}, published paper boost">
          <span class="top-score-label">Score</span>
          <span class="top-score top-score--published" title="Keyword ${rawScore} + ${boost} peer-reviewed boost">${displayScore}</span>
          <span class="top-score-breakdown">${rawScore}+${boost}</span>
        </aside>`;
    } else {
      scoreAside = `<aside class="top-pick-aside" aria-label="Relevance score ${rawScore}">
          <span class="top-score-label">Score</span>
          <span class="top-score">${rawScore}</span>
        </aside>`;
    }
  }

  const publishedClass =
    highlightConference && pick.source === "conference" ? " top-pick--published" : "";

  return `
    <li class="top-pick top-pick-rich${publishedClass}">
      <span class="top-rank" aria-hidden="true">${pick.rank}</span>
      <div class="top-pick-main">
        <div class="top-pick-head">
          <span class="badge badge-${escapeHtml(pick.source)}">${escapeHtml(sourceLabel)}</span>
          ${feedMeta}
          ${
            pick.published
              ? `<time class="top-date" datetime="${escapeHtml(pick.published)}">${escapeHtml(formatPickDate(pick.published))}</time>`
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

export function pickCalendarYear(pick) {
  if (pick?.year) return Number(pick.year);
  if (pick?.published) {
    const d = new Date(pick.published);
    if (!Number.isNaN(d.getTime())) return d.getFullYear();
  }
  return null;
}

export function sortedUniqueYears(years) {
  return [...new Set(years.filter((y) => Number.isFinite(y)))].sort((a, b) => a - b);
}

export function filterPicksByYears(picks, selectedYears) {
  const years = selectedYears instanceof Set ? selectedYears : new Set(selectedYears);
  return picks.filter((p) => {
    const y = pickCalendarYear(p);
    return y === null || years.has(y);
  });
}

export function withDisplayRanks(picks) {
  return picks.map((p, i) => ({ ...p, rank: i + 1 }));
}

export function areaPicksPageUrl(scope, catId, selectedYears) {
  const mode = scope === "published" ? "published" : "arxiv";
  const years = sortedUniqueYears([...selectedYears]).join(",");
  const params = new URLSearchParams({ mode, area: catId });
  if (years) params.set("years", years);
  return `area-picks.html?${params.toString()}`;
}
