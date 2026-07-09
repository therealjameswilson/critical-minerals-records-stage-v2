"""
Fetch a public GitHub repository to use as a corpus source.

Records Studio normally reads a corpus from a local file or folder. Some
archives, though, are published as public GitHub repositories (e.g. the
Office of the Historian's FRUS volumes at github.com/historyatstate/frus).
This helper shallow-clones such a repo to a stable temp directory so the
Connect tab can point ``parser.parse_corpus()`` at it without the adopter
cloning by hand.

It is deliberately generic — it clones *any* public repo. The corpus-specific
knowledge (which files to read, how to parse them) lives in the adopter's
parser, not here.

Design notes
------------
* Shallow clone (``--depth 1``) keeps bandwidth and disk down; we only ever
  read the current state of the files, never history.
* Clones land in ``<tmp>/records_studio_corpora/<owner>__<name>`` so repeated
  builds reuse the same checkout instead of re-downloading. Pass
  ``force=True`` (or call :func:`update_repo`) to refresh.
* No authentication: this is for *public* repos only. A private repo will
  fail at the clone step with git's own error, surfaced to the caller.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

CORPORA_DIRNAME = "records_studio_corpora"
_USER_AGENT = "records-studio/1.0"
RAW_HOST = "https://raw.githubusercontent.com"
API_HOST = "https://api.github.com"

# owner/name, optionally wrapped in a github.com URL, optionally with .git.
_REPO_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/"
    r"(?P<owner>[\w.\-]+)/(?P<name>[\w.\-]+?)(?:\.git)?/?$"
)
_SHORT_RE = re.compile(r"^(?P<owner>[\w.\-]+)/(?P<name>[\w.\-]+?)(?:\.git)?/?$")


def parse_repo(value: str) -> tuple[str, str]:
    """Return ``(owner, name)`` from a repo URL or ``owner/name`` shorthand.

    Accepts, e.g.::

        historyatstate/frus
        github.com/historyatstate/frus
        https://github.com/historyatstate/frus
        https://github.com/historyatstate/frus.git

    Raises ``ValueError`` on anything that doesn't look like a GitHub repo.
    """
    value = (value or "").strip()
    if not value:
        raise ValueError("No repository given.")
    m = _REPO_RE.match(value) or _SHORT_RE.match(value)
    if not m:
        raise ValueError(
            f"{value!r} doesn't look like a GitHub repo. "
            "Use 'owner/name' or a github.com URL."
        )
    return m.group("owner"), m.group("name")


def clone_url(owner: str, name: str) -> str:
    return f"https://github.com/{owner}/{name}.git"


def corpora_root() -> Path:
    root = Path(tempfile.gettempdir()) / CORPORA_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def local_path(owner: str, name: str) -> Path:
    return corpora_root() / f"{owner}__{name}"


def clone_repo(
    repo: str,
    *,
    force: bool = False,
    depth: int = 1,
    timeout: int = 900,
) -> Path:
    """Shallow-clone ``repo`` (URL or ``owner/name``) and return the local path.

    If the repo is already checked out and ``force`` is False, the existing
    checkout is reused (a fast no-op). ``force=True`` deletes and re-clones.

    Raises ``ValueError`` for an unparseable repo, ``RuntimeError`` if git is
    unavailable, and ``subprocess.CalledProcessError`` / ``TimeoutExpired`` if
    the clone itself fails (e.g. private or nonexistent repo).
    """
    owner, name = parse_repo(repo)
    dest = local_path(owner, name)

    if dest.exists() and not force:
        # Reuse an existing checkout. A ".git" presence is a good-enough signal
        # that the previous clone completed.
        if (dest / ".git").exists():
            return dest
        # Half-written or non-git directory — clear and re-clone.
        shutil.rmtree(dest, ignore_errors=True)
    elif dest.exists() and force:
        shutil.rmtree(dest, ignore_errors=True)

    if shutil.which("git") is None:
        raise RuntimeError(
            "git is not installed or not on PATH — cannot clone from GitHub. "
            "Install git, or download the repository manually and point "
            "Records Studio at the local folder instead."
        )

    subprocess.run(
        ["git", "clone", "--depth", str(depth), clone_url(owner, name), str(dest)],
        check=True,
        capture_output=True,
        timeout=timeout,
    )
    return dest


# ---------------------------------------------------------------------------
# Stream-without-download: read individual files over HTTP, no local clone.
#
# For a large repo you only partly need (or have no disk for), cloning is
# wasteful. These helpers fetch one file at a time from raw.githubusercontent
# so a parser can read a corpus in memory and discard each file after parsing.
# ---------------------------------------------------------------------------


def default_branch(owner: str, name: str, *, timeout: int = 30) -> str:
    """Best-effort default branch via the GitHub API; falls back to 'master'."""
    url = f"{API_HOST}/repos/{owner}/{name}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()).get("default_branch") or "master"
    except Exception:
        return "master"


def raw_url(owner: str, name: str, path: str, ref: str) -> str:
    return f"{RAW_HOST}/{owner}/{name}/{ref}/{path.lstrip('/')}"


def fetch_text(owner: str, name: str, path: str, ref: str, *, timeout: int = 120) -> str:
    """Fetch one file's contents as text from raw.githubusercontent.

    Raises ``urllib.error.HTTPError`` (e.g. 404) if the path doesn't exist on
    that ref — callers typically skip-and-continue.
    """
    req = urllib.request.Request(
        raw_url(owner, name, path, ref), headers={"User-Agent": _USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def update_repo(repo: str, *, timeout: int = 900) -> Path:
    """Pull the latest commit into an existing checkout (or clone if absent)."""
    owner, name = parse_repo(repo)
    dest = local_path(owner, name)
    if not (dest / ".git").exists():
        return clone_repo(repo, timeout=timeout)
    subprocess.run(
        ["git", "-C", str(dest), "pull", "--ff-only", "--depth", "1"],
        check=True,
        capture_output=True,
        timeout=timeout,
    )
    return dest
