"""End-to-end run against a fake catalog: no network access."""

from datetime import date

from conftest import FIXTURES

from tokyo_pop import db, pipeline
from tokyo_pop.catalog import Release

RELEASE = Release(
    package_id="t000003d2000001181",
    title="東京都の人口（推計）令和8年9月1日現在",
    as_of=date(2026, 9, 1),
    urls={"population": "https://example/_1.csv", "movement": "https://example/_3.csv"},
)


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        pass


class FakeSession:
    def __init__(self) -> None:
        self.requests: list[str] = []

    def get(self, url, **kwargs):
        self.requests.append(url)
        name = "population" if url.endswith("_1.csv") else "movement"
        return FakeResponse((FIXTURES / f"{name}_2026-09.csv").read_bytes())


def test_run_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "find_releases", lambda session: [RELEASE])
    session = FakeSession()

    assert pipeline.run(session, tmp_path) == [RELEASE]
    assert len(session.requests) == 2
    # Second run: already loaded, nothing downloaded.
    assert pipeline.run(session, tmp_path) == []
    assert len(session.requests) == 2

    con = db.connect(tmp_path)
    assert con.execute("select population from monthly_total").fetchone()[0] == 14_296_683
    assert con.execute("select count(*) from municipality_latest").fetchone()[0] == 62
    assert con.execute("select census_adjustment from nationality_trend").fetchone()[0] == 0
