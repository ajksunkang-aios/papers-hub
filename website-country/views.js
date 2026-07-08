import { escapeHtml } from "./shared.js";

const SESSION_KEY = "papers-hub-view-hit";
let hitRecordedThisPage = false;

const ZONE_COLORS = {
  americas: "#2563eb",
  europe: "#7c3aed",
  asia: "#0891b2",
  oceania: "#059669",
  africa_me: "#ea580c",
  other: "#64748b",
};

const HIGHLIGHT_COLORS = {
  CN: "#de2910",
};

const DEFAULT_CHINA_CITIES = {
  order: ["beijing", "shanghai", "guangzhou", "shenzhen", "hangzhou"],
  labels: {
    beijing: "Beijing",
    shanghai: "Shanghai",
    guangzhou: "Guangzhou",
    shenzhen: "Shenzhen",
    hangzhou: "Hangzhou",
  },
};

function normalizeChinaCities(raw) {
  if (!raw || typeof raw !== "object") {
    return {
      order: DEFAULT_CHINA_CITIES.order,
      labels: DEFAULT_CHINA_CITIES.labels,
      counts: Object.fromEntries(DEFAULT_CHINA_CITIES.order.map((k) => [k, 0])),
    };
  }
  if (Array.isArray(raw.order)) {
    const counts = raw.counts && typeof raw.counts === "object" ? raw.counts : {};
    return {
      order: raw.order.length ? raw.order : DEFAULT_CHINA_CITIES.order,
      labels: { ...DEFAULT_CHINA_CITIES.labels, ...(raw.labels || {}) },
      counts: {
        ...Object.fromEntries(DEFAULT_CHINA_CITIES.order.map((k) => [k, 0])),
        ...counts,
      },
    };
  }
  return {
    order: DEFAULT_CHINA_CITIES.order,
    labels: DEFAULT_CHINA_CITIES.labels,
    counts: {
      ...Object.fromEntries(DEFAULT_CHINA_CITIES.order.map((k) => [k, 0])),
      ...raw,
    },
  };
}

