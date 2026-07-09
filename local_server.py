#!/usr/bin/env python3
"""
Toolkit Local Server

A tiny local HTTP server that backs the in-browser features of the
Records Stage HTML tool (fetched via ``fetch_records_stage.py``):

  /ping            — health check; reports which features are enabled
  /summarize       — optional AI summarization of draft text
                     (requires transformers + torch + a HuggingFace model)
  /nara/search     — proxies the National Archives Catalog v2 API so the
                     HTML tool can search for photos to attach to a tweet
  /nara/fetch      — streams a NARA S3 image through the proxy, bypassing
                     the browser's CORS restrictions

All routes listen on http://localhost:5757 by default — the same port the
upstream records-stage.html expects. Keep this terminal open while using
the HTML tool.

WHAT YOU NEED

Minimum (NARA-only):
    pip install flask flask-cors
    Save your NARA Catalog API key to .nara_key in this directory
    (request one by emailing Catalog_API@nara.gov)

Optional (also enable the AI summarizer, ~300 MB model download):
    pip install transformers torch sentencepiece

RUN

    python local_server.py

OPTIONS

    python local_server.py --port 5757
    python local_server.py --model facebook/bart-large-cnn   # higher-quality summarizer (~1.6 GB)
    python local_server.py --no-browser-open
"""

import argparse
import os
import re
import sys
import threading
import webbrowser
from pathlib import Path


# ── Argument parsing ──────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Toolkit Local Server")
parser.add_argument("--port",  type=int, default=5757, help="Port to listen on (default: 5757)")
parser.add_argument("--model", default="sshleifer/distilbart-cnn-12-6",
                    help="HuggingFace summarization model (only used if transformers is installed). "
                         "Default: sshleifer/distilbart-cnn-12-6 (~300 MB).")
parser.add_argument("--no-browser-open", action="store_true",
                    help="Don't auto-open records-stage.html in the browser.")
args = parser.parse_args()

PORT = args.port


# ── Dependency check ──────────────────────────────────────────────────────────

