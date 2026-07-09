import { escapeHtml } from "./shared.js";
import { initViewsWidget } from "./views.js?v=3";

let analyticsData = null;
let selectedCountry = null;
let activeRegion = "all";

function formatPct(value) {
  return `${Math.round((Number(value) || 0) * 1000) / 10}%`;
}

function sortedCountries(data, region = "all") {
  const groups = data.region_groups || {};
  let list = (data.countries || []).filter((c) => c.code !== "XX");
  if (region !== "all") {
    const allowed = new Set(groups[region] || []);
    list = list.filter((c) => allowed.has(c.code));
  }
  return list.sort((a, b) => b.total - a.total || a.label.localeCompare(b.label));
}

function renderSummary(data) {
  const cov = data.coverage || {};
  const sourceLabel = data.data_source === "dblp" ? "dblp papers" : "papers";
  const cards = [
    ["Total papers", (cov.total_papers || 0).toLocaleString()],
    ["Countries", String((data.countries || []).filter((c) => c.code !== "XX").length)],
    ["Country resolved", formatPct(cov.resolution_rate || 0)],
    [sourceLabel, String(data.sources?.dblp || cov.total_papers || 0)],
    ["Unknown author country", String(cov.unknown || 0)],
  ];
  document.getElementById("country-summary").innerHTML = cards
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

function renderRegionFilters(data) {
  const groups = data.region_groups || {};
  const buttons = [
    `<button type="button" class="country-region-btn is-active" data-region="all">All</button>`,
    ...Object.keys(groups).map(
      (key) =>
        `<button type="button" class="country-region-btn" data-region="${escapeHtml(key)}">${escapeHtml(key)}</button>`
    ),
  ];
  const mount = document.getElementById("region-filters");
  mount.innerHTML = buttons.join("");
  mount.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-region]");
    if (!btn) return;
    activeRegion = btn.dataset.region || "all";
    mount.querySelectorAll(".country-region-btn").forEach((el) => {
      el.classList.toggle("is-active", el === btn);
    });
    renderCountryChart(analyticsData);
    renderHeatmap(analyticsData);
  });
}

function renderCountryChart(data) {
  const list = sortedCountries(data, activeRegion);
  const max = Math.max(1, ...list.map((c) => c.total));
  const mount = document.getElementById("country-rank-chart");
  mount.innerHTML = list
    .map((country) => {
      const width = Math.max(4, Math.round((country.total / max) * 100));
      const active = selectedCountry === country.code ? " is-active" : "";
      return `
        <button type="button" class="country-rank-row${active}" data-country="${escapeHtml(country.code)}">
          <span class="country-rank-label">${escapeHtml(country.label)}</span>
          <span class="country-rank-bar-wrap"><span class="country-rank-bar" style="width:${width}%"></span></span>
          <span class="country-rank-count">${country.total.toLocaleString()}</span>
        </button>
      `;
    })
    .join("");
  mount.querySelectorAll("[data-country]").forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedCountry = btn.dataset.country;
      renderCountryChart(data);
      renderCountryDetail(data, selectedCountry);
    });
  });
}

function heatColor(value, max) {
  if (!value) return "rgba(148, 163, 184, 0.15)";
  const t = Math.min(1, value / Math.max(1, max));
  const alpha = 0.18 + t * 0.72;
  return `rgba(79, 70, 229, ${alpha.toFixed(3)})`;
}

