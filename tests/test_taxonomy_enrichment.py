"""Tests for build_cache.resolve_taxonomy + enrich_with_taxonomy — the path
that an incremental merge runs against the COMBINED set of retained + fresh
events. Subjects on retained events must survive the re-enrichment with
correct positional indices, otherwise the publishing tool's subject filter
silently loses its data when an adopter merges only one source."""

import build_cache


def _force_taxonomy_optout(monkeypatch):
    """Force the 'no adopter taxonomy loaded' condition.

    This instance wires a real taxonomy (the FRUS energy subset) via
    taxonomy.load_taxonomy(), so the synthesis fallback below would never fire
    under ambient config. These tests exercise the GENERIC seam behavior, so we
    pin load_taxonomy() to the opted-out state (NotImplementedError) that
    build_cache._load_taxonomy_optional() treats as 'none loaded'."""
    def _optout(*_a, **_k):
        raise NotImplementedError
    monkeypatch.setattr("taxonomy.load_taxonomy", _optout)


def test_resolve_synthesizes_taxonomy_when_none_loaded(monkeypatch):
    """When no adopter taxonomy is loaded, build_cache should synthesize one
    from observed subjects, grouped by subject_categories where supplied
    (else 'Other'). Synthetic subcategory is always 'All'."""
    _force_taxonomy_optout(monkeypatch)
    events = [
        {"subjects": ["Foo", "Bar"], "subject_categories": {"Foo": "Cat1"}},
        {"subjects": ["Bar", "Baz"], "subject_categories": {"Baz": "Cat2"}},
    ]
    tax = build_cache.resolve_taxonomy(events)
    names = {t["name"] for t in tax}
    assert names == {"Foo", "Bar", "Baz"}
    by_name = {t["name"]: t for t in tax}
    assert by_name["Foo"]["category"] == "Cat1"
    assert by_name["Baz"]["category"] == "Cat2"
    # Bar has no category supplied anywhere — falls back to "Other"
    assert by_name["Bar"]["category"] == "Other"
    # The synthetic subcategory is always "All" for free-form subjects
    assert all(t["subcategory"] == "All" for t in tax)


def test_enrich_populates_subject_indices():
    """enrich_with_taxonomy populates each event's subject_indices by name
    lookup against the taxonomy. Indices come back sorted ascending so the
    compact cache writer's output is deterministic."""
    tax = [
        {"name": "Foo", "category": "Cat1", "subcategory": "All"},
        {"name": "Bar", "category": "Cat2", "subcategory": "All"},
    ]
    events = [{"subjects": ["Bar", "Foo"]}, {"subjects": ["Foo"]}]
    out = build_cache.enrich_with_taxonomy(events, tax)
    assert out[0]["subject_indices"] == [0, 1]
    assert out[1]["subject_indices"] == [0]


def test_merge_path_keeps_retained_subjects(monkeypatch):
    """Simulate the merge_sources flow: combine retained + fresh, re-resolve
    the taxonomy over the combined set, re-enrich everything. The retained
    event's subject names must still be reachable from its subject_indices
    in the new taxonomy ordering — otherwise an incremental merge silently
    drops half the corpus from the subject filter UI."""
    _force_taxonomy_optout(monkeypatch)
    retained = [
        {"source": "Other", "subjects": ["Alpha"],
         "subject_categories": {"Alpha": "A"}},
    ]
    fresh = [
        {"source": "State Magazine", "subjects": ["Beta"],
         "subject_categories": {"Beta": "B"}},
    ]
    combined = retained + fresh
    tax = build_cache.resolve_taxonomy(combined)
    combined = build_cache.enrich_with_taxonomy(combined, tax)
    names_by_idx = {i: t["name"] for i, t in enumerate(tax)}
    retained_names = [names_by_idx[i] for i in combined[0]["subject_indices"]]
    assert retained_names == ["Alpha"], \
        "retained event lost its subject during re-enrichment"