def check_deps():
    """flask + flask_cors are mandatory (used by every route).
    transformers + torch are only needed by /summarize — if they're absent
    the server runs in NARA-only mode."""
    missing = []
    for pkg in ("flask", "flask_cors"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print("\n  ✗  Missing required packages:", ", ".join(missing))
        print("     Run:  pip install flask flask-cors\n")
        sys.exit(1)

check_deps()

from flask import Flask, request, jsonify, Response   # noqa: E402
from flask_cors import CORS                             # noqa: E402

# Standard-library deps for the NARA proxy (no extra pip install).
import json                # noqa: E402
import urllib.error        # noqa: E402
import urllib.parse        # noqa: E402
import urllib.request      # noqa: E402

# Optional AI summarizer.
try:
    from transformers import pipeline    # noqa: E402
    AI_AVAILABLE = True
except ImportError:
    pipeline = None
    AI_AVAILABLE = False


# ── NARA Catalog API key ──────────────────────────────────────────────────────
# Read from .nara_key in the repo root (gitignored). If absent, the /nara/*
# routes return 503 with a setup hint — the summarizer keeps working.

_NARA_KEY_PATH = Path(__file__).parent / ".nara_key"
NARA_API_KEY = _NARA_KEY_PATH.read_text().strip() if _NARA_KEY_PATH.exists() else None
NARA_BASE = "https://catalog.archives.gov/api/v2"

if NARA_API_KEY:
    print(f"  ✓ NARA key loaded ({len(NARA_API_KEY)} chars) — /nara/search enabled.")
else:
    print(f"  ⚠ No .nara_key in {_NARA_KEY_PATH.parent} — /nara/search disabled.")


# ── Model loading ─────────────────────────────────────────────────────────────

summarizer = None

if AI_AVAILABLE:
    print(f"\n  Toolkit Local Server  —  model: {args.model}")
    print("  Loading model (first run downloads it and caches — may take a minute)…")
    try:
        summarizer = pipeline(
            "summarization",
            model=args.model,
            device=-1,           # CPU; change to 0 for GPU
        )
        print("  ✓ Model ready.")
    except Exception as e:
        print(f"\n  ⚠  Could not load model — /summarize will be disabled: {e}")
        summarizer = None
else:
    print("\n  ⚠  transformers/torch not installed — /summarize disabled.")
    print("     To enable the AI summarizer:")
    print("         pip install transformers torch sentencepiece")


# ── Text helpers for the summarizer ───────────────────────────────────────────
# Adopters: tune these to match your drafting style. The defaults just
# normalize whitespace and strip common boilerplate the summarizer adds.

def preprocess(raw: str) -> str:
    """Cap length so the summarizer doesn't OOM on long inputs."""
    flat = re.sub(r"\s+", " ", raw).strip()
    return flat[:1500]


def clean_output(text: str) -> str:
    """Strip wrapping quotes and 'Summary:'-style prefixes."""
    text = text.strip().strip('"\'')
    text = re.sub(r"^(summary|result|tweet|output)[:\s]+", "", text, flags=re.I)
    return text


def trim(text: str, budget: int) -> str:
    if len(text) <= budget:
        return text
    cut = text[:budget - 1]
    sp  = cut.rfind(" ")
    return (cut[:sp] if sp > budget * 0.6 else cut) + "…"


# ── Flask app ──────────────────────────────────────────────────────────────────

app = Flask(__name__)

# Only the local HTML tool should reach these routes. records-stage.html is
# opened from disk, so its requests carry `Origin: null`; we also allow the
# loopback origins in case it's served locally. Crucially this is NOT a bare
# CORS(app): an unrestricted policy lets any website the user happens to be
# visiting drive this server (burning the NARA quota, using /summarize as free
# compute, probing the fetch proxies) while it's running.
_ALLOWED_ORIGINS = [
    "null",
    "http://localhost", f"http://localhost:{PORT}",
    "http://127.0.0.1", f"http://127.0.0.1:{PORT}",
]
CORS(app, origins=_ALLOWED_ORIGINS)

# Hard cap on bytes streamed through the image proxies, so a hostile or
# mistaken upstream URL can't make us relay an unbounded download.
_MAX_PROXY_BYTES = 64 * 1024 * 1024


def _capped_stream(upstream, limit=_MAX_PROXY_BYTES):
    """Yield upstream bytes, stopping once `limit` is exceeded."""
    sent = 0
    try:
        while True:
            chunk = upstream.read(65536)
            if not chunk:
                break
            sent += len(chunk)
            if sent > limit:
                break
            yield chunk
    finally:
        upstream.close()


@app.route("/ping")
def ping():
    """Used by the HTML tool to detect whether the server is running and
    which features are available."""
    return jsonify({
        "status": "ok",
        "model": args.model if summarizer else None,
        "features": {
            "summarize": summarizer is not None,
            "nara": NARA_API_KEY is not None,
        },
    })


@app.route("/summarize", methods=["POST"])
def summarize():
    if summarizer is None:
        return jsonify({
            "error": "AI summarizer not available",
            "hint": "Install: pip install transformers torch sentencepiece, then restart this server.",
        }), 503

    data   = request.get_json(force=True, silent=True) or {}
    text   = (data.get("text") or "").strip()
    budget = int(data.get("budget") or 200)

    if not text:
        return jsonify({"error": "No text provided"}), 400

    processed  = preprocess(text)
    max_tokens = min(80, max(20, budget // 4))

    try:
        result = summarizer(
            processed,
            max_new_tokens=max_tokens,
            min_length=10,
            do_sample=False,
            truncation=True,
        )
        body = clean_output(result[0]["summary_text"])
        body = trim(body, budget)
        return jsonify({"summary": body, "model": args.model})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── NARA Catalog proxy ────────────────────────────────────────────────────────
# The browser can't call catalog.archives.gov directly (no CORS) and we don't
# want the API key shipped to clients. These two routes wrap the v2 catalog
# API and the S3 image hosts so the HTML tool can search and embed photos.

# Allowed prefixes for /nara/fetch — defensive whitelist so the proxy can't
# be turned into an open relay. All NARA digital objects live under one of these.
_NARA_IMAGE_HOSTS = (
    "https://s3.amazonaws.com/NARAprodstorage/",
    "https://s3.dualstack.us-east-1.amazonaws.com/NARAprodstorage/",
    "https://s3.us-east-1.amazonaws.com/NARAprodstorage/",
    # NARA migrated digital objects off the NARAprodstorage S3 bucket onto
    # catalog.archives.gov (e.g. /medialz/stillpix/...); allow both.
    "https://catalog.archives.gov/",
)

# Browsers render these inline; TIFF (NARA's preservation master) they do not.
_RENDERABLE_IMAGE_RE = re.compile(r"\.(jpe?g|png|gif|webp)$", re.IGNORECASE)


def _nara_unavailable():
    return jsonify({
        "error": "NARA API key not configured",
        "hint": "Save your key to .nara_key in the repo root and restart this server.",
    }), 503


def _walk_first(node, *keys):
    """Depth-first search for the first non-empty value matching any key."""
    if isinstance(node, dict):
        for k in keys:
            if k in node and node[k] not in (None, "", [], {}):
                return node[k]
        for v in node.values():
            r = _walk_first(v, *keys)
            if r is not None:
                return r
    elif isinstance(node, list):
        for x in node:
            r = _walk_first(x, *keys)
            if r is not None:
                return r
    return None


def _walk_all_digital_objects(node):
    """Collect every digitalObjects[] array found anywhere in the record."""
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "digitalObjects" and isinstance(v, list):
                out.extend(v)
            else:
                out.extend(_walk_all_digital_objects(v))
    elif isinstance(node, list):
        for item in node:
            out.extend(_walk_all_digital_objects(item))
    return out


# A hit carries many `naId` keys, but most belong to ancestors (record group,
# collection) and authority references (creators, contributors) shared across
# results — a naive deep search returned the same wrong id for every card. The
# record's own NAID is the catalog document id (`_id`); prefer it, falling back
# to a search that skips those shared branches.
_SKIP_NAID_KEYS = {
    "ancestors", "creators", "contributors", "creatingOrganizations",
    "creatingIndividuals", "organizationalReferences", "personalReferences",
    "geographicReferences", "topicalSubjectReferences",
    "specificRecordsTypeReferences", "referenceUnits", "digitalObjects",
}


def _walk_first_except(node, keys, skip):
    """Like _walk_first but does not descend into keys listed in `skip`."""
    if isinstance(node, dict):
        for k in keys:
            if k in node and node[k] not in (None, "", [], {}):
                return node[k]
        for k, v in node.items():
            if k in skip:
                continue
            r = _walk_first_except(v, keys, skip)
            if r is not None:
                return r
    elif isinstance(node, list):
        for x in node:
            r = _walk_first_except(x, keys, skip)
            if r is not None:
                return r
    return None


def _record_naid(hit):
    """The record's own NAID = the catalog document id, else an ancestor-free walk."""
    doc_id = hit.get("_id") if isinstance(hit, dict) else None
    if doc_id is not None and str(doc_id).strip().isdigit():
        return str(doc_id).strip()
    return _walk_first_except(hit, ("naId",), _SKIP_NAID_KEYS)


def _normalize_hit(hit):
    """Flatten a NARA hit into the minimal shape the browser cares about."""
    naid = _record_naid(hit)
    title = _walk_first(hit, "title") or ""
    lod = _walk_first(hit, "levelOfDescription")
    gtypes = _walk_first(hit, "generalRecordsTypes")
    use = _walk_first(hit, "useRestriction") or {}
    if isinstance(use, dict):
        use_status = use.get("status") or use.get("note") or ""
    else:
        use_status = str(use)

    digital = _walk_all_digital_objects(hit)
    # Only surface browser-renderable images (JPG/PNG/GIF/WebP). NARA preservation
    # masters are TIFF, which no browser can display and social platforms won't
    # accept, so a record whose only image objects are TIFF yields zero images
    # here (imageCount 0) and is dropped by the client; the search UI notes that
    # some items are hidden for format.
    images = [
        {
            "url": d.get("objectUrl"),
            "type": d.get("objectType"),
            "filename": d.get("objectFilename"),
        }
        for d in digital
        if d.get("objectUrl") and "Image" in (d.get("objectType") or "")
        and _RENDERABLE_IMAGE_RE.search(d.get("objectUrl") or "")
    ]
    docs = [
        {
            "url": d.get("objectUrl"),
            "type": d.get("objectType"),
            "filename": d.get("objectFilename"),
        }
        for d in digital
        if d.get("objectUrl") and "Image" not in (d.get("objectType") or "")
    ]

    return {
        "naid": naid,
        "title": title,
        "levelOfDescription": lod,
        "generalRecordsTypes": gtypes,
        "useRestriction": use_status,
        "imageCount": len(images),
        "docCount": len(docs),
        "thumbnail": images[0]["url"] if images else None,
        "images": images[:24],   # cap to keep payload small
    }


@app.route("/nara/search")
def nara_search():
    """Proxy the NARA catalog search with photo-priority defaults baked in.

    Query params accepted from the browser:
      q              — search string (required)
      limit          — max results to return (default 30, hard-capped 100)
      photos_only    — '1'/'true' (legacy default) applies the Photographs
                       typeOfMaterials + levelOfDescription=item filters. Only
                       used when type_of_materials is absent.
      type_of_materials — NARA typeOfMaterials value, optional (e.g.
                       'Maps and Charts', 'Moving Images'). 'any' = no type
                       filter. Overrides photos_only when present.
      phrase         — '1'/'true' wraps q in quotes for exact-phrase search.
      recurring_day  — DD, optional (for "On This Day"-style queries)
      recurring_month— MM, optional (pair with recurring_day)
      record_group   — RG number, optional (e.g. '59' for State Dept)
    """
    if not NARA_API_KEY:
        return _nara_unavailable()

    raw_q = (request.args.get("q") or "").strip()
    if not raw_q:
        return jsonify({"error": "Missing required parameter: q"}), 400

    # Phrase-quoting is opt-in. Auto-quoting a two-word keyword combo
    # (e.g. "Person Topic") often returns zero hits because no record
    # title contains that exact phrase; the unquoted form treats the
    # words as an AND search, which is usually what the caller wants.
    use_phrase = (request.args.get("phrase", "0").lower()
                  in ("1", "true", "yes"))
    if (use_phrase
            and " " in raw_q
            and not raw_q.startswith('"')
            and " AND " not in raw_q
            and " OR " not in raw_q):
        q = f'"{raw_q}"'
    else:
        q = raw_q

    try:
        limit = max(1, min(100, int(request.args.get("limit", "30"))))
    except ValueError:
        limit = 30

    # 1-based page number for paging through large result sets ("Load more").
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1

    photos_only = (request.args.get("photos_only", "1").lower()
                   not in ("0", "false", "no"))

    params = {
        "q": q,
        "limit": str(limit),
        "page": str(page),
        "availability": "unrestrictedOnly",
        "availableOnline": "true",
    }
    # Type of material. The UI sends an explicit type_of_materials value
    # ("any" = no type filter). When absent (older clients) fall back to the
    # legacy photos_only default of Photographs & graphic materials.
    tom = (request.args.get("type_of_materials") or "").strip()
    if tom:
        if tom.lower() != "any":
            params["typeOfMaterials"] = tom
            params["levelOfDescription"] = "item"
    elif photos_only:
        params["typeOfMaterials"] = "Photographs and other Graphic Materials"
        params["levelOfDescription"] = "item"

    for key, api_key in [("recurring_day", "recurringDateDay"),
                         ("recurring_month", "recurringDateMonth"),
                         ("record_group", "recordGroupNumber")]:
        val = (request.args.get(key) or "").strip()
        if val:
            params[api_key] = val

    url = f"{NARA_BASE}/records/search?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "x-api-key": NARA_API_KEY,
        "Accept": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return jsonify({"error": f"NARA HTTP {e.code}",
                        "detail": e.read().decode("utf-8", "replace")[:400]}), 502
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 502

    def find_hits(node):
        if isinstance(node, dict):
            if isinstance(node.get("hits"), list):
                return node["hits"]
            for v in node.values():
                r = find_hits(v)
                if r:
                    return r
        return []

    def find_total(node):
        if isinstance(node, dict):
            if "total" in node:
                t = node["total"]
                return t.get("value") if isinstance(t, dict) else t
            for v in node.values():
                r = find_total(v)
                if r is not None:
                    return r
        return None

    hits = find_hits(body)
    total = find_total(body)

    normalized = [_normalize_hit(h) for h in hits]
    # Surface image-bearing results first; keep doc-only as fallback.
    normalized.sort(key=lambda r: (-r["imageCount"], -(r["docCount"] or 0)))

    return jsonify({
        "total": total,
        "returned": len(normalized),
        "query": {"raw": raw_q, "effective": q, "params": params},
        "hits": normalized,
    })


@app.route("/nara/fetch")
def nara_fetch():
    """Stream a NARA S3 image through the proxy to bypass browser CORS.

    Query params:
      url — full S3 URL; must start with one of _NARA_IMAGE_HOSTS.
    """
    if not NARA_API_KEY:
        return _nara_unavailable()

    target = (request.args.get("url") or "").strip()
    if not target.startswith(_NARA_IMAGE_HOSTS):
        return jsonify({"error": "URL must be a NARA S3 object",
                        "allowed_prefixes": list(_NARA_IMAGE_HOSTS)}), 400

    try:
        upstream = urllib.request.urlopen(target, timeout=30)
    except urllib.error.HTTPError as e:
        return jsonify({"error": f"S3 HTTP {e.code}"}), 502
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 502

    # NARA's S3 serves images as binary/octet-stream, which confuses browsers.
    # Override the content type based on the URL extension so the browser
    # treats the response as a real image.
    ext = target.rsplit(".", 1)[-1].lower()
    content_type = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif",
        "tif": "image/tiff", "tiff": "image/tiff",
        "pdf": "application/pdf",
    }.get(ext, upstream.headers.get("Content-Type", "application/octet-stream"))

    return Response(_capped_stream(upstream), mimetype=content_type, headers={
        "Cache-Control": "public, max-age=86400",
    })


# ── Internet Archive page-image proxy ────────────────────────────────────────
# Used by records-stage.html's article-image gallery: the publishing tool
# knows the IA identifier + PDF page for each image (from the extraction
# pass), this endpoint fetches the corresponding page-render JPEG and
# streams it back as a real image/jpeg so the browser can attach it to
# a tweet card. Bypasses browser-side CORS that IA doesn't set, mirrors
# the /nara/fetch pattern.

_IA_VALID_SIZE = {"full", "pct:25", "pct:50", "pct:75", "pct:100"}


@app.route("/ia/fetch")
def ia_fetch():
    """Stream an Internet Archive page-render image through the proxy.

    Query params:
      id   — IA identifier (e.g. "sim_state-magazine_1991-05_344")
      page — 1-indexed PDF page number (1 = front cover); converted
             to IA's 0-indexed `n<N>` form internally
      size — optional IIIF region/size token. Defaults to "pct:50",
             which is plenty for tweet attachment (~1200 px wide on
             a typical magazine scan). Set to "full" or "pct:100" for
             archival-quality fetch.
    """
    identifier = (request.args.get("id") or "").strip()
    page_raw = (request.args.get("page") or "").strip()
    size = (request.args.get("size") or "pct:50").strip()

    if not identifier or not page_raw:
        return jsonify({"error": "Both `id` and `page` query params are required"}), 400
    if size not in _IA_VALID_SIZE:
        return jsonify({"error": f"size must be one of {sorted(_IA_VALID_SIZE)}"}), 400

    # Light defense-in-depth: IA identifiers are letters/digits/_-.
    # Reject anything that looks path-traversal-y.
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+", identifier):
        return jsonify({"error": "identifier has invalid characters"}), 400

    try:
        page = int(page_raw)
    except ValueError:
        return jsonify({"error": "page must be an integer"}), 400
    if page < 1:
        return jsonify({"error": "page must be 1 or greater"}), 400

    target = (
        f"https://archive.org/download/{identifier}/page/n{page - 1}/"
        f"full/{size}/0/default.jpg"
    )

    try:
        upstream = urllib.request.urlopen(target, timeout=60)
    except urllib.error.HTTPError as e:
        return jsonify({"error": f"IA HTTP {e.code}", "url": target}), 502
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 502

    return Response(_capped_stream(upstream), mimetype="image/jpeg", headers={
        "Cache-Control": "public, max-age=86400",
        "X-IA-Source-URL": target,
    })


@app.route("/")
def index():
    nara_line = (
        "<p>NARA proxy: <strong>enabled</strong> "
        "(/nara/search, /nara/fetch)</p>"
        if NARA_API_KEY
        else "<p>NARA proxy: <em>disabled</em> — drop a key into "
             "<code>.nara_key</code> and restart to enable.</p>"
    )
    summary_line = (
        f"<p>AI summarizer: <strong>enabled</strong> "
        f"(model: <code>{args.model}</code>)</p>"
        if summarizer
        else "<p>AI summarizer: <em>disabled</em> — run "
             "<code>pip install transformers torch sentencepiece</code> "
             "and restart to enable.</p>"
    )
    return (
        "<h2>Toolkit Local Server is running ✓</h2>"
        f"{nara_line}"
        f"{summary_line}"
        "<p>IA image proxy: <strong>enabled</strong> (/ia/fetch) — "
        "lets the publishing tool attach original-issue photos to tweet cards.</p>"
        "<p>Keep this terminal open while using the Records Stage HTML tool.</p>"
    )


# ── Startup ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    html_path = Path(__file__).parent / "records-stage.html"

    if not args.no_browser_open and html_path.exists():
        def open_browser():
            import time; time.sleep(1)
            webbrowser.open(html_path.as_uri())
        threading.Thread(target=open_browser, daemon=True).start()

    print(f"  Listening at  http://localhost:{PORT}")
    print(f"  Press Ctrl+C to stop.\n")
    app.run(host="127.0.0.1", port=PORT, debug=False)
