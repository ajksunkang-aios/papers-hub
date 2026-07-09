/**
 * Cloudflare Worker: cumulative page views by world zone (CF-IPCountry).
 * Deploy with wrangler; bind KV namespace VIEW_STATS.
 */

import zones from "./zones.json";

const ZONE_ORDER = zones.zone_order;
const ZONE_LABELS = zones.zone_labels;

const COUNTRY_TO_ZONE = new Map();
for (const zone of ZONE_ORDER) {
  if (zone === "other") continue;
  for (const code of zones.countries[zone] || []) {
    COUNTRY_TO_ZONE.set(code.toUpperCase(), zone);
  }
}

const KV_TOTAL = "total";
const kvZone = (zone) => `zone:${zone}`;

function countryToZone(code) {
  const c = (code || "").toUpperCase();
  if (!c || c === "XX" || c === "T1") return "other";
  return COUNTRY_TO_ZONE.get(c) || "other";
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

async function readStats(env) {
  const total = Number((await env.VIEW_STATS.get(KV_TOTAL)) || 0);
  const zoneCounts = {};
  for (const zone of ZONE_ORDER) {
    zoneCounts[zone] = Number((await env.VIEW_STATS.get(kvZone(zone))) || 0);
  }
  return {
    total,
    zones: zoneCounts,
    zone_labels: ZONE_LABELS,
    zone_order: ZONE_ORDER,
    updated_at: new Date().toISOString(),
  };
}

async function recordHit(env, country) {
  const zone = countryToZone(country);
  await env.VIEW_STATS.put(KV_TOTAL, String(Number((await env.VIEW_STATS.get(KV_TOTAL)) || 0) + 1));
  await env.VIEW_STATS.put(
    kvZone(zone),
    String(Number((await env.VIEW_STATS.get(kvZone(zone))) || 0) + 1)
  );
  return { zone };
}

async function parseHitGeo(request) {
  let country = request.headers.get("CF-IPCountry") || "XX";

  const contentType = request.headers.get("Content-Type") || "";
  if (contentType.includes("application/json")) {
    try {
      const body = await request.json();
      if ((!country || country === "XX") && body.country) {
        country = String(body.country).toUpperCase();
      }
    } catch {
      /* optional JSON body */
    }
  }

  return { country };
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
      const { country } = await parseHitGeo(request);
      const { zone } = await recordHit(env, country);
      const stats = await readStats(env);
      return Response.json({ ok: true, zone, country, ...stats }, { headers });
    }

    return Response.json({ error: "Not found" }, { status: 404, headers });
  },
};
