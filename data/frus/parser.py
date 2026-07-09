"""
FRUS adapter for Records Studio — Energy & Natural Resources edition.

Reads Foreign Relations of the United States (FRUS) volume XML from a local
checkout of github.com/historyatstate/frus and yields one toolkit "event" per
historically significant document. This instance is **scoped to the Energy and
Natural Resources subject subcategory**: a document is emitted only if it both

  1. carries at least one Energy & Natural Resources subject (per the
     frus-subject-taxonomy ``document_subjects.json`` mapping), and
  2. meets the FRUS interest-score threshold.

Provenance
----------
The document scanner and scoring rules are ported from
``frus-otd/on_this_day.py`` (``parse_frus_volumes``, ``_score_frus_document``);
the subject enrichment is ported from ``frus-otd/subject_taxonomy.py``. Both are
restricted here to the 23-subject energy subset shipped with this repo as
``taxonomy-energy-natural-resources.json``.

Seam contract
-------------
``parse_corpus(source_root)`` yields event dicts matching event_contract:
``source, year, month, day, title, url`` plus ``subjects`` (energy names),
``description``, and an ``extra`` dict carrying ``frus_score`` (read back by
``scorer.score_event``), ``doc_type``, ``classification``,
``recently_published`` and ``pub_year`` (surfaced in the compact cache via
``cache_format.COMPACT_EXTRA_FIELDS``).
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
ENERGY_TAXONOMY_FILE = REPO_ROOT / "taxonomy-energy-natural-resources.json"

# Where document_subjects.json (the doc→subject mapping) can be found.
_TAXONOMY_DIR_ENV = "TAXONOMY_REPO_DIR"
_GITHUB_RAW = "https://raw.githubusercontent.com/{repo}/main/exports/{file}"
_DEFAULT_TAXONOMY_REPO = "vak2ve/frus-subject-taxonomy"

# ---------------------------------------------------------------------------
# Neutral document signals (ported from frus-otd/on_this_day.py)
#
# IMPORTANT: this module no longer *scores* or filters documents. Scoring is an
# editorial decision that belongs to the user, made in Records Studio's
# "Tune scoring" tab (scoring_config.json → axis_scorer). The parser only
# detects and labels the raw signals a scorer might weight:
#
#   doc_type           — the document-type label (one per document)
#   participant_roles  — the senior roles named in the head/participant list
#   classification     — Top Secret / Secret / Confidential / "" (unclassified)
#
# The "FRUS standard" scoring template (scoring_presets/frus_standard.json)
# applies FRUS's original weights to exactly these fields, so every number a
# user could change lives in a config they own, not in this parser.
# ---------------------------------------------------------------------------

# Document type: (regex over head text, label). First match wins; else "Document".
DOC_TYPE_RULES: list[tuple] = [
    (re.compile(r"Memorandum of Conversation", re.I), "Memorandum of Conversation"),
    (re.compile(r"Notes of (?:Meeting|Telephone Conversation|Conversation)", re.I), "Notes of Meeting/Conversation"),
    (re.compile(r"Backchannel (?:Message|Telegram)", re.I), "Backchannel Message"),
    (re.compile(r"(?:Special )?National Intelligence Estimate", re.I), "National Intelligence Estimate"),
    (re.compile(r"(?:Special|Current) Intelligence (?:Memorandum|Bulletin)", re.I), "Intelligence Memorandum"),
    (re.compile(r"Minutes of (?:the )?(?:National Security Council|NSC|Cabinet)", re.I), "NSC/Cabinet Minutes"),
    (re.compile(r"Summary of Conclusions", re.I), "Summary of Conclusions"),
    (re.compile(r"(?:Letter|Message) From (?:the )?President", re.I), "Letter/Message from President"),
    (re.compile(r"Memorandum From (?:the )?President", re.I), "Presidential Memorandum"),
    (re.compile(r"Memorandum From .{0,60}(?:National Security|Assistant to the President)", re.I), "NSA Memorandum"),
    (re.compile(r"(?:Letter|Memorandum) From (?:the )?Secretary of State", re.I), "SecState Memo/Letter"),
    (re.compile(r"Telegram From", re.I), "Telegram"),
    (re.compile(r"(?:Cable|Message) From", re.I), "Cable/Message"),
    (re.compile(r"Memorandum From", re.I), "Memorandum"),
    (re.compile(r"Letter From", re.I), "Letter"),
    (re.compile(r"(?:Paper|Study|Report) Prepared", re.I), "Policy Paper"),
    (re.compile(r"Address (?:by|of)", re.I), "Address/Speech"),
]

# Senior participant roles: (regex over head + participant text, role label).
# ALL matches are collected; the "FRUS standard" template's any-of axis takes
# the highest-weighted match (reproducing the original "max prestige" rule).
PARTICIPANT_ROLE_RULES: list[tuple] = [
    (re.compile(r"\bThe President\b|\bPresident [A-Z][a-z]"), "The President"),
    (re.compile(r"\bGeneral Secretary\b"), "General Secretary"),
    (re.compile(r"\bPrime Minister\b"), "Prime Minister"),
    (re.compile(r"\bChancellor\b"), "Chancellor"),
    (re.compile(r"\bPremier\b"), "Premier"),
    (re.compile(r"\bChairman of the Joint Chiefs\b", re.I), "Chairman of the Joint Chiefs"),
    (re.compile(r"\bChairman\b"), "Chairman"),
    (re.compile(r"\bSecretary of State\b"), "Secretary of State"),
    (re.compile(r"\bNational Security Advis(?:or|er)\b", re.I), "National Security Advisor"),
    (re.compile(r"\bAssistant to the President for National Security\b", re.I), "Assistant to the President for National Security"),
    (re.compile(r"\bSecretary of Defense\b"), "Secretary of Defense"),
    (re.compile(r"\bDirector of Central Intelligence\b", re.I), "Director of Central Intelligence"),
    (re.compile(r"\bVice President\b"), "Vice President"),
    (re.compile(r"\bForeign (?:Minister|Secretary)\b"), "Foreign Minister"),
    (re.compile(r"\bDeputy Secretary\b"), "Deputy Secretary"),
    (re.compile(r"\bAmbassador\b"), "Ambassador"),
    (re.compile(r"\bUnder Secretary\b"), "Under Secretary"),
    (re.compile(r"\bAssistant Secretary\b"), "Assistant Secretary"),
]

# Classification: (regex over source note, label). First match wins.
CLASSIFICATION_RULES: list[tuple] = [
    (re.compile(r"\bTop Secret\b", re.I), "Top Secret"),
    (re.compile(r"\bSecret\b", re.I), "Secret"),
    (re.compile(r"\bConfidential\b", re.I), "Confidential"),
]


def _extract_document_signals(
    head_text: str, participant_text: str, source_note_text: str
) -> dict:
    """Detect neutral, weightable signals for one document. No scoring here."""
    doc_type = "Document"
    for pattern, label in DOC_TYPE_RULES:
        if pattern.search(head_text):
            doc_type = label
            break

    combined = head_text + " " + participant_text
    participant_roles: list[str] = []
    for pattern, label in PARTICIPANT_ROLE_RULES:
        if pattern.search(combined) and label not in participant_roles:
            participant_roles.append(label)

    classification = ""  # "" == unclassified (and the compact cache omits it)
    for pattern, label in CLASSIFICATION_RULES:
        if pattern.search(source_note_text):
            classification = label
            break

    return {
        "doc_type": doc_type,
        "participant_roles": participant_roles,
        "classification": classification,
    }


# ---------------------------------------------------------------------------
# Fast regex scanner helpers (ported from frus-otd/on_this_day.py)
# ---------------------------------------------------------------------------

_RE_DOC_DIV = re.compile(r'<div[^>]*\bsubtype="historical-document"[^>]*>', re.DOTALL)
_RE_ATTR = re.compile(r'([\w:{}./\-]+)="([^"]*)"')
_RE_HEAD_BLOCK = re.compile(r"<head\b[^>]*>(.*?)</head>", re.DOTALL)
_RE_PARTICIPANTS = re.compile(r'<list[^>]*type="participants"[^>]*>(.*?)</list>', re.DOTALL)
_RE_PARTICIPANT_ITEM = re.compile(r"<item\b[^>]*>(.*?)</item>", re.DOTALL)
_RE_SOURCE_NOTE = re.compile(r'<note[^>]*type="source"[^>]*>(.*?)</note>', re.DOTALL)
_RE_NOTE_ELEMENT = re.compile(r'<note\b[^>]*>.*?</note>', re.DOTALL)


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def parse_iso_date(date_str: str) -> Optional[tuple[int, int]]:
    """Extract (month, day) from an ISO-ish date. Returns None if year-only."""
    if not date_str:
        return None
    date_only = date_str.split("T")[0]
    parts = date_only.split("-")
    if len(parts) >= 3:
        try:
            return (int(parts[1]), int(parts[2]))
        except ValueError:
            return None
    return None


def _pub_year_from_text(text: str) -> int:
    """Volume publication year from the teiHeader (scans the first 6 KB)."""
    m = re.search(r'type="publication-date"[^>]*>(\d{4})<', text[:6000])
    return int(m.group(1)) if m else 0


def _get_vol_pub_year(xml_file: Path) -> int:
    """Volume publication year, reading only the first 6 KB of a local file."""
    try:
        with open(xml_file, "rb") as f:
            return _pub_year_from_text(f.read(6000).decode("utf-8", errors="ignore"))
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Energy subject mapping (ported/restricted from frus-otd/subject_taxonomy.py)
# ---------------------------------------------------------------------------


def _load_json_path(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "records-studio-frus/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _resolve_document_subjects() -> Optional[dict]:
    """Find document_subjects.json: env var, sibling checkout, then GitHub."""
    env_dir = os.environ.get(_TAXONOMY_DIR_ENV, "").strip()
    candidates = []
    if env_dir:
        candidates.append(Path(env_dir) / "exports" / "document_subjects.json")
    candidates += [
        REPO_ROOT.parent / "frus-subject-taxonomy" / "exports" / "document_subjects.json",
        Path.home() / "workspace" / "frus-subject-taxonomy" / "exports" / "document_subjects.json",
    ]
    for c in candidates:
        if c.exists():
            print(f"  Loading document_subjects from {c}")
            return _load_json_path(c)
    url = _GITHUB_RAW.format(repo=_DEFAULT_TAXONOMY_REPO, file="document_subjects.json")
    print(f"  Fetching document_subjects from GitHub ({_DEFAULT_TAXONOMY_REPO})...")
    try:
        return _fetch_json(url)
    except Exception as e:  # pragma: no cover - network dependent
        print(f"  ⚠ Could not load document_subjects.json: {e}")
        return None


def _energy_refs_and_names() -> dict[str, str]:
    """ref → subject name for the 23 Energy & Natural Resources subjects."""
    data = _load_json_path(ENERGY_TAXONOMY_FILE)
    out: dict[str, str] = {}
    for cat in data.get("categories", []):
        for subcat in cat.get("subcategories", []):
            for subj in subcat.get("subjects", []):
                ref = subj.get("ref")
                if ref:
                    out[ref] = subj.get("name", ref)
    return out


def load_energy_doc_map() -> dict[tuple[str, str], list[str]]:
    """Build ``(vol_id, doc_id) -> [energy subject names]`` for energy docs only.

    Returns an empty dict (and warns) if the document_subjects mapping can't be
    resolved — the caller then yields no events rather than the full FRUS corpus.
    """
    ref_to_name = _energy_refs_and_names()
    energy_refs = set(ref_to_name)
    ds = _resolve_document_subjects()
    if ds is None:
        return {}

    doc_map: dict[tuple[str, str], list[str]] = {}
    for subj_ref, vol_docs in ds.get("subjects", {}).items():
        if subj_ref not in energy_refs:
            continue
        name = ref_to_name[subj_ref]
        for vol_id, doc_ids_str in vol_docs.items():
            for doc_id in doc_ids_str.split(", "):
                doc_id = doc_id.strip()
                if doc_id:
                    doc_map.setdefault((vol_id, doc_id), []).append(name)
    for key in doc_map:
        # De-dup and stabilise order.
        doc_map[key] = sorted(set(doc_map[key]))
    print(
        f"  ✓ Energy subject map: {len(ref_to_name)} subjects, "
        f"{len(doc_map)} energy documents"
    )
    return doc_map


# ---------------------------------------------------------------------------
# Corpus location
# ---------------------------------------------------------------------------


def _find_volumes_dir(source_root: Path) -> Optional[Path]:
    """Locate the FRUS ``volumes/`` directory under ``source_root``.

    Accepts the cloned frus repo root (``<root>/volumes``), an on_this_day-style
    data dir (``<root>/frus/volumes``), or the volumes directory itself.
    """
    candidates = [
        source_root / "volumes",
        source_root / "frus" / "volumes",
        source_root,
    ]
    for c in candidates:
        if c.is_dir() and any(c.glob("*.xml")):
            return c
    # Last resort: a shallow search a couple levels down.
    for c in source_root.glob("*/volumes"):
        if c.is_dir() and any(c.glob("*.xml")):
            return c
    return None


# ---------------------------------------------------------------------------
# Per-volume scan — shared by the local and streaming paths
# ---------------------------------------------------------------------------


def _iter_volume_events(
    vol_id: str,
    raw: str,
    energy_docs: dict,
    current_year: int,
    seen: set,
) -> Iterator[dict]:
    """Yield energy events from one volume's XML text (in memory)."""
    pub_year = _pub_year_from_text(raw)
    recently_published = pub_year >= (current_year - 5) if pub_year else False

    for m in _RE_DOC_DIV.finditer(raw):
        attrs = dict(_RE_ATTR.findall(m.group(0)))
        dt_min = ""
        doc_id = ""
        for k, v in attrs.items():
            if "doc-dateTime-min" in k:
                dt_min = v
            elif k.endswith("}id") or k == "xml:id":
                doc_id = v

        # Energy filter first — cheapest possible reject before any parsing.
        subjects = energy_docs.get((vol_id, doc_id))
        if not subjects:
            continue

        md = parse_iso_date(dt_min)
        if md is None:
            continue

        window = raw[m.end(): m.end() + 8000]

        head_m = _RE_HEAD_BLOCK.search(window)
        if head_m is None:
            continue
        head_inner = _RE_NOTE_ELEMENT.sub("", head_m.group(1))
        head_inner = re.sub(r"<note\b[^>]*>.*$", "", head_inner, flags=re.DOTALL)
        head_raw = re.sub(r"\s+", " ", _strip_tags(head_inner)).strip()
        head_raw = re.sub(r"^\d+\.\s*", "", head_raw).strip()
        head_raw = re.sub(r"\(\s+", "(", head_raw)
        head_raw = re.sub(r"\s+\)", ")", head_raw)
        head_text = re.sub(r"\s*Source:.*$", "", head_raw, flags=re.DOTALL).strip()

        participant_text = ""
        part_m = _RE_PARTICIPANTS.search(window)
        if part_m:
            items = _RE_PARTICIPANT_ITEM.findall(part_m.group(1))
            participant_text = " ".join(
                re.sub(r"\s+", " ", _strip_tags(it)).strip() for it in items
            )

        source_note_text = ""
        sn_m = _RE_SOURCE_NOTE.search(window)
        if sn_m:
            source_note_text = re.sub(r"\s+", " ", _strip_tags(sn_m.group(1))).strip()

        signals = _extract_document_signals(head_text, participant_text, source_note_text)

        display_title = head_text
        if "Memorandum of Conversation" in head_text and participant_text:
            top = [p.strip() for p in participant_text.split("  ") if p.strip()][:2]
            if top:
                display_title += f" ({'; '.join(top)})"

        month, day = md
        key = (f"{month:02d}", f"{day:02d}", dt_min[:4], display_title[:80])
        if key in seen:
            continue
        seen.add(key)

        classification = signals["classification"]
        # No scoring or threshold here — the parser yields every energy
        # document. The user's scorer (Tune scoring tab) decides what's
        # significant and where the threshold sits.
        yield {
            "source": "Foreign Relations of the United States",
            "year": dt_min[:4],
            "month": f"{month:02d}",
            "day": f"{day:02d}",
            "date_display": dt_min[:10],
            "title": display_title[:250],
            "url": f"https://history.state.gov/historicaldocuments/{vol_id}/{doc_id}",
            "description": (
                f"{signals['doc_type']}"
                + (f" | {classification}" if classification else "")
                + f" | FRUS Volume: {vol_id}"
                + (" | Recently published" if recently_published else "")
            ),
            "subjects": subjects,
            "extra": {
                # Neutral signals for the scorer to weight (or ignore).
                "doc_type": signals["doc_type"],
                "participant_roles": signals["participant_roles"],
                "classification": classification,
                "recently_published": recently_published,
                "pub_year": pub_year,
            },
        }


