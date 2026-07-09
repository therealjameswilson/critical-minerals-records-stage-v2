"""Network-free tests for github_fetch URL parsing + path layout."""

import pytest

import github_fetch


def test_parse_repo_shorthand_and_urls():
    assert github_fetch.parse_repo("historyatstate/frus") == ("historyatstate", "frus")
    assert github_fetch.parse_repo("github.com/historyatstate/frus") == ("historyatstate", "frus")
    assert github_fetch.parse_repo("https://github.com/historyatstate/frus") == ("historyatstate", "frus")
    assert github_fetch.parse_repo("https://github.com/historyatstate/frus.git") == ("historyatstate", "frus")
    assert github_fetch.parse_repo("  historyatstate/frus/  ") == ("historyatstate", "frus")


@pytest.mark.parametrize("bad", ["", "   ", "not-a-repo", "https://gitlab.com/a/b", "onlyowner"])
def test_parse_repo_rejects_junk(bad):
    with pytest.raises(ValueError):
        github_fetch.parse_repo(bad)


def test_local_path_is_stable_and_namespaced():
    p1 = github_fetch.local_path("historyatstate", "frus")
    p2 = github_fetch.local_path("historyatstate", "frus")
    assert p1 == p2
    assert p1.name == "historyatstate__frus"
    assert p1.parent.name == github_fetch.CORPORA_DIRNAME


def test_clone_url():
    assert github_fetch.clone_url("a", "b") == "https://github.com/a/b.git"