function renderHeatmap(data) {
  const labels = data.category_labels || {};
  const areaIds = Object.keys(labels);
  const list = sortedCountries(data, activeRegion).slice(0, 12);
  const matrix = data.matrix || {};
  let max = 1;
  for (const country of list) {
    for (const areaId of areaIds) {
      max = Math.max(max, matrix[country.code]?.[areaId] || 0);
    }
  }

  const header = `<tr><th scope="col">Country</th>${areaIds
    .map((id) => `<th scope="col">${escapeHtml(labels[id] || id)}</th>`)
    .join("")}</tr>`;
  const rows = list
    .map((country) => {
      const cells = areaIds
        .map((areaId) => {
          const value = matrix[country.code]?.[areaId] || 0;
          return `<td class="country-heat-cell" style="background:${heatColor(value, max)}" title="${escapeHtml(country.label)} · ${escapeHtml(labels[areaId] || areaId)}: ${value}">${value || ""}</td>`;
        })
        .join("");
      return `<tr><th scope="row">${escapeHtml(country.label)}</th>${cells}</tr>`;
    })
    .join("");

  document.getElementById("country-heatmap").innerHTML = `
    <div class="country-heatmap-scroll">
      <table class="country-heatmap-table">
        <thead>${header}</thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function paperLinks(paper) {
  const links = [];
  if (paper.dblp_url) links.push(`<a href="${escapeHtml(paper.dblp_url)}" target="_blank" rel="noopener">dblp</a>`);
  if (paper.conference_id) {
    links.push(
      `<a href="conference.html?id=${encodeURIComponent(paper.conference_id)}">Proceedings</a>`
    );
  }
  return links.join(" · ");
}

function renderCountryDetail(data, code) {
  const country = (data.countries || []).find((c) => c.code === code);
  const mount = document.getElementById("country-detail");
  if (!country) {
    mount.innerHTML = `<p class="panel-note">Country not found.</p>`;
    return;
  }

  const years = Object.entries(country.by_year || {}).sort(([a], [b]) => a.localeCompare(b));
  const maxYear = Math.max(1, ...years.map(([, count]) => count));
  const yearBars = years
    .map(([year, count]) => {
      const width = Math.max(6, Math.round((count / maxYear) * 100));
      return `
        <div class="country-year-row">
          <span>${escapeHtml(year)}</span>
          <span class="country-year-bar-wrap"><span class="country-year-bar" style="width:${width}%"></span></span>
          <span>${count}</span>
        </div>
      `;
    })
    .join("");

  const areas = Object.entries(country.areas || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([areaId, count]) => {
      const label = data.category_labels?.[areaId] || areaId;
      return `<li><span>${escapeHtml(label)}</span><strong>${count}</strong></li>`;
    })
    .join("");

  const papers = (country.top_papers || [])
    .map(
      (paper) => `
      <li class="country-paper-row">
        <a href="${escapeHtml(paper.dblp_url || "#")}" target="_blank" rel="noopener">${escapeHtml(paper.title)}</a>
        <p class="country-paper-meta">
          ${escapeHtml(paper.venue || paper.area_label || "")} · score ${paper.area_score || 0} · ${escapeHtml(String(paper.year || ""))}
          · ${escapeHtml(paper.first_author?.country_label || country.label)}
        </p>
        <p class="country-paper-links">${paperLinks(paper)}</p>
      </li>
    `
    )
    .join("");

  mount.innerHTML = `
    <div class="country-detail-head">
      <h3>${escapeHtml(country.label)} <span class="country-code">${escapeHtml(country.code)}</span></h3>
      <p class="hub-section-meta">${country.total.toLocaleString()} dblp papers</p>
    </div>
    <div class="country-detail-block">
      <h4>By year</h4>
      ${yearBars || `<p class="panel-note">No yearly data.</p>`}
    </div>
    <div class="country-detail-block">
      <h4>Top areas</h4>
      <ul class="country-area-list">${areas || `<li>No area matches</li>`}</ul>
    </div>
    <div class="country-detail-block">
      <h4>Top papers</h4>
      <ol class="country-paper-list">${papers || `<li class="panel-note">No papers.</li>`}</ol>
    </div>
  `;
}

async function loadAnalytics() {
  const res = await fetch(`data/country-analytics.json?ts=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load country analytics (${res.status})`);
  return res.json();
}

async function main() {
  initViewsWidget();
  try {
    analyticsData = await loadAnalytics();
    const sourceNote = analyticsData.data_source === "dblp" ? "dblp proceedings" : "papers";
    document.getElementById("analytics-meta").textContent = `${analyticsData.period_label || ""} · ${
      analyticsData.coverage?.total_papers || 0
    } ${sourceNote} · updated ${new Date(analyticsData.generated_at || Date.now()).toLocaleString()} · first-author country`;
    renderSummary(analyticsData);
    renderRegionFilters(analyticsData);
    renderCountryChart(analyticsData);
    renderHeatmap(analyticsData);
    const first = sortedCountries(analyticsData, activeRegion)[0];
    if (first) {
      selectedCountry = first.code;
      renderCountryChart(analyticsData);
      renderCountryDetail(analyticsData, selectedCountry);
    }
  } catch (err) {
    document.getElementById("analytics-meta").textContent = "Country analytics unavailable";
    document.getElementById("country-summary").innerHTML = `<p class="empty">${escapeHtml(String(err))}</p>`;
  }
}

main();
