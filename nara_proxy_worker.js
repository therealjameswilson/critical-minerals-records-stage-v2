// nara_proxy_worker.js
// ----------------------------------------------------------------------
// Cloudflare Worker  -  cloud replacement for the local local_server.py NARA proxy.
//
// Why this exists: the browser cannot call catalog.archives.gov directly (the
// API sends no CORS headers, so the browser blocks reading the response). The
// local Python server solved that but requires Python + a running process on
// the user's machine  -  not workable on a locked-down or managed laptop.
// This Worker does the same job in the cloud: it calls NARA server-to-server
// (no CORS involved) and returns the data to the browser WITH CORS headers.
//
// Each project should deploy its OWN copy of this Worker with its OWN NARA key
// (steps below). Don't point at someone else's Worker  -  their key, quota, and
// uptime would become your single point of failure.
//
// It mirrors the endpoints the tweet tool uses, with identical JSON
// shapes, so records-stage.html works by simply pointing at this Worker's URL
// instead of http://localhost:5757:
//     /ping            -> { ok, nara }
//     /nara/search?q=... -> { total, returned, query, hits:[...] }
//     /nara/fetch?url=... -> the image bytes (Content-Type fixed up)
//     /ia/fetch?id=...&page=...&size=... -> an Internet Archive page-render image
//
// The API key is NOT in this file. It is read from a Worker Secret named
// NARA_API_KEY, so it never reaches the browser (unlike public baked-in keys).
//
// -- Deploy entirely in the browser (no installs needed) ----------------------------------------------------------------------
//   1. dash.cloudflare.com -> Workers & Pages -> Create -> Worker.
//      Give it a name (e.g. "nara-proxy"), click Deploy on the starter.
//   2. "Edit code", delete the starter, paste this whole file, Deploy.
//   3. Worker -> Settings -> Variables and Secrets -> add a SECRET:
//         Name:  NARA_API_KEY
//         Value: your NARA catalog API key
//      Deploy again so the secret takes effect.
//   4. Copy the Worker URL (https://nara-proxy.<your-subdomain>.workers.dev)
//      and paste it into the tweet tool's "NARA proxy URL" setting.
// ----------------------------------------------------------------------

const NARA_BASE = "https://catalog.archives.gov/api/v2";

// Defensive whitelist  -  /nara/fetch only proxies NARA's own image hosts so
// the Worker can't be turned into an open relay. (Ported from local_server.py.)
// NARA migrated digital-object hosting off the old NARAprodstorage S3 bucket
// onto catalog.archives.gov (e.g. /medialz/stillpix/...); both are allowed so
// older and newer object URLs keep working.
const IMAGE_HOSTS = [
  "https://s3.amazonaws.com/NARAprodstorage/",
  "https://s3.dualstack.us-east-1.amazonaws.com/NARAprodstorage/",
  "https://s3.us-east-1.amazonaws.com/NARAprodstorage/",
  "https://catalog.archives.gov/",
];

// Browsers render these inline; TIFF (NARA's preservation master) they do not.
const RENDERABLE_IMAGE = /\.(jpe?g|png|gif|webp)$/i;

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, x-api-key",
  "Access-Control-Max-Age": "86400",
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...CORS },
  });
}

// -- response-shape helpers (ported 1:1 from otd_server.py) ----------------------------------------------------------------------
function isEmpty(v) {
  return (
    v === null ||
    v === undefined ||
    v === "" ||
    (Array.isArray(v) && v.length === 0) ||
    (typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === 0)
  );
}

// Depth-first search for the first non-empty value matching any key.
function walkFirst(node, keys) {
  if (node && typeof node === "object" && !Array.isArray(node)) {
    for (const k of keys) {
      if (k in node && !isEmpty(node[k])) return node[k];
    }
    for (const v of Object.values(node)) {
      const r = walkFirst(v, keys);
      if (r !== null && r !== undefined) return r;
    }
  } else if (Array.isArray(node)) {
    for (const x of node) {
      const r = walkFirst(x, keys);
      if (r !== null && r !== undefined) return r;
    }
  }
  return null;
}

