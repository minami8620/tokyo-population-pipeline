"""Discover monthly releases through the Tokyo Open Data catalog (CKAN API)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

import requests

from .wareki import parse_wareki

CKAN_API = "https://catalog.data.metro.tokyo.lg.jp/api/3/action"
SEARCH_QUERY = 'title:"東京都の人口（推計）"'
# After NFKC normalization: 東京都の人口(推計)令和8年9月1日現在
TITLE_PATTERN = re.compile(r"^東京都の人口\(推計\)\s*(?P<date>(?:令和|平成).+?日)現在$")

# Each release ships several CSVs; the file suffix identifies the table.
TABLES = {"_1.csv": "population", "_3.csv": "movement"}


@dataclass(frozen=True)
class Release:
    package_id: str
    title: str
    as_of: date
    urls: dict[str, str]  # table name -> CSV URL


def parse_release(package: dict) -> Release | None:
    """Turn a CKAN package into a ``Release``, or ``None`` if it is a different dataset."""
    title = unicodedata.normalize("NFKC", package["title"]).strip()
    match = TITLE_PATTERN.match(title)
    if not match:
        return None
    urls = {}
    for resource in package.get("resources", []):
        url = resource.get("url", "")
        for suffix, table in TABLES.items():
            if url.lower().endswith(suffix):
                urls[table] = url
    if set(urls) != set(TABLES.values()):
        return None
    return Release(package["name"], package["title"], parse_wareki(match["date"]), urls)


def find_releases(session: requests.Session, page_size: int = 100) -> list[Release]:
    """Return every monthly release currently listed in the catalog, oldest first."""
    releases: dict[date, Release] = {}
    start = 0
    while True:
        response = session.get(
            f"{CKAN_API}/package_search",
            params={"q": SEARCH_QUERY, "rows": page_size, "start": start},
        )
        response.raise_for_status()
        result = response.json()["result"]
        for package in result["results"]:
            release = parse_release(package)
            if release:
                releases[release.as_of] = release
        start += page_size
        if start >= result["count"]:
            break
    return [releases[d] for d in sorted(releases)]
