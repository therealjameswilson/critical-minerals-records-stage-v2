#!/usr/bin/env python3
"""
categorize_subjects.py — Back-fill high-level categories onto already-extracted
State Magazine articles.

Older articles_*.json files store subjects as bare strings (predating the
category-aware extract_articles.py prompt). This script:

  1. Reads every articles_*.json in this directory.
  2. Collects the unique subject strings across all of them.
  3. Asks Claude once to map each subject onto one of the seven canonical
     categories that extract_articles.py uses.
  4. Rewrites every article's `subjects` field in place from
        ["Awards", "Cuba", ...]
     to
        [{"name": "Awards", "category": "Personnel"}, ...]

After this runs, future extractions will already include categories at
extraction time and this script becomes optional.

Cost: ~1 cent per run regardless of how many issues you have (one short
prompt with the unique-subject list).

USAGE:
    python categorize_subjects.py
    python categorize_subjects.py --dry-run    # don't write back; just print
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


CATEGORIES = [
    "Personnel",
    "Posts & Geography",
    "Operations",
    "Events & History",
    "Culture & Community",
    "Health",
    "Other",
]


CATEGORIZATION_PROMPT = """You're assigning a high-level category to each
free-form subject tag from articles in *State Magazine*, the U.S. Department
of State's employee magazine.

Categorize each subject below into EXACTLY one of these categories:

  - Personnel           (awards, retirements, appointments, careers, training)
  - Posts & Geography   (embassies, countries, cities, posts, travel)
  - Operations          (IT, security, inspector general, administrative)
  - Events & History    (conferences, anniversaries, wars, milestones)
  - Culture & Community (arts, music, hobbies, profiles, community)
  - Health              (health programs, wellness, work-life)
  - Other               (use only when no other category fits)

Subjects to categorize:
{subjects}

Output ONLY a JSON object mapping each subject (exactly as written) to its
category string. No preamble, no markdown fences. Example:
{{"Awards": "Personnel", "Cuba": "Posts & Geography", "Music": "Culture & Community"}}
"""


def gather_unique_subjects(this_dir: Path) -> list[str]:
    """Walk every articles_*.json and collect unique subject names."""
    seen: set[str] = set()
    for path in sorted(this_dir.glob("articles_*.json")):
        for article in json.loads(path.read_text(encoding="utf-8")):
            for s in article.get("subjects") or []:
                if isinstance(s, dict):
                    n = (s.get("name") or "").strip()
                elif isinstance(s, str):
                    n = s.strip()
                else:
                    n = ""
                if n:
                    seen.add(n)
    return sorted(seen)


def load_api_key() -> str:
    env = os.environ.get("ANTHROPIC_API_KEY")
    if env:
        return env.strip()
    sibling = Path(__file__).resolve().parent / ".anthropic_key"
    if sibling.exists():
        return sibling.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "Anthropic API key not found. Set ANTHROPIC_API_KEY or save the "
        "key to .anthropic_key in this directory."
    )


def call_claude(subjects: list[str], api_key: str, model: str) -> dict[str, str]:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    prompt = CATEGORIZATION_PROMPT.format(
        subjects="\n".join(f"  - {s}" for s in subjects)
    )
    response = client.messages.create(
        model=model,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    # Tolerate accidental fences
    m = re.match(r"^```(?:json)?\s*\n", text)
    if m:
        text = text[m.end():]
        text = re.sub(r"\n```\s*$", "", text)
    mapping = json.loads(text)
    # Validate categories
    for subj, cat in mapping.items():
        if cat not in CATEGORIES:
            print(f"  ⚠ Claude returned an unknown category for {subj!r}: "
                  f"{cat!r}. Falling back to 'Other'.", file=sys.stderr)
            mapping[subj] = "Other"
    return mapping


def rewrite_articles(this_dir: Path, mapping: dict[str, str], dry_run: bool) -> int:
    """Replace each article's `subjects` field with the categorized objects."""
    touched = 0
    for path in sorted(this_dir.glob("articles_*.json")):
        articles = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for article in articles:
            new_subjects = []
            for s in article.get("subjects") or []:
                if isinstance(s, dict):
                    n = (s.get("name") or "").strip()
                    if not n:
                        continue
                    new_subjects.append({
                        "name": n,
                        "category": s.get("category") or mapping.get(n, "Other"),
                    })
                elif isinstance(s, str) and s.strip():
                    n = s.strip()
                    new_subjects.append({"name": n, "category": mapping.get(n, "Other")})
            if new_subjects != article.get("subjects"):
                article["subjects"] = new_subjects
                changed = True
        if changed:
            touched += 1
            if not dry_run:
                path.write_text(
                    json.dumps(articles, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            print(f"  {'(dry-run) ' if dry_run else ''}updated {path.name}")
    return touched


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="claude-sonnet-4-6")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would change; don't write back.")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    subjects = gather_unique_subjects(here)
    print(f"  Found {len(subjects)} unique subject(s) across articles_*.json")
    if not subjects:
        print("  Nothing to categorize.")
        return

    api_key = load_api_key()
    print(f"  Calling {args.model} for categorization...")
    mapping = call_claude(subjects, api_key, args.model)
    print(f"  Got categories for {len(mapping)} subject(s).")

    # Report category histogram
    from collections import Counter
    hist = Counter(mapping.values())
    for cat in CATEGORIES:
        if hist.get(cat):
            print(f"    {cat:22s} {hist[cat]}")

    touched = rewrite_articles(here, mapping, args.dry_run)
    print(f"\n  {'(dry-run) ' if args.dry_run else ''}Updated {touched} article JSON file(s).")


if __name__ == "__main__":
    main()