// Collect every digitalObjects[] array found anywhere in the record.
function walkDigitalObjects(node, out = []) {
  if (node && typeof node === "object" && !Array.isArray(node)) {
    for (const [k, v] of Object.entries(node)) {
      if (k === "digitalObjects" && Array.isArray(v)) out.push(...v);
      else walkDigitalObjects(v, out);
    }
  } else if (Array.isArray(node)) {
    for (const item of node) walkDigitalObjects(item, out);
  }
  return out;
}

// A hit carries many `naId` keys, but most belong to ancestors (record group,
// collection) and authority references (creators, contributors) that are SHARED
// across results  -  which is why a naive deep search returned the same wrong id
// for every card. The record's own NAID is the catalog document id (`_id`);
// prefer it, and if it's absent fall back to a search that skips those shared
// branches.
const SKIP_NAID_KEYS = new Set([
  "ancestors", "creators", "contributors", "creatingOrganizations",
  "creatingIndividuals", "organizationalReferences", "personalReferences",
  "geographicReferences", "topicalSubjectReferences",
  "specificRecordsTypeReferences", "referenceUnits", "digitalObjects",
]);

function walkFirstExcept(node, keys, skip) {
  if (node && typeof node === "object" && !Array.isArray(node)) {
    for (const k of keys) {
      if (k in node && !isEmpty(node[k])) return node[k];
    }
    for (const [k, v] of Object.entries(node)) {
      if (skip.has(k)) continue;
      const r = walkFirstExcept(v, keys, skip);
      if (r !== null && r !== undefined) return r;
    }
  } else if (Array.isArray(node)) {
    for (const x of node) {
      const r = walkFirstExcept(x, keys, skip);
      if (r !== null && r !== undefined) return r;
    }
  }
  return null;
}

function recordNaId(hit) {
  const id = hit && hit._id;
  if (id !== undefined && id !== null && /^\d+$/.test(String(id).trim())) {
    return String(id).trim();
  }
  return walkFirstExcept(hit, ["naId"], SKIP_NAID_KEYS);
}

function normalizeHit(hit) {
  const naid = recordNaId(hit);
  const title = walkFirst(hit, ["title"]) || "";
  const lod = walkFirst(hit, ["levelOfDescription"]);
  const gtypes = walkFirst(hit, ["generalRecordsTypes"]);
  const use = walkFirst(hit, ["useRestriction"]) || {};
  let useStatus;
  if (use && typeof use === "object" && !Array.isArray(use)) {
    useStatus = use.status || use.note || "";
  } else {
    useStatus = String(use);
  }

  const digital = walkDigitalObjects(hit);
  const toObj = (d) => ({ url: d.objectUrl, type: d.objectType, filename: d.objectFilename });
  // Only surface browser-renderable images (JPG/PNG/GIF/WebP). NARA preservation
  // masters are TIFF, which no browser can display in an <img> and which social
  // platforms won't accept anyway. A record whose only image objects are TIFF
  // therefore yields zero images here (imageCount 0) and is dropped by the
  // client; the search UI shows a note that some items are hidden for format.
  const images = digital
    .filter((d) => d.objectUrl && (d.objectType || "").includes("Image") && RENDERABLE_IMAGE.test(d.objectUrl))
    .map(toObj);
  const docs = digital
    .filter((d) => d.objectUrl && !(d.objectType || "").includes("Image"))
    .map(toObj);

  return {
    naid,
    title,
    levelOfDescription: lod,
    generalRecordsTypes: gtypes,
    useRestriction: useStatus,
    imageCount: images.length,
    docCount: docs.length,
    thumbnail: images.length ? images[0].url : null,
    images: images.slice(0, 24),
  };
}

function findHits(node) {
  if (node && typeof node === "object" && !Array.isArray(node)) {
    if (Array.isArray(node.hits)) return node.hits;
    for (const v of Object.values(node)) {
      const r = findHits(v);
      if (r.length) return r;
    }
  }
  return [];
}