# ---------------------------------------------------------------------------
# parse_corpus — the seam Records Studio calls
# ---------------------------------------------------------------------------


def parse_corpus(source_root) -> Iterator[dict]:
    """Yield energy-tagged, score-passing FRUS documents.

    ``source_root`` can be:

    * a local path — a clone of github.com/historyatstate/frus, or any directory
      containing a ``volumes/`` folder of FRUS volume XML; or
    * a streaming spec ``"github:owner/name"`` (optionally ``"@ref"``) — read the
      volumes one at a time over HTTP, **without keeping a local copy**. Use this
      when there's no disk for a full clone.
    """
    spec = str(source_root)
    if spec.startswith("github:"):
        remainder = spec[len("github:"):]
        ref = None
        if "@" in remainder:
            remainder, ref = remainder.rsplit("@", 1)
        yield from _parse_corpus_streaming(remainder, ref)
        return
    yield from _parse_corpus_local(Path(source_root))


def _parse_corpus_local(source_root: Path) -> Iterator[dict]:
    volumes_dir = _find_volumes_dir(source_root)
    if volumes_dir is None:
        print(
            f"  ⚠ No FRUS volumes/ directory found under {source_root}. "
            "Point Records Studio at a clone of historyatstate/frus, or use a "
            "'github:historyatstate/frus' streaming source."
        )
        return

    energy_docs = load_energy_doc_map()
    if not energy_docs:
        print("  ⚠ No energy document mapping available — yielding 0 events.")
        return

    energy_vol_ids = {vol for (vol, _doc) in energy_docs}
    xml_files = sorted(volumes_dir.glob("*.xml"))
    current_year = datetime.now().year
    emitted = 0
    seen: set = set()

    for i, xml_file in enumerate(xml_files):
        vol_id = xml_file.stem
        if vol_id not in energy_vol_ids:
            continue
        try:
            raw = xml_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"  Warning: cannot read {vol_id}: {e}")
            continue
        for ev in _iter_volume_events(vol_id, raw, energy_docs, current_year, seen):
            emitted += 1
            yield ev
        if (i + 1) % 50 == 0:
            print(f"    ... scanned {i + 1}/{len(xml_files)} volumes ({emitted} energy events so far)")

    print(f"  ✓ FRUS Energy events: {emitted}")


