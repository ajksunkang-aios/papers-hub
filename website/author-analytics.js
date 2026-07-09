import { escapeHtml } from "./shared.js";
import { initViewsWidget } from "./views.js?v=3";

let analyticsData = null;
let selectedAuthorKey = null;

function formatAuthorMeta(author) {
  const parts = [];
  if (author.country_label) parts.push(author.country_label);
  const aff = author.affiliation || (author.affiliations || [])[0];
  if (aff) parts.push(aff);
  return parts.join(" · ");
}

function authorDisplayTags(author) {
  const tags = author.display_tags?.length
    ? author.display_tags
    : author.tech_tags?.length
      ? author.tech_tags
      : author.topic_tags || [];
  return tags.slice(0, 4);
}

function topicParentLabel(data, tagLabel) {
  const topics = data.research_breakdown?.uncategorized_topics || [];
  return topics.find((row) => row.label === tagLabel)?.parent_area_label || null;
}

function mergedBreakdownRows(breakdown) {
  const areas = (breakdown.areas || []).map((row) => ({
    ...row,
    barClass: "author-area-bar",
  }));
  const topics = (breakdown.uncategorized_topics || []).map((row) => ({
    ...row,
    barClass: "author-topic-bar",
  }));
  return [...areas, ...topics].sort(
    (a, b) => b.count - a.count || String(a.label).localeCompare(String(b.label))
  );
}

function mergedAuthorBreakdown(author, data) {
  const rows = [];
  for (const area of author.primary_areas || []) {
    if (area.id === "uncategorized") continue;
    rows.push({
      label: area.label,
      count: area.count,
      barClass: "author-area-bar",
    });
  }
  for (const topic of author.uncategorized_topics || []) {
    rows.push({
      label: topic.tag,
      count: topic.count,
      parent_area_label: topicParentLabel(data, topic.tag),
      barClass: "author-topic-bar",
    });
  }
  return rows.sort((a, b) => b.count - a.count || String(a.label).localeCompare(String(b.label)));
}

function renderSummary(data) {
  const cov = data.coverage || {};
  const uncatPct = Math.round((Number(cov.uncategorized_rate) || 0) * 1000) / 10;
  const cards = [
    ["Total papers", (cov.total_papers || 0).toLocaleString()],
    ["Unique authors", (cov.unique_authors || 0).toLocaleString()],
    ["Topic-classified share", `${uncatPct}%`],
    ["Top 50 w/ country", String(cov.top_with_country || 0)],
    ["Period", data.period_label || ""],
  ];
  document.getElementById("author-summary").innerHTML = cards
    .map(
      ([label, value]) => `
      <article class="country-summary-card">
        <p class="country-summary-label">${escapeHtml(label)}</p>
        <p class="country-summary-value">${escapeHtml(value)}</p>
      </article>
    `
    )
    .join("");
}

function renderAuthorChart(data) {
  const list = data.authors || [];
  const max = Math.max(1, ...list.map((a) => a.paper_count));
  const mount = document.getElementById("author-rank-chart");
  mount.innerHTML = list
    .map((author) => {
      const width = Math.max(4, Math.round((author.paper_count / max) * 100));
      const active = selectedAuthorKey === author.key ? " is-active" : "";
      const tags = authorDisplayTags(author)
        .map((t) => `<span class="author-tag-pill">${escapeHtml(t.tag)}</span>`)
        .join("");
      const meta = formatAuthorMeta(author);
      return `
        <button type="button" class="country-rank-row author-rank-row${active}" data-author="${escapeHtml(author.key)}">
          <span class="country-rank-label">
            <span class="author-rank-num">#${author.rank}</span>
            <span class="author-rank-name-block">
              <span class="author-rank-name">${escapeHtml(author.name)}</span>
              ${meta ? `<span class="author-rank-meta">${escapeHtml(meta)}</span>` : `<span class="author-rank-meta author-rank-meta-muted">Affiliation unknown</span>`}
            </span>
          </span>
          <span class="author-rank-middle">
            <span class="country-rank-bar-wrap"><span class="country-rank-bar" style="width:${width}%"></span></span>
            <span class="author-tag-row">${tags}</span>
          </span>
          <span class="country-rank-count">${author.paper_count.toLocaleString()}</span>
        </button>
      `;
    })
    .join("");
  mount.querySelectorAll("[data-author]").forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedAuthorKey = btn.dataset.author;
      renderAuthorChart(data);
      renderAuthorDetail(data, selectedAuthorKey);
    });
  });
}

function renderBreakdownRows(rows, max) {
  if (!rows.length) {
    return `<p class="panel-note">No breakdown data.</p>`;
  }
  return rows
    .map((row) => {
      const width = Math.max(6, Math.round((row.count / max) * 100));
      const parent = row.parent_area_label
        ? `<span class="author-uncat-parent">→ ${escapeHtml(row.parent_area_label)}</span>`
        : "";
      const barClass = row.barClass || "";
      return `
        <div class="author-uncat-row">
          <span class="author-uncat-label">${escapeHtml(row.label)}${parent}</span>
          <span class="country-rank-bar-wrap"><span class="country-rank-bar ${barClass}" style="width:${width}%"></span></span>
          <span class="country-rank-count">${row.count.toLocaleString()}</span>
        </div>`;
    })
    .join("");
}