function findTotal(node) {
  if (node && typeof node === "object" && !Array.isArray(node)) {
    if ("total" in node) {
      const t = node.total;
      return t && typeof t === "object" ? t.value : t;
    }
    for (const v of Object.values(node)) {
      const r = findTotal(v);
      if (r !== null && r !== undefined) return r;
    }
  }
  return null;
}

// -- /nara/search ----------------------------------------------------------------------
async function handleSearch(url, env) {
  const key = env.NARA_API_KEY;
  if (!key) {
    return json(
      {
        error: "NARA API key not configured",
        hint: "Add a Secret named NARA_API_KEY to this Worker (Settings -> Variables and Secrets), then redeploy.",
      },
      503
    );
  }

  const p = url.searchParams;
  const rawQ = (p.get("q") || "").trim();
  if (!rawQ) return json({ error: "Missing required parameter: q" }, 400);

  // Phrase-quoting is opt-in (see otd_server.py rationale): auto-quoting
  // multi-word keyword combos returns zero hits, while unquoted = AND search.
  const usePhrase = ["1", "true", "yes"].includes((p.get("phrase") || "0").toLowerCase());
  let q = rawQ;
  if (
    usePhrase &&
    rawQ.includes(" ") &&
    !rawQ.startsWith('"') &&
    !rawQ.includes(" AND ") &&
    !rawQ.includes(" OR ")
  ) {
    q = `"${rawQ}"`;
  }

  let limit = parseInt(p.get("limit") || "30", 10);
  if (Number.isNaN(limit)) limit = 30;
  limit = Math.max(1, Math.min(100, limit));

  // 1-based page number for paging through large result sets ("Load more").
  let page = parseInt(p.get("page") || "1", 10);
  if (Number.isNaN(page) || page < 1) page = 1;

  const photosOnly = !["0", "false", "no"].includes((p.get("photos_only") || "1").toLowerCase());

  const params = new URLSearchParams({
    q,
    limit: String(limit),
    page: String(page),
    availability: "unrestrictedOnly",
    availableOnline: "true",
  });
  // Type of material. The UI sends an explicit `type_of_materials` value
  // ("any" = no type filter). When absent (older clients) fall back to the
  // legacy photos_only default of Photographs & graphic materials.
  const tom = (p.get("type_of_materials") || "").trim();
  if (tom) {
    if (tom.toLowerCase() !== "any") {
      params.set("typeOfMaterials", tom);
      params.set("levelOfDescription", "item");
    }
  } else if (photosOnly) {
    params.set("typeOfMaterials", "Photographs and other Graphic Materials");
    params.set("levelOfDescription", "item");
  }
  for (const [src, apiName] of [
    ["recurring_day", "recurringDateDay"],
    ["recurring_month", "recurringDateMonth"],
    ["record_group", "recordGroupNumber"],
  ]) {
    const v = (p.get(src) || "").trim();
    if (v) params.set(apiName, v);
  }

  const target = `${NARA_BASE}/records/search?${params.toString()}`;
  let resp;
  try {
    resp = await fetch(target, {
      headers: { "x-api-key": key, Accept: "application/json" },
    });
  } catch (e) {
    return json({ error: `${e.name}: ${e.message}` }, 502);
  }
  if (!resp.ok) {
    const detail = (await resp.text()).slice(0, 400);
    return json({ error: `NARA HTTP ${resp.status}`, detail }, 502);
  }

  let body;
  try {
    body = await resp.json();
  } catch (e) {
    return json({ error: `Bad JSON from NARA: ${e.message}` }, 502);
  }

  const hits = findHits(body);
  const total = findTotal(body);
  const normalized = hits.map(normalizeHit);
  // Surface image-bearing results first; keep doc-only as fallback.
  normalized.sort((a, b) => b.imageCount - a.imageCount || (b.docCount || 0) - (a.docCount || 0));

  const paramsObj = {};
  for (const [k, v] of params) paramsObj[k] = v;

  return json({
    total,
    returned: normalized.length,
    query: { raw: rawQ, effective: q, params: paramsObj },
    hits: normalized,
  });
}

