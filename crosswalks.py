"""Helpers for loading critical-minerals YAML crosswalks."""

from __future__ import annotations

from pathlib import Path

import yaml


DEFAULT_CROSSWALK_DIR = Path(__file__).resolve().parent / "data" / "crosswalks"


def load_yaml_crosswalk(name: str, base_dir: Path | None = None) -> dict:
    """Load one YAML crosswalk by file name or stem.

    Example:
        load_yaml_crosswalk("mineral_to_hs_codes")
    """

    root = base_dir or DEFAULT_CROSSWALK_DIR
    path = root / name
    if path.suffix not in {".yml", ".yaml"}:
        path = path.with_suffix(".yml")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Crosswalk {path} must contain a mapping")
    return data