function renderResearchBreakdown(data) {
  const mount = document.getElementById("research-breakdown");
  if (!mount) return;

  const rows = mergedBreakdownRows(data.research_breakdown || {});
  const max = Math.max(1, ...rows.map((row) => row.count));

  mount.innerHTML = renderBreakdownRows(rows, max);
}

function renderAuthorDetail(data, key) {
  const author = (data.authors || []).find((a) => a.key === key);
  const mount = document.getElementById("author-detail");
  if (!author) {
    mount.innerHTML = `<p class="panel-note">Author not found.</p>`;
    return;
  }

  const breakdownRows = mergedAuthorBreakdown(author, data);
  const soft = (author.secondary_areas || [])
    .slice(0, 3)
    .map(
      (a) =>
        `<li class="author-soft-area"><span class="panel-note">↳ possible</span> <strong>${escapeHtml(a.label)}</strong> <span class="panel-note">(${a.count})</span></li>`
    )
    .join("");
  const areas = breakdownRows
    .map(
      (row) => {
        const parent = row.parent_area_label
          ? ` <span class="panel-note">(${escapeHtml(row.parent_area_label)})</span>`
          : "";
        return `<li><strong>${escapeHtml(row.label)}</strong>${parent} <span class="panel-note">(${row.count})</span></li>`;
      }
    )
    .join("");
  const tags = (author.tech_tags || [])
    .map((t) => `<span class="author-tag-pill">${escapeHtml(t.tag)} <em>${t.count}</em></span>`)
    .join("");
  const breakdownList = areas
    ? `<ul class="country-area-list">${areas}${soft ? soft : ""}</ul>`
    : soft
      ? `<ul class="country-area-list author-soft-list">${soft}</ul>`
      : `<p class="panel-note">No matches.</p>`;
  const yearBars = Object.entries(author.by_year || {})
    .map(([year, count]) => {
      const max = Math.max(...Object.values(author.by_year || { x: 1 }));
      const width = Math.max(8, Math.round((count / max) * 100));
      return `<div class="country-year-row"><span>${escapeHtml(year)}</span><span class="country-rank-bar-wrap"><span class="country-rank-bar" style="width:${width}%"></span></span><span>${count}</span></div>`;
    })
    .join("");
  const papers = (author.top_papers || [])
    .map((paper) => {
      const href = paper.dblp_url || (paper.conference_id ? `conference.html?id=${encodeURIComponent(paper.conference_id)}` : "#");
      const tagText = [...(paper.matched_tags || []), ...(paper.topic_tags || [])].slice(0, 4).join(", ");
      return `<li><a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(paper.title || "Untitled")}</a>
        <span class="panel-note">${escapeHtml(String(paper.year || ""))} · ${escapeHtml(paper.venue || "")}${tagText ? ` · ${escapeHtml(tagText)}` : ""}</span></li>`;
    })
    .join("");
  const affList = (author.affiliations || []).length
    ? author.affiliations
    : author.affiliation
      ? [author.affiliation]
      : [];
  const profileLines = [];
  if (author.country_label) {
    profileLines.push(`<p class="author-profile-line"><strong>Country</strong> ${escapeHtml(author.country_label)}</p>`);
  }
  if (affList.length) {
    profileLines.push(
      `<p class="author-profile-line"><strong>Affiliation</strong> ${affList.map((a) => escapeHtml(a)).join("<br />")}</p>`
    );
  } else {
    profileLines.push(`<p class="author-profile-line panel-note">Affiliation not found in dblp enrich data.</p>`);
  }

  mount.innerHTML = `
    <div class="country-detail-head">
      <h3>${escapeHtml(author.name)}</h3>
      <p class="country-code">${author.paper_count.toLocaleString()} papers · rank #${author.rank}</p>
      ${profileLines.join("")}
    </div>
    <div class="country-detail-block">
      <h4>Area keyword tags</h4>
      <div class="author-tag-row">${tags || `<span class="panel-note">No area keyword tags matched.</span>`}</div>
    </div>
    <div class="country-detail-block">
      <h4>Research breakdown</h4>
      ${breakdownList}
    </div>
    <div class="country-detail-block">
      <h4>By year</h4>
      ${yearBars || `<p class="panel-note">No yearly data.</p>`}
    </div>
    <div class="country-detail-block">
      <h4>Top papers</h4>
      <ol class="country-paper-list">${papers || `<li class="panel-note">No papers.</li>`}</ol>
    </div>
  `;
}

async function loadAnalytics() {
  const res = await fetch(`data/author-analytics.json?ts=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load author analytics (${res.status})`);
  return res.json();
}

async function main() {
  initViewsWidget();
  try {
    analyticsData = await loadAnalytics();
    document.getElementById("analytics-meta").textContent = `${analyticsData.period_label || ""} · ${
      analyticsData.coverage?.unique_authors || 0
    } unique authors · top ${analyticsData.coverage?.top_n || 50} · updated ${new Date(analyticsData.generated_at || Date.now()).toLocaleString()}`;
    renderSummary(analyticsData);
    renderResearchBreakdown(analyticsData);
    renderAuthorChart(analyticsData);
    const first = (analyticsData.authors || [])[0];
    if (first) {
      selectedAuthorKey = first.key;
      renderAuthorChart(analyticsData);
      renderAuthorDetail(analyticsData, selectedAuthorKey);
    }
  } catch (err) {
    document.getElementById("analytics-meta").textContent = "Author analytics unavailable";
    document.getElementById("author-summary").innerHTML = `<p class="empty">${escapeHtml(String(err))}</p>`;
  }
}

main();
