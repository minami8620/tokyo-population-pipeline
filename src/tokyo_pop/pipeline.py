"""Extract -> transform -> check -> load, one monthly release at a time.

Releases are immutable once published, so a release whose Parquet files already
exist is skipped. Re-running the pipeline is safe and makes no extra requests
beyond the catalog search.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import requests

from .catalog import Release, find_releases
from .checks import check_consistency, check_movement, check_population
from .transform import clean_movement, clean_population

log = logging.getLogger(__name__)


@dataclass
class Paths:
    root: Path

    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def processed(self) -> Path:
        return self.root / "processed"

    def raw_file(self, release: Release, table: str) -> Path:
        return self.raw / release.as_of.isoformat() / f"{table}.csv"

    def parquet(self, release: Release, table: str) -> Path:
        return self.processed / table / f"{release.as_of.isoformat()}.parquet"


def _download(session: requests.Session, url: str, dest: Path) -> bytes:
    if dest.exists():
        return dest.read_bytes()
    response = session.get(url)
    response.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(response.content)
    return response.content


def process_release(session: requests.Session, release: Release, paths: Paths) -> None:
    population = clean_population(
        _download(session, release.urls["population"], paths.raw_file(release, "population")),
        release.as_of,
    )
    movement = clean_movement(
        _download(session, release.urls["movement"], paths.raw_file(release, "movement")),
        release.as_of,
    )
    check_population(population)
    check_movement(movement)
    check_consistency(population, movement)

    for table, df in (("population", population), ("movement", movement)):
        out = paths.parquet(release, table)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out, index=False)


def run(session: requests.Session, data_dir: Path, force: bool = False) -> list[Release]:
    """Load every release not yet in ``data_dir``. Returns the releases that were loaded."""
    paths = Paths(data_dir)
    loaded = []
    for release in find_releases(session):
        done = all(paths.parquet(release, t).exists() for t in ("population", "movement"))
        if done and not force:
            continue
        log.info("loading %s (%s)", release.as_of, release.package_id)
        process_release(session, release, paths)
        loaded.append(release)
    return loaded