// -- /nara/fetch ----------------------------------------------------------------------
async function handleFetch(url) {
  const target = (url.searchParams.get("url") || "").trim();
  if (!IMAGE_HOSTS.some((h) => target.startsWith(h))) {
    return json({ error: "URL must be a NARA S3 object", allowed_prefixes: IMAGE_HOSTS }, 400);
  }

  let upstream;
  try {
    upstream = await fetch(target);
  } catch (e) {
    return json({ error: `${e.name}: ${e.message}` }, 502);
  }
  if (!upstream.ok) return json({ error: `S3 HTTP ${upstream.status}` }, 502);

  // NARA's S3 serves images as binary/octet-stream, which confuses browsers.
  // Override the Content-Type based on the URL extension.
  const ext = target.split(".").pop().toLowerCase();
  const ctMap = {
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    png: "image/png",
    gif: "image/gif",
    tif: "image/tiff",
    tiff: "image/tiff",
    pdf: "application/pdf",
  };
  const contentType =
    ctMap[ext] || upstream.headers.get("Content-Type") || "application/octet-stream";

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "public, max-age=86400",
      ...CORS,
    },
  });
}

// -- /ia/fetch ----------------------------------------------------------------------
// Stream an Internet Archive page-render image through the proxy so the tweet
// tool can attach article images without a local server. Mirrors
// local_server.py's /ia/fetch route: builds IA's IIIF page-image URL from an
// identifier + 1-indexed PDF page and streams the JPEG back with CORS.
const IA_VALID_SIZE = new Set(["full", "pct:25", "pct:50", "pct:75", "pct:100"]);

async function handleIaFetch(url) {
  const identifier = (url.searchParams.get("id") || "").trim();
  const pageRaw = (url.searchParams.get("page") || "").trim();
  const size = (url.searchParams.get("size") || "pct:50").trim();

  if (!identifier || !pageRaw) {
    return json({ error: "Both `id` and `page` query params are required" }, 400);
  }
  if (!IA_VALID_SIZE.has(size)) {
    return json({ error: `size must be one of ${[...IA_VALID_SIZE].sort().join(", ")}` }, 400);
  }
  // Defense-in-depth: IA identifiers are letters/digits/_-. only.
  if (!/^[A-Za-z0-9_.\-]+$/.test(identifier)) {
    return json({ error: "identifier has invalid characters" }, 400);
  }
  const page = Number.parseInt(pageRaw, 10);
  if (Number.isNaN(page)) return json({ error: "page must be an integer" }, 400);
  if (page < 1) return json({ error: "page must be 1 or greater" }, 400);

  // IA uses 0-indexed n<N> page tokens in its IIIF reader URLs.
  const target =
    `https://archive.org/download/${identifier}/page/n${page - 1}/` +
    `full/${size}/0/default.jpg`;

  let upstream;
  try {
    upstream = await fetch(target);
  } catch (e) {
    return json({ error: `${e.name}: ${e.message}`, url: target }, 502);
  }
  if (!upstream.ok) return json({ error: `IA HTTP ${upstream.status}`, url: target }, 502);

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "image/jpeg",
      "Cache-Control": "public, max-age=86400",
      "X-IA-Source-URL": target,
      ...CORS,
    },
  });
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    if (path === "/ping") return json({ ok: true, nara: !!env.NARA_API_KEY });
    if (path === "/nara/search") return handleSearch(url, env);
    if (path === "/nara/fetch") return handleFetch(url);
    if (path === "/ia/fetch") return handleIaFetch(url);
    if (path === "/") {
      return new Response(
        "NARA proxy worker is running. Endpoints: /ping, /nara/search, /nara/fetch, /ia/fetch",
        { status: 200, headers: { "Content-Type": "text/plain", ...CORS } }
      );
    }
    return json({ error: "Not found", path }, 404);
  },
};
