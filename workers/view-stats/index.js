/**
 * Cloudflare Worker: cumulative page views by world zone (CF-IPCountry).
 * Deploy with wrangler; bind KV namespace VIEW_STATS.
 */

import zones from "./zones.json";

const ZONE_ORDER = zones.zone_order;
const ZONE_LABELS = zones.zone_labels;
const HIGHLIGHT_COUNTRIES = zones.highlight_countries || {};
const CHINA_CITY_CONFIG = zones.china_cities || {};
const CHINA_CITY_ORDER = CHINA_CITY_CONFIG.order || [];
const CHINA_CITY_LABELS = CHINA_CITY_CONFIG.labels || {};

const COUNTRY_TO_ZONE = new Map();
for (const zone of ZONE_ORDER) {
  if (zone === "other") continue;
  for (const code of zones.countries[zone] || []) {
    COUNTRY_TO_ZONE.set(code.toUpperCase(), zone);
  }
}

const CITY_TO_BUCKET = new Map();
for (const [bucket, names] of Object.entries(CHINA_CITY_CONFIG.match || {})) {
  CITY_TO_BUCKET.set(normalizeCityName(bucket), bucket);
  for (const alias of names) {
    CITY_TO_BUCKET.set(normalizeCityName(alias), bucket);
  }
}

const KV_TOTAL = "total";
const kvZone = (zone) => `zone:${zone}`;
const kvCountry = (code) => `country:${code}`;
const kvChinaCity = (city) => `china:${city}`;

function normalizeCityName(city) {
  if (!city) return "";
  let normalized = city.trim().toLowerCase();
  for (const suffix of [" shi", " city", " municipality"]) {
    if (normalized.endsWith(suffix)) {
      normalized = normalized.slice(0, -suffix.length);
    }
  }
  return normalized.replace(/\./g, "").trim();
}

function countryToZone(code) {
  const c = (code || "").toUpperCase();
  if (!c || c === "XX" || c === "T1") return "other";
  return COUNTRY_TO_ZONE.get(c) || "other";
}

function chinaCityBucket(city) {
  const normalized = normalizeCityName(city);
  if (!normalized) return null;
  if (CITY_TO_BUCKET.has(normalized)) return CITY_TO_BUCKET.get(normalized);
  for (const [alias, bucket] of CITY_TO_BUCKET.entries()) {
    if (normalized.startsWith(alias) || alias.startsWith(normalized)) return bucket;
  }
  return null;
}

function corsHeaders(origin, env) {
  const allowed = (env.ALLOWED_ORIGINS || "*").split(",").map((s) => s.trim()).filter(Boolean);
  if (allowed.includes("*")) {
    return {
      "Access-Control-Allow-Origin": origin || "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
    };
  }
  const match = allowed.includes(origin);
  return {
    "Access-Control-Allow-Origin": match ? origin : allowed[0],
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

async function readChinaCityCounts(env) {
  const counts = {};
  for (const city of CHINA_CITY_ORDER) {
    counts[city] = Number((await env.VIEW_STATS.get(kvChinaCity(city))) || 0);
  }
  return {
    order: CHINA_CITY_ORDER,
    labels: CHINA_CITY_LABELS,
    counts,
  };
}

async function readStats(env) {
  const total = Number((await env.VIEW_STATS.get(KV_TOTAL)) || 0);
  const zoneCounts = {};
  for (const zone of ZONE_ORDER) {
    zoneCounts[zone] = Number((await env.VIEW_STATS.get(kvZone(zone))) || 0);
  }
  const countryCounts = {};
  for (const code of Object.keys(HIGHLIGHT_COUNTRIES)) {
    countryCounts[code] = Number((await env.VIEW_STATS.get(kvCountry(code))) || 0);
  }
  return {
    total,
    zones: zoneCounts,
    countries: countryCounts,
    china_cities: await readChinaCityCounts(env),
    highlight_countries: HIGHLIGHT_COUNTRIES,
    zone_labels: ZONE_LABELS,
    zone_order: ZONE_ORDER,
    updated_at: new Date().toISOString(),
  };
}

async function recordHit(env, country, city) {
  const zone = countryToZone(country);
  const code = (country || "").toUpperCase();
  await env.VIEW_STATS.put(KV_TOTAL, String(Number((await env.VIEW_STATS.get(KV_TOTAL)) || 0) + 1));
  await env.VIEW_STATS.put(
    kvZone(zone),
    String(Number((await env.VIEW_STATS.get(kvZone(zone))) || 0) + 1)
  );
  let chinaBucket = null;
  if (HIGHLIGHT_COUNTRIES[code]) {
    await env.VIEW_STATS.put(
      kvCountry(code),
      String(Number((await env.VIEW_STATS.get(kvCountry(code))) || 0) + 1)
    );
    if (code === "CN") {
      chinaBucket = chinaCityBucket(city);
      if (chinaBucket) {
        await env.VIEW_STATS.put(
          kvChinaCity(chinaBucket),
          String(Number((await env.VIEW_STATS.get(kvChinaCity(chinaBucket))) || 0) + 1)
        );
      }
    }
  }
  return { zone, chinaBucket };
}

async function parseHitGeo(request) {
  let country = request.headers.get("CF-IPCountry") || "XX";
  let city = request.cf?.city || "";

  const contentType = request.headers.get("Content-Type") || "";
  if (contentType.includes("application/json")) {
    try {
      const body = await request.json();
      if ((!country || country === "XX") && body.country) {
        country = String(body.country).toUpperCase();
      }
      if (!city && body.city) {
        city = String(body.city);
      }
    } catch {
      /* optional JSON body */
    }
  }

  return { country, city };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin") || "";
    const headers = { "Content-Type": "application/json; charset=utf-8", ...corsHeaders(origin, env) };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers });
    }

    if (url.pathname === "/stats" && request.method === "GET") {
      return Response.json(await readStats(env), { headers });
    }

    if (url.pathname === "/hit" && request.method === "POST") {
      const { country, city } = await parseHitGeo(request);
      const { zone, chinaBucket } = await recordHit(env, country, city);
      const stats = await readStats(env);
      return Response.json(
        { ok: true, zone, country, city: city || null, china_city: chinaBucket, ...stats },
        { headers }
      );
    }

    return Response.json({ error: "Not found" }, { status: 404, headers });
  },
};
