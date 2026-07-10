# NARA Catalog API Integration

## Architecture Decision

GitHub Pages is static and cannot keep `NARA_API_KEY` secret. The v2 site uses a
small serverless proxy for on-demand Catalog searches:

```text
GitHub Pages browser
  -> public Worker URL
  -> Worker adds x-api-key from its secret environment
  -> NARA Catalog API v2
  -> Worker returns minimized metadata with Cache-Control: no-store
```

The repository also provides `local_server.py` for local development and
`connectors/nara.py` for server-side scripts. Neither client writes API responses
to disk.

NARA’s current API terms require the key to remain private, require a visible
attribution notice, impose a default monthly query limit, and say: do not cache or store
content returned by the API. For that reason, this project does not
use the initially contemplated GitHub Actions response cache. The Worker option
was one of the permitted architectures in the project brief and is compatible
with the current terms.

Official guidance:

- <https://www.archives.gov/research/catalog/help/api>
- <https://www.archives.gov/research/catalog/help/api-getting-started>
- <https://catalog.archives.gov/api/v2/api-docs/>

## Secret Handling

The only supported key name is:

```text
NARA_API_KEY
```

Local setup:

```bash
cp .env.example .env.local
# Populate .env.local locally. Do not commit it.
python local_server.py --no-browser-open
```

The server checks the process environment first and `.env.local` second. It
never prints the key or its length. `.env.local`, `.env.*`, and legacy local-key
patterns are ignored by Git. `assets/runtime-config.js` points local site hosts
to `http://localhost:5757` automatically. The public GitHub Pages site uses the
deployed Cloudflare Worker URL; the secret remains available only to the Worker
runtime.

## Deploy the Worker

1. Create a Cloudflare Worker or equivalent serverless JavaScript function.
2. Deploy `nara_proxy_worker.js`.
3. Add a secret environment variable named `NARA_API_KEY`.
4. Deploy again.
5. Test `https://YOUR-WORKER/ping`.
6. Put only the public Worker URL in `assets/runtime-config.js`.
7. Run the repository secret scan before committing.

The public Worker URL is not a secret. The API key must never appear in the
Worker source, runtime config, browser output, logs, screenshots, docs, or Git
history.

## Query Plans

`data/history-stack/nara-queries.json` contains 25 structured plans. Each plan
stores:

- a bounded historical query
- one or more record groups
- start and end years
- linked minerals and countries
- relevance method
- live-query status
- source registry ID

The browser sends `q`, `recordGroupNumber`, `startDate`, `endDate`,
`availableOnline`, and a bounded `limit`. Dates use NARA’s documented `YYYY`
format at the same precision.

High-priority record groups in the pilot include RG 59, 84, 165, 169, 218, 229,
234, 287, 330, and 353.

## Normalized Response

The proxy keeps only metadata needed for discovery:

- NAID
- title
- Catalog URL
- level of description
- general record type
- date note
- creator metadata
- record group number
- scope note
- use restriction
- browser-renderable preview metadata
- retrieval timestamp
- live status and required NARA attribution

No extracted OCR text or full document body is returned by the project proxy.
The browser labels every response as live and unreviewed.

## Relevance Labels

- **Direct match:** all significant query tokens appear in returned title or
  description metadata.
- **Probable match:** at least half of significant query tokens appear.
- **Contextual match:** record-group context matches but topical tokens are weak.
- **Broad archival lead:** the result requires wider archival review.

These are transparent metadata-match aids, not historical judgments.

## Failure Behavior

If the Worker, key, quota, or NARA service is unavailable:

- the historical site still loads
- no stale API response is substituted
- the user sees a clear unavailable state
- the structured plan still opens in the official NARA Catalog
- all FRUS, USGS, law, agreement, and static pilot data remains functional

## Required Attribution

The application displays NARA’s required notice:

> This product uses the National Archives Catalog API but is not endorsed or
> certified by the National Archives and Records Administration.
