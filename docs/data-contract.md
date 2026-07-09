# Data shape

The toolkit needs to turn each document in your archive into a small
record — an "event." Your `parser.parse_corpus()` function produces one
of these per document. The toolkit handles everything else.

This page describes the shape of those records.

---

## The shortest possible event

```python
{
    "source": "State Magazine",
    "year":   1995,
    "month":  "03",
    "day":    "15",
    "title":  "Diplomacy in the Digital Age",
    "url":    "https://archive.org/details/sim_state-magazine_1995-03",
}
```

If your parser yields records like this, the toolkit can already do most
of what it does. Everything below is *additions* that make the publishing
tool more useful — none of it is mandatory.

### What each required field is for

| Field | What it is | Example |
|---|---|---|
| `source` | Short label for which archive this came from. Shown as a badge on every tweet card. | `"State Magazine"` |
| `year` | The publication year. **Integer** (not string) — date filters compare numerically. | `1995` |
| `month` | Two-digit month, zero-padded **string**. | `"03"` |
| `day` | Two-digit day, zero-padded **string**. Use `"01"` if you only know the month. | `"15"` |
| `title` | The document's headline or name. Appears as the card title. | `"Diplomacy in the Digital Age"` |
| `url` | A stable link to the original document. The publishing tool links here; it doesn't fetch the content. | `"https://archive.org/..."` |

The toolkit caches events by `"MM-DD"` key (so `"03-15"` here), which is
why month and day are strings. `"3"` and `"03"` would collide.

---

## Recommended extras

These aren't required, but the publishing tool surfaces them if you
provide them:

| Field | What it powers |
|---|---|
| `description` | A 1–2 sentence summary. Used for keyword search in the document browser. |
| `subjects` | A list of topic tags (strings). Powers the topic-filter pane in the publishing tool. |
| `date_display` | Human-readable date (e.g. `"March 1995"`) shown in Records Stage. If omitted, the tool falls back to constructing one from year/month/day. |

A typical, fully-fleshed-out event:

```python
{
    "source":       "State Magazine",
    "year":         1995,
    "month":        "03",
    "day":          "15",
    "date_display": "March 1995",
    "title":        "Diplomacy in the Digital Age",
    "url":          "https://archive.org/details/sim_state-magazine_1995-03",
    "description":  "Feature article on emerging IT challenges in the Foreign Service.",
    "subjects":     ["Information Technology", "Public Diplomacy"],
}
```

---

## Anything corpus-specific goes in `extra`

`extra` is a free-form dict for fields the toolkit doesn't have an
opinion about. The cache builder threads it through to the JSON output
verbatim; nothing breaks if you add fields the toolkit doesn't know.

```python
"extra": {
    "author":      "Smith, Jane",
    "page_start":  12,
    "department":  "IRM",
    "word_count":  2400,
}
```

If you want a specific `extra` field to appear in the publishing tool
(as a filter, badge, or column), register it in
[`cache_format.COMPACT_EXTRA_FIELDS`](../cache_format.py) — that's a
small dev-level wiring step, [described below](#under-the-hood).

---

## What the cache builder fills in automatically

These fields get computed for you. Your parser does **not** set them.

| Field | Set by |
|---|---|
| `score` | `scorer.score_event()` runs each event through your scoring rules |
| `subject_indices` | If you've loaded a subject taxonomy, the names in `subjects` get translated into integer indices |

---

## What the toolkit doesn't store

- **Document body text.** The cache is metadata-only by design. See
  [Constraints](constraints.md) for why and what that means.
- **Anything not in this schema** — the publishing tool can only surface
  fields it knows about.

---

## Under the hood

The rest of this page is for developers wiring up a new field or
debugging the cache. Most adopters never need it.

### Compact JS encoding

The full JSON record (above) is the source of truth in
`events_cache.json`. A *compact* version, `events_cache.js`, is what
gets embedded in the HTML publishing tool. It uses short keys to save
bytes:

```javascript
{
    y: 1995,            // year
    t: "Diplomacy …",   // title
    u: "https://…",     // url
    s: "State Magazine",// source
    sc: 62,             // score
    sb: [3, 12, 87],    // subject indices into SUBJECT_TAXONOMY
    // any extras registered in COMPACT_EXTRA_FIELDS:
    au: "Smith, Jane",
    dp: "IRM",
}
```

The compact format drops `description`, `date_display`, `month`, `day`,
and any `extra.*` fields that aren't registered in
`cache_format.COMPACT_EXTRA_FIELDS`.

### Cache file layout

```
events_cache.json
{
  "01-01": [ {event}, {event}, ... ],
  "01-02": [ {event}, {event}, ... ],
  ...
  "12-31": [ {event}, ... ]
}
```

Keys are `"MM-DD"` strings. Within each day, events are sorted by score
descending. Days with no events are simply absent from the dict.

### Adding a corpus-specific field

```text
1. Parser emits it:    event["extra"]["priority_flag"] = ...
2. cache_format.py:    add "priority_flag": "pf" to COMPACT_EXTRA_FIELDS
3. records-stage.html: render or filter on event.pf
```