function formatCount(n) {
  const v = Number(n) || 0;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (v >= 10_000) return `${Math.round(v / 1000)}k`;
  if (v >= 1000) return `${(v / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  return String(v);
}

function resolveApiUrl(explicit) {
  if (explicit) return explicit.replace(/\/$/, "");
  const meta = document.querySelector('meta[name="papers-hub-views-api"]')?.content?.trim();
  if (meta) return meta.replace(/\/$/, "");
  if (location.hostname === "localhost" || location.hostname === "127.0.0.1") {
    return "http://127.0.0.1:8788";
  }
  return "";
}

async function resolveApiUrlAsync(explicit) {
  const direct = resolveApiUrl(explicit);
  if (direct) return direct;
  try {
    const res = await fetch(`data/hub.json?ts=${Date.now()}`, { cache: "no-store" });
    if (res.ok) {
      const hub = await res.json();
      const fromHub = (hub.views_api_url || "").trim();
      if (fromHub) return fromHub.replace(/\/$/, "");
    }
  } catch {
    /* hub.json optional */
  }
  return resolveApiUrl("");
}

function isLocalDevApi(apiUrl) {
  try {
    const url = new URL(apiUrl);
    return (
      (url.hostname === "127.0.0.1" || url.hostname === "localhost") &&
      (url.port === "8788" || url.port === "")
    );
  } catch {
    return false;
  }
}

async function fetchLocationHint(apiUrl) {
  if (!isLocalDevApi(apiUrl)) {
    return { country: "", city: "" };
  }
  try {
    const res = await fetch("https://ipapi.co/json/", { cache: "no-store" });
    if (!res.ok) return { country: "XX", city: "" };
    const data = await res.json();
    const country = (data.country_code || "XX").trim().toUpperCase();
    return {
      country: /^[A-Z]{2}$/.test(country) ? country : "XX",
      city: (data.city || "").trim(),
    };
  } catch {
    return { country: "XX", city: "" };
  }
}

function sessionHitRecorded() {
  try {
    return sessionStorage.getItem(SESSION_KEY) === "1" || hitRecordedThisPage;
  } catch {
    return hitRecordedThisPage;
  }
}

function markSessionHitRecorded() {
  hitRecordedThisPage = true;
  try {
    sessionStorage.setItem(SESSION_KEY, "1");
  } catch {
    /* private mode / blocked storage */
  }
}

function setStatusMessage(mount, className, message) {
  mount.innerHTML = `<p class="${className}" role="status" aria-live="polite">${escapeHtml(message)}</p>`;
}

function renderChip(className, label, count, barTotal, color, title) {
  const pct = barTotal > 0 ? Math.max(2, Math.round((count / barTotal) * 100)) : 0;
  return `
    <span class="${className}" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">
      <span class="global-views-zone-dot" style="background:${color}"></span>
      <span class="global-views-zone-label">${escapeHtml(label)}</span>
      <span class="global-views-zone-count">${formatCount(count)}</span>
      <span class="global-views-zone-bar" style="width:${pct}%;background:${color}"></span>
    </span>
  `;
}

function renderZoneChip(zone, labels, zones, total) {
  const count = Number(zones[zone]) || 0;
  const label = labels[zone] || zone;
  const color = ZONE_COLORS[zone] || ZONE_COLORS.other;
  const title = `${label}: ${count.toLocaleString()} views`;
  return renderChip("global-views-zone", label, count, total, color, title);
}

function renderHighlightChip(code, label, countries, total) {
  const count = Number(countries[code]) || 0;
  const color = HIGHLIGHT_COLORS[code] || "#dc2626";
  const slug = code.toLowerCase();
  const title = `${label}: ${count.toLocaleString()} views`;
  return renderChip(
    `global-views-zone global-views-zone-highlight global-views-zone-${slug}`,
    label,
    count,
    total,
    color,
    title
  );
}

function renderChinaCityChip(cityKey, label, counts, chinaTotal) {
  const count = Number(counts[cityKey]) || 0;
  const color = HIGHLIGHT_COLORS.CN;
  const title = `${label}: ${count.toLocaleString()} views in China`;
  return renderChip(
    `global-views-zone global-views-zone-highlight global-views-zone-china-city global-views-zone-${escapeHtml(cityKey)}`,
    label,
    count,
    chinaTotal,
    color,
    title
  );
}

function renderBar(mount, data) {
  const order = data.zone_order || Object.keys(data.zones || {});
  const labels = data.zone_labels || {};
  const highlights = data.highlight_countries || { CN: "China" };
  const countries = data.countries || {};
  const chinaMeta = normalizeChinaCities(data.china_cities);
  const chinaTotal = Number(countries.CN) || 0;
  const total = Number(data.total) || 0;
  const zones = data.zones || {};

  const chips = [];

  if (highlights.CN) {
    const chinaParts = [renderHighlightChip("CN", highlights.CN, countries, total)];
    for (const cityKey of chinaMeta.order) {
      chinaParts.push(
        renderChinaCityChip(
          cityKey,
          chinaMeta.labels[cityKey] || cityKey,
          chinaMeta.counts,
          chinaTotal
        )
      );
    }
    chips.push(
      `<div class="global-views-china-group" aria-label="China region">${chinaParts.join("")}</div>`
    );
  }

  for (const zone of order) {
    chips.push(renderZoneChip(zone, labels, zones, total));
  }

  mount.innerHTML = `
    <div class="global-views-inner">
      <p class="global-views-total">
        <span class="global-views-total-value">${total.toLocaleString()}</span>
        cumulative views worldwide
      </p>
      <div class="global-views-zones" aria-label="Views by world region">${chips.join("")}</div>
    </div>
  `;
  mount.hidden = false;
}

async function recordPageHit(apiUrl) {
  if (sessionHitRecorded()) return;

  const payload = isLocalDevApi(apiUrl) ? await fetchLocationHint(apiUrl) : {};
  const res = await fetch(`${apiUrl}/hit`, {
    method: "POST",
    mode: "cors",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`hit failed: HTTP ${res.status}`);
  }
  markSessionHitRecorded();
}

export async function initViewsWidget(options = {}) {
  const mount = document.getElementById("global-views-bar");
  if (!mount) return;

  const apiUrl = await resolveApiUrlAsync(options.apiUrl);
  if (!apiUrl) {
    mount.hidden = true;
    return;
  }

  mount.hidden = false;
  setStatusMessage(mount, "global-views-loading", "Counting worldwide readers...");

  try {
    await recordPageHit(apiUrl);
    const res = await fetch(`${apiUrl}/stats`, { cache: "no-store", mode: "cors" });
    if (!res.ok) throw new Error(`stats failed: HTTP ${res.status}`);
    const data = await res.json();
    renderBar(mount, data);
  } catch (err) {
    console.warn("[papers-hub] views widget:", err);
    setStatusMessage(mount, "global-views-unavailable", "Global view stats unavailable");
  }
}
