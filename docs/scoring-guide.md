# Designing a Scoring Function

Scoring is the **editorial seam**. The toolkit never has to know what makes a
document significant in your corpus; you write that down once, in
`scorer.score_event()`.

This guide collects design heuristics from the upstream FRUS scoring function
and the State Magazine scoring proposal. Use it as a starting framework, not
a recipe.

---

## What a scoring function is for

Two purposes, in this order:

1. **Ranking within a day.** Within "January 15," which 3–5 events should
   Records Stage surface to a drafter? Score breaks ties.
2. **Threshold filtering at cache build time.** Events below `MIN_SCORE` are
   excluded from the cache. This is permanent — they're not in
   `events_cache.json` at all.

Threshold filtering is most useful for **large corpora** (FRUS: 172k events,
threshold 30 cuts ~95k of them). For **small corpora** (≲20k events), set
the threshold low and rely on ranking.

---

## Scoring templates (slider-based scorer)

You don't have to write `scorer.py` by hand. With the slider-based scorer
(`scorer.py` re-exporting `axis_scorer`), scoring is a **config you choose and
tune** in the Tune scoring tab, never something a parser decides for you. The
tab offers selectable **templates** from `scoring_presets/`:

- **FRUS standard** — FRUS's original numbers, expressed as three axes over
  signals the FRUS adapter emits: a *weights* axis on `extra.doc_type`, an
  *any-of* axis on `extra.participant_roles` (which takes the highest-weighted
  role — the original "max prestige" rule), and a *weights* axis on
  `extra.classification`. Threshold 30. Load it and every weight is a slider you
  can change.
- **General starter** — a generic four-axis scaffold to edit for a new corpus.

Loading a template writes it to `scoring_config.json`; the sliders then tune it,
and **Save** + rebuild applies it. The build honors the template's `threshold`
(and never drops below `cache_format.MIN_SCORE`, which stays a hard floor at 0).

> One nuance vs. the original FRUS function: there, classification was a
> *displayed label only* and did not count toward the 30 cut. In the template
> it's a real scored axis (same weights), so a Top Secret document now gets a
> small boost toward the threshold. Zero out the Classification axis if you want
> the original pass/fail set exactly.

This is the **neutral-signals** pattern: the parser detects *what a document is*
(type, roles, classification) and the template decides *what that's worth*. It's
the same principle as the "Hidden thresholds" mistake below — the FRUS adapter
emits every energy document unscored, and the scorer/threshold do the cutting.

---

## Multi-axis is almost always right

Single-axis scoring (e.g. "newest first" or "most citations") tends to
produce homogeneous, predictable surfacing. Records Stage is most
useful when the editor sees a mix of obvious-major-event and
unexpected-discovery on the same date.

Aim for **three to five orthogonal axes**, summed into a 0–100 total. Each
axis answers a different "is this worth surfacing?" question.

### Axes that worked for FRUS

| Axis | Range | What it captures |
|---|---|---|
| Document type | 0–40 | Memos of conversation, telegrams, NSC papers all rank differently. |
| Participant prestige | 0–40 | President-level participants rank higher than desk officers. |
| Classification | 0–10 | Top Secret edges Secret edges Confidential. Small weight; recognizes that significance correlates with classification but is not determined by it. |
| **Total** | **0–90** | Threshold: 30. |

### Axes proposed for State Magazine

| Axis | Range | What it captures |
|---|---|---|
| Author seniority | 0–40 | Secretary byline = 40, FSO byline = 10. Senior bylines signal policy weight. |
| Topic relevance | 0–30 | Current editorial priorities, configurable. |
| Editorial salience | 0–20 | Cover story / long-form / multimedia presence. The editors already signaled what they thought was important. |
| Anniversary alignment | 0–10 | Boost when publication date aligns with institutional anniversaries. |
| **Total** | **0–100** | Threshold: 35. |

Notice State Magazine doesn't have a classification axis (no classifications)
but adds an author-seniority axis FRUS doesn't need (FRUS scores prestige
through participant lists, not bylines).

---

## Choosing axis weights

Three rules of thumb:

1. **Weights should reflect editorial reality, not technical neatness.**
   Don't pick 25 + 25 + 25 + 25 because it sums to 100. Pick weights that
   produce rankings the editor would defend.
2. **The dominant axis should swing 30–40% of total range.** If the top axis
   maxes at 10% of total, it can't actually move events between tiers.
3. **Calibrate against ~100 hand-ranked events before locking it in.** The
   editor picks 100 events from their corpus, ranks them, and you tune
   weights until the scorer agrees. Cheaper than any analytical exercise.

---

## Where editorial knowledge belongs

In code, ideally in named constants at the top of `scorer.py`:

```python
PRIORITY_SUBJECTS = {"Information Technology", "Public Diplomacy"}
AUTHOR_WEIGHTS = {"Secretary": 40, "Director": 20, ...}
COVER_STORY_POINTS = 10
```

Reason: editors update these lists; engineers don't. Named constants let an
editor send "please add X to PRIORITY_SUBJECTS" in plain English. If the
editorial knowledge is buried in conditionals, every adjustment becomes a
code review.

---

## Common mistakes

- **Scoring by recency.** "Recent = important" is rarely true for an archive.
  Use recency as a small tiebreaker, not a primary axis.
- **Scoring by length.** Long articles aren't necessarily significant.
  Editorial salience (cover, long-form) is a proxy; length alone isn't.
- **Scoring by URL depth or page rank.** These reflect the publishing
  system, not the editorial significance.
- **Hidden thresholds.** Don't drop events inside `score_event()` —
  always return a score and let the cache builder threshold. Easier to
  retune.
- **Per-source normalization that hides cross-source comparisons.** If your
  cache has multiple sources, decide whether you want them globally
  comparable (one shared scale) or independently ranked (each source has
  its own threshold). The HTML tool surfaces a single sorted list per date,
  so global comparability is the simpler choice.