def _parse_corpus_streaming(repo_spec: str, ref: Optional[str]) -> Iterator[dict]:
    """Stream energy volumes over HTTP, parsing in memory and discarding each.

    Only the energy-bearing volumes (known from the document_subjects mapping)
    are fetched; nothing is written to disk. Trades bandwidth and time for zero
    persistent storage.
    """
    import github_fetch  # local import: only needed for the streaming path

    owner, name = github_fetch.parse_repo(repo_spec)
    if not ref:
        ref = github_fetch.default_branch(owner, name)

    energy_docs = load_energy_doc_map()
    if not energy_docs:
        print("  ⚠ No energy document mapping available — yielding 0 events.")
        return

    vol_ids = sorted({vol for (vol, _doc) in energy_docs})
    current_year = datetime.now().year
    print(
        f"  Streaming {len(vol_ids)} FRUS volumes from {owner}/{name}@{ref} "
        "(no local copy kept)…"
    )

    def _fetch(vol_id: str):
        try:
            return vol_id, github_fetch.fetch_text(owner, name, f"volumes/{vol_id}.xml", ref)
        except Exception as e:  # 404 / transient network — skip this volume
            return vol_id, None

    emitted = 0
    missing = 0
    done = 0
    seen: set = set()

    # Fetch concurrently (I/O-bound), but parse + yield on this thread so the
    # shared `seen` set and the generator stay single-threaded.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_fetch, v): v for v in vol_ids}
        for fut in as_completed(futures):
            vol_id, raw = fut.result()
            done += 1
            if raw is None:
                missing += 1
            else:
                for ev in _iter_volume_events(vol_id, raw, energy_docs, current_year, seen):
                    emitted += 1
                    yield ev
            if done % 50 == 0:
                print(f"    ... streamed {done}/{len(vol_ids)} volumes ({emitted} energy events so far)")

    note = f" ({missing} volumes unavailable on {ref})" if missing else ""
    print(f"  ✓ FRUS Energy events (streamed): {emitted}{note}")
