#!/usr/bin/env python3
"""Extract source-bounded supply-chain geography from the USGS Compendium.

Country production tables provide 1986-1990 mine, concentrate, smelter, and
refinery stages. The cobalt import table provides Census-derived U.S. imports
by country for 1970-1990. Historical country labels are preserved; modern A3
codes are orientation joins, not claims about historical borders.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import urllib.request
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "history-stack" / "supply-chain.json"
ORIENTATION = ROOT / "data" / "atlas" / "world-orientation.geojson"
SOURCE_PAGE = "https://www.usgs.gov/centers/national-minerals-information-center/statistical-compendium"
USER_AGENT = "critical-minerals-history-research/3.0 (official USGS data ingestion)"

TABLES = [
    ("aluminum", "smelting", "World production of primary aluminum, by country", "Thousand metric tons", "aluminum/stats/tbl10.txt", "matrix"),
    ("chromium", "mining", "World annual chromite production, by country", "Thousand metric tons", "chromium/stats/tbl8.txt", "rows"),
    ("cobalt", "mining", "Cobalt: World mine production, by country", "Metric tons cobalt content", "cobalt/status/tbl9.txt", "rows"),
    ("copper", "mining", "World copper mine production", "Thousand metric tons", "copper/stats/tbl12.txt", "rows"),
    ("copper", "smelting", "Copper world smelter production", "Thousand metric tons", "copper/stats/tbl13.txt", "rows"),
    ("copper", "refining", "World copper refinery production", "Thousand metric tons primary and secondary refined copper", "copper/stats/tbl14.txt", "rows"),
    ("manganese", "mining", "Manganese ore: world production, by country", "Thousand metric tons gross weight", "manganese/stats/tbl6.txt", "rows"),
    ("rare-earth-elements", "mining", "Monazite concentrate: world production, by country", "Metric tons gross weight", "rare-earth/stats/tbl5.txt", "rows"),
    ("tin", "mining", "Tin: world mine production, by country", "Metric tons", "tin/stats/tbl2.txt", "rows"),
    ("tin", "smelting", "Tin: world smelter production, by country", "Metric tons", "tin/stats/tbl3.txt", "rows"),
    ("tungsten", "mining", "World tungsten concentrate production, by country", "Metric tons tungsten content", "tungsten/stats/tbl4.txt", "rows"),
]

COBALT_IMPORT_URL = (
    "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/"
    "mineral-pubs/cobalt/status/tbl5.txt"
)

ALUMINUM_BLOCKS = [
    ["Argentina", "Australia", "Austria", "Bahrain", "Brazil", "Cameroon", "Canada", "China", "Czechoslovakia"],
    ["Egypt", "France", "Germany, Federal Republic of: Eastern states", "Germany, Federal Republic of: Western states", "Ghana", "Greece", "Hungary", "Iceland", "India"],
    ["Indonesia", "Iran", "Italy", "Japan", "Korea, North", "Korea, Republic of", "Mexico", "Netherlands", "New Zealand"],
    ["Norway", "Poland", "Romania", "South Africa, Republic of", "Spain", "Suriname", "Sweden", "Switzerland", "Turkey"],
    ["U.S.S.R.", "United Arab Emirates: Dubai", "United Kingdom", "United States", "Venezuela", "Yugoslavia", "Total"],
]

ALIASES = {
    "burma": ("MMR", "historical-name"),
    "czechoslovakia": ("CZE", "historical-state-orientation-proxy"),
    "germany federal republic of eastern states": ("DEU", "historical-state-orientation-proxy"),
    "germany federal republic of western states": ("DEU", "historical-state-orientation-proxy"),
    "germany federal republic of": ("DEU", "historical-name"),
    "korea north": ("PRK", "historical-name"),
    "korea republic of": ("KOR", "historical-name"),
    "south africa republic of": ("ZAF", "historical-name"),
    "u s s r": ("RUS", "historical-state-orientation-proxy"),
    "united states": ("USA", "direct"),
    "united arab emirates dubai": ("ARE", "subnational-orientation-proxy"),
    "yugoslavia": ("SRB", "historical-state-orientation-proxy"),
    "zaire": ("COD", "historical-name"),
    "belgium luxembourg": ("BEL", "combined-geography-orientation-proxy"),
    "rhodesia": ("ZWE", "historical-name"),
    "swaziland": ("SWZ", "historical-name"),
    "ivory coast": ("CIV", "historical-name"),
    "bahrain": ("BHR", "direct"),
    "singapore": ("SGP", "direct"),
    "western states": ("DEU", "table-subregion-orientation-proxy"),
}


def slug(value: str) -> str:
    return "-".join("".join(ch if ch.isalnum() else " " for ch in value.lower()).split())


def normalized_country(value: str) -> str:
    text = re.sub(r"(?:e/|,?\d+/)+$", "", value.strip().rstrip(":")).strip(" ,")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def orientation_names() -> tuple[dict[str, str], dict[str, str]]:
    payload = json.loads(ORIENTATION.read_text(encoding="utf-8"))
    names: dict[str, str] = {}
    labels: dict[str, str] = {}
    for feature in payload["features"]:
        props = feature["properties"]
        code = props["ADM0_A3"]
        labels[code] = props.get("NAME_LONG") or props.get("ADMIN")
        for field in ("ADMIN", "NAME_LONG", "SOVEREIGNT"):
            if props.get(field):
                names[normalized_country(props[field])] = code
    return names, labels


def map_country(source_name: str, names: dict[str, str], labels: dict[str, str]) -> tuple[str | None, str, str | None]:
    normalized = normalized_country(source_name)
    if normalized in ALIASES:
        code, basis = ALIASES[normalized]
        return code, basis, labels.get(code)
    code = names.get(normalized)
    return code, "direct" if code else "unmapped", labels.get(code) if code else None


def fetch(url: str, destination: Path) -> str:
    if not destination.exists():
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            destination.write_bytes(response.read())
    return destination.read_text(encoding="utf-8", errors="replace")


def parse_value(token: str) -> tuple[float | None, bool, str]:
    raw = token.strip()
    if raw in {"--", "NA", "W", "XX"}:
        return None, False, {"W": "withheld", "NA": "not-available"}.get(raw, "not-reported")
    if raw.startswith("("):
        return None, False, "less-than-source-unit"
    estimated = "e/" in raw
    cleaned = raw.replace(",", "").replace("$", "")
    cleaned = re.sub(r"^(?:e/|\d+/)+", "", cleaned)
    match = re.search(r"-?(?:\d+(?:\.\d+)?|\.\d+)$", cleaned)
    if not match:
        return None, estimated, "nonnumeric"
    value = float(match.group())
    return int(value) if value.is_integer() else value, estimated, "reported-estimate" if estimated else "reported"


def year_header(lines: list[str]) -> tuple[int, list[int]]:
    for index, line in enumerate(lines):
        years = [int(value) for value in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", line)]
        if len(years) >= 3:
            return index, years
    raise ValueError("No multi-year header found")


def parse_row_table(text: str) -> list[dict]:
    lines = text.splitlines()
    header_index, years = year_header(lines)
    rows: list[dict] = []
    parent: str | None = None
    for line in lines[header_index + 1:]:
        stripped = line.strip()
        if re.match(r"^(?:e/|\d+/)[A-Za-z]", stripped) or stripped.startswith("Source:"):
            break
        parent_match = re.match(r"^([A-Za-z].*?):(?:e/)?$", stripped)
        if parent_match and "---" not in stripped:
            candidate = re.sub(r"(?:e/|,?\d+/)+$", "", parent_match.group(1).strip()).strip(" ,")
            parent = None if candidate.lower() in {"of which", "grand total"} else candidate
            continue
        match = re.match(r"^\s*(.*?)\s*(?:-{3,}|\.{3,})\s*(.*?)\s*$", line)
        if not match:
            continue
        label = re.sub(r"(?:e/|,?\d+/)+$", "", match.group(1).strip()).strip(" ,")
        if not label:
            continue
        component = "published-row"
        suffix = re.match(r"^(.*?),\s*(primary|secondary)(?:e/)?$", label, flags=re.I)
        is_subregion = bool(parent and re.match(r"^(?:eastern|western) states", label, flags=re.I))
        if suffix:
            source_country = suffix.group(1).strip()
            component = suffix.group(2).lower()
            parent = None
        elif is_subregion or re.match(r"^(?:eastern|western) states", label, flags=re.I):
            state_label = re.sub(r",?\s*(?:total|primary|secondary)(?:e/)?$", "", label, flags=re.I).strip()
            source_country = f"{parent or 'Germany, Federal Republic of'}: {state_label}"
            component_match = re.search(r"(total|primary|secondary)(?:e/)?$", label, flags=re.I)
            component = component_match.group(1).lower() if component_match else "published-row"
        elif parent and label.lower().startswith("total"):
            source_country = parent
            component = "total"
        elif parent and label.lower().startswith(("primary", "secondary")):
            source_country = parent
            component = "primary" if label.lower().startswith("primary") else "secondary"
        else:
            source_country = label
            parent = None
        if source_country.lower().startswith(("total", "other", "world", "grand total", "of which", "primary", "secondary")):
            continue
        tokens = match.group(2).split()
        if len(tokens) < len(years):
            continue
        values = [parse_value(token) for token in tokens[-len(years):]]
        rows.append({"source_country_name": source_country, "component": component, "values": list(zip(years, values))})

    component_countries = {
        row["source_country_name"]
        for row in rows
        if row["component"] in {"primary", "secondary"}
    }
    return [
        row for row in rows
        if not (row["component"] == "total" and row["source_country_name"] in component_countries)
    ]


def parse_aluminum(text: str) -> list[dict]:
    lines = text.splitlines()
    blocks: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in lines:
        match = re.match(r"^\s*(198[6-9]|1990)-{3,}\s*(.*?)\s*$", line)
        if match:
            current.append([match.group(1), *match.group(2).split()])
            if len(current) == 5:
                blocks.append(current)
                current = []
    if len(blocks) != len(ALUMINUM_BLOCKS):
        raise ValueError(f"Expected {len(ALUMINUM_BLOCKS)} aluminum blocks, found {len(blocks)}")
    rows = []
    for countries, block in zip(ALUMINUM_BLOCKS, blocks):
        for column, country in enumerate(countries, start=1):
            if country == "Total":
                continue
            values = []
            for source_row in block:
                if column >= len(source_row):
                    continue
                values.append((int(source_row[0]), parse_value(source_row[column])))
            rows.append({"source_country_name": country, "component": "published-row", "values": values})
    return rows


def production_records(cache_dir: Path, access_date: str, names: dict[str, str], labels: dict[str, str]) -> list[dict]:
    records: list[dict] = []
    base = "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/"
    for mineral_id, stage, title, unit, path, layout in TABLES:
        url = base + path
        text = fetch(url, cache_dir / f"{mineral_id}-{stage}-{Path(path).name}")
        parsed = parse_aluminum(text) if layout == "matrix" else parse_row_table(text)
        for row in parsed:
            code, mapping_basis, orientation_label = map_country(row["source_country_name"], names, labels)
            for year, (value, estimated, status) in row["values"]:
                if value is None:
                    continue
                records.append({
                    "id": f"usgs-compendium-{mineral_id}-{stage}-{slug(row['source_country_name'])}-{year}-{slug(row['component'])}",
                    "record_type": "production",
                    "year": year,
                    "mineral_id": mineral_id,
                    "stage": stage,
                    "source_country_name": row["source_country_name"],
                    "country_iso3": code,
                    "orientation_name": orientation_label,
                    "mapping_basis": mapping_basis,
                    "component": row["component"],
                    "metric": title,
                    "value": value,
                    "unit": unit,
                    "status": status,
                    "estimated": estimated,
                    "agency": "U.S. Geological Survey and predecessor U.S. Bureau of Mines",
                    "publication_title": "USGS Statistical Compendium",
                    "table_or_page": title,
                    "source_id": "usgs-statistical-compendium",
                    "source_url": url,
                    "catalog_url": SOURCE_PAGE,
                    "access_date": access_date,
                    "geographic_precision": "source-country row joined to modern orientation geometry",
                    "caveat": "Production geography is not a shipment route, U.S. supplier share, ownership record, reserve estimate, or measure of political accessibility.",
                })
    return records


def cobalt_import_records(cache_dir: Path, access_date: str, names: dict[str, str], labels: dict[str, str]) -> list[dict]:
    text = fetch(COBALT_IMPORT_URL, cache_dir / "cobalt-imports-by-country-tbl5.txt")
    records: list[dict] = []
    year: int | None = None
    for line in text.splitlines():
        year_match = re.match(r"^\s*(19\d{2}):\s*$", line)
        if year_match:
            year = int(year_match.group(1))
            continue
        if year is None:
            continue
        match = re.match(r"^\s*(.*?)\s*-{3,}\s*(.*?)\s*$", line)
        if not match:
            continue
        country = match.group(1).strip()
        if not country or country.lower().startswith(("total", "other")):
            continue
        tokens = match.group(2).split()
        if not tokens:
            continue
        value, estimated, status = parse_value(tokens[-1])
        if value is None:
            continue
        code, mapping_basis, orientation_label = map_country(country, names, labels)
        records.append({
            "id": f"usgs-compendium-cobalt-imports-{slug(country)}-{year}",
            "record_type": "us-import",
            "year": year,
            "mineral_id": "cobalt",
            "stage": "trade",
            "source_country_name": country,
            "country_iso3": code,
            "orientation_name": orientation_label,
            "mapping_basis": mapping_basis,
            "component": "total cobalt content",
            "metric": "U.S. imports for consumption of cobalt, by country: total cobalt content",
            "value": value,
            "unit": "Metric tons cobalt content",
            "status": status,
            "estimated": estimated,
            "agency": "U.S. Department of Commerce, Bureau of the Census; reproduced by USGS",
            "publication_title": "USGS Statistical Compendium",
            "table_or_page": "Cobalt table 5, U.S. imports for consumption of cobalt, by country",
            "source_id": "usgs-statistical-compendium",
            "source_url": COBALT_IMPORT_URL,
            "catalog_url": SOURCE_PAGE,
            "access_date": access_date,
            "geographic_precision": "reported country row joined to modern orientation geometry",
            "caveat": "Reported country is the published trade partner, not necessarily mine origin, processing location, ownership, route, end use, or political accessibility.",
        })
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--access-date", default=date.today().isoformat())
    args = parser.parse_args()
    names, labels = orientation_names()
    if args.cache_dir:
        args.cache_dir.mkdir(parents=True, exist_ok=True)
        rows = production_records(args.cache_dir, args.access_date, names, labels)
        rows.extend(cobalt_import_records(args.cache_dir, args.access_date, names, labels))
    else:
        with tempfile.TemporaryDirectory(prefix="usgs-supply-chain-") as directory:
            cache = Path(directory)
            rows = production_records(cache, args.access_date, names, labels)
            rows.extend(cobalt_import_records(cache, args.access_date, names, labels))
    rows.sort(key=lambda row: (row["year"], row["mineral_id"], row["stage"], row["source_country_name"], row["component"]))
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate supply-chain record identifiers")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    mapped = sum(bool(row["country_iso3"]) for row in rows)
    print(f"Wrote {len(rows)} supply-chain records ({mapped} map-ready) to {args.output}")


if __name__ == "__main__":
    main()
