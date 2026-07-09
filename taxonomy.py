"""
Optional taxonomy loader and event enrichment.

If your corpus has a controlled vocabulary of subjects, load it here so the
HTML tool's Category → Subcategory → Subject cascade activates. If you
don't have a taxonomy, leave ``load_taxonomy()`` raising NotImplementedError
and the build will skip enrichment automatically (subject UI hides itself).

If you publish your taxonomy as a JSON export in a separate repo (a
useful pattern when the taxonomy is shared across multiple tools), this
module ships a multi-source resolver so adopters can point at the export
without copying files around:

    1. Explicit path passed to load_taxonomy(path=...).
    2. ``TAXONOMY_REPO_DIR`` env var → ``<dir>/exports/taxonomy.json``.
    3. Sibling-directory checkout (``../<repo-name>/exports/``).
    4. GitHub raw fetch from ``<owner>/<repo>``.

If you have a simpler local taxonomy (one JSON file in your repo, a CSV,
a hard-coded list), just override ``load_taxonomy()`` to return your
list directly and ignore the resolution helpers.

The toolkit ships **no default taxonomy source.** Adopters either provide
their own or skip taxonomy entirely.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Optional


TAXONOMY_REPO_ENV = "TAXONOMY_REPO_DIR"
DEFAULT_TAXONOMY_REPO = "vak2ve/frus-subject-taxonomy"  # adopter override

# This standalone adaptation ships a critical-minerals starter taxonomy as a
# local file. load_taxonomy() loads it directly when present so Records Stage's
# subject filter uses the FSO-facing categories in this repo.
LOCAL_TAXONOMY_FILE = "taxonomy-critical-minerals.json"


def load_taxonomy(path: Optional[Path] = None, repo: Optional[str] = None) -> list[dict]:
    """
    Return the ordered subject taxonomy.

    Each element must contain at minimum:
        name     — display name of the subject
        category — top-level category for the cascade UI
    Recommended optional:
        subcategory, ref, count

    Position in the returned list is the integer index referenced from each
    event's ``sb`` array in the compact cache.

    Adopters can either:
      (a) Override this function entirely to return their own list.
      (b) Wire up the external-taxonomy-export pattern by setting
          DEFAULT_TAXONOMY_REPO at the top of this module and letting the
          ``_resolve_taxonomy_json()`` helper find the file.
    """
    # This instance: load the bundled energy subset directly when no explicit
    # source was requested.
    if not path and not repo and LOCAL_TAXONOMY_FILE:
        local = Path(__file__).resolve().parent / LOCAL_TAXONOMY_FILE
        if local.exists():
            return load_taxonomy_from_bytes(local.read_bytes())

    if not (path or repo or DEFAULT_TAXONOMY_REPO or os.environ.get(TAXONOMY_REPO_ENV)):
        raise NotImplementedError(
            "Adopter must implement load_taxonomy() OR set DEFAULT_TAXONOMY_REPO "
            "at the top of taxonomy.py. Leave it raising to opt out — the "
            "subject filter UI will hide itself."
        )

    data = _resolve_taxonomy_json(path, repo or DEFAULT_TAXONOMY_REPO)
    if data is None:
        # A source WAS configured (path/repo/env) but nothing resolved — a
        # missing file or a failed fetch. Fail loudly instead of silently
        # shipping a tool whose subject filter has mysteriously vanished.
        # (To intentionally skip subjects, opt out via NotImplementedError
        # above rather than pointing at a source that doesn't exist.)
        raise RuntimeError(
            "A taxonomy source was configured but could not be loaded — see the "
            "warnings above for the path/repo that was tried. Fix the source, or "
            "remove the configuration to opt out of subject filtering."
        )
    return _flatten_taxonomy(data)


def load_taxonomy_from_bytes(raw: bytes) -> list[dict]:
    """
    Parse taxonomy JSON from raw bytes (e.g. an uploaded file in a UI) and
    return the ordered flat list used by the compact cache. Exposed so the
    Streamlit wrapper's file-upload path doesn't have to depend on
    filesystem paths or reach into private helpers.
    """
    data = json.loads(raw)
    return _flatten_taxonomy(data)


def enrich(events: list[dict], taxonomy: list[dict]) -> list[dict]:
    """
    Populate event['subject_indices'] from event['subjects'] (list of names).

    Generic, name-based mapping. Adopters who have a richer source-of-truth
    (e.g. a per-document subject export keyed by document ID — see upstream
    ``subject_taxonomy.py:enrich_events_with_subjects``) should override
    this function.
    """
    name_to_index = {t.get("name", t.get("n", "")): i for i, t in enumerate(taxonomy)}
    for event in events:
        names = event.get("subjects") or []
        event["subject_indices"] = sorted(
            name_to_index[n] for n in names if n in name_to_index
        )
    return events


# --- Resolution helpers ----------------------------------------------------


def _resolve_taxonomy_json(path: Optional[Path], repo: str) -> Optional[dict]:
    """Find taxonomy.json by resolution order. Returns parsed dict or None."""
    # 1. Explicit path
    if path:
        if path.exists():
            return _load_json(path)
        print(f"  ⚠ Explicit taxonomy path not found: {path}")

    # 2. TAXONOMY_REPO_DIR env var
    env_dir = os.environ.get(TAXONOMY_REPO_ENV, "").strip()
    if env_dir:
        candidate = Path(env_dir) / "exports" / "taxonomy.json"
        if candidate.exists():
            print(f"  Loading taxonomy from {candidate}")
            return _load_json(candidate)
        print(f"  ⚠ {TAXONOMY_REPO_ENV}={env_dir} but {candidate} not found")

    # 3. Sibling directory
    if repo:
        repo_name = repo.split("/")[-1]
        sibling = Path(__file__).resolve().parent.parent / repo_name / "exports" / "taxonomy.json"
        if sibling.exists():
            print(f"  Loading taxonomy from sibling checkout: {sibling}")
            return _load_json(sibling)

    # 4. GitHub raw
    if repo:
        url = f"https://raw.githubusercontent.com/{repo}/main/exports/taxonomy.json"
        try:
            print(f"  Fetching taxonomy from {url} ...")
            return _fetch_json(url)
        except Exception as e:
            print(f"  ⚠ GitHub fetch failed: {e}")

    return None


def _flatten_taxonomy(data: dict) -> list[dict]:
    """Convert a {categories: [{label, subcategories:[{label, subjects:[...]}]}]}
    document into the ordered flat list used by the compact cache.

    Accepts either of two shapes:
      (a) Has a top-level ``subjectIndex`` list of refs — items emitted in
          the order the refs appear.
      (b) Has only categories/subcategories/subjects — emit subjects in
          encountered order.
    """
    ref_to_entry: dict[str, dict] = {}
    flat_order: list[dict] = []
    for cat in data.get("categories", []):
        cat_label = cat.get("label", "")
        for subcat in cat.get("subcategories", []):
            subcat_label = subcat.get("label", "")
            for subj in subcat.get("subjects", []):
                entry = {
                    "name": subj.get("name", subj.get("label", "")),
                    "category": cat_label,
                    "subcategory": subcat_label,
                    "ref": subj.get("ref", ""),
                    "count": subj.get("count", 0),
                }
                if entry["ref"]:
                    ref_to_entry[entry["ref"]] = entry
                flat_order.append(entry)

    subject_index = data.get("subjectIndex")
    if subject_index:
        ordered = []
        for ref in subject_index:
            if ref in ref_to_entry:
                ordered.append(ref_to_entry[ref])
        return ordered
    return flat_order


def _load_json(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "toolkit-template/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())
