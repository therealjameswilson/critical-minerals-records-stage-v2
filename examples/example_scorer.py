"""
Worked example: a four-axis scoring function.

Mirrors the structure proposed for State Magazine in
docs/state-magazine-portability.md (upstream): author seniority, topic
relevance, editorial salience, anniversary alignment. Total 0–100.

Copy to scorer.py at the template root and adjust the weights to your
corpus's editorial logic.
"""

from __future__ import annotations

# --- Tuning knobs ----------------------------------------------------------

PRIORITY_SUBJECTS = {"Information Technology", "Public Diplomacy"}
ADJACENT_SUBJECTS = {"Communications", "Foreign Service Life"}

# Author title → seniority weight.
AUTHOR_WEIGHTS = {
    "Secretary": 40,
    "Deputy Secretary": 40,
    "Under Secretary": 30,
    "Assistant Secretary": 30,
    "Ambassador": 20,
    "Director": 20,
    "Foreign Service Officer": 10,
}

# Editorial-salience proxies.
COVER_STORY_POINTS = 10
LONG_FORM_WORD_THRESHOLD = 2000
LONG_FORM_POINTS = 5
MULTIMEDIA_POINTS = 5


def score_event(event: dict) -> int:
    """Return an integer score 0–100 across four axes."""
    axes = {
        "author": _author_seniority(event),
        "topic": _topic_relevance(event),
        "salience": _editorial_salience(event),
        "anniversary": _anniversary_alignment(event),
    }
    return sum(axes.values())


def _author_seniority(event: dict) -> int:
    title = (event.get("extra", {}).get("author_title") or "").strip()
    return AUTHOR_WEIGHTS.get(title, 0)


def _topic_relevance(event: dict) -> int:
    subjects = set(event.get("subjects", []))
    if subjects & PRIORITY_SUBJECTS:
        return 30
    if subjects & ADJACENT_SUBJECTS:
        return 20
    if subjects:
        return 10
    return 0


def _editorial_salience(event: dict) -> int:
    extra = event.get("extra", {})
    score = 0
    if extra.get("cover_story"):
        score += COVER_STORY_POINTS
    if (extra.get("word_count") or 0) >= LONG_FORM_WORD_THRESHOLD:
        score += LONG_FORM_POINTS
    if extra.get("media"):
        score += MULTIMEDIA_POINTS
    return score


def _anniversary_alignment(event: dict) -> int:
    # Stub: real adopters wire this to a list of institutional anniversaries.
    return 0
