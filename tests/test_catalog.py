from datetime import date

from tokyo_pop.catalog import parse_release

BASE = "https://www.toukei.metro.tokyo.lg.jp/jsuikei/2026/js269v0000"


def package(title: str, suffixes=("_1.csv", "_2.csv", "_3.csv")) -> dict:
    return {
        "name": "t000003d2000001181",
        "title": title,
        "resources": [{"url": f"{BASE}{s}"} for s in suffixes],
    }


def test_parse_release_maps_tables_and_date():
    release = parse_release(package("東京都の人口（推計）令和8年9月1日現在"))
    assert release is not None
    assert release.as_of == date(2026, 9, 1)
    assert release.urls == {"population": f"{BASE}_1.csv", "movement": f"{BASE}_3.csv"}


def test_parse_release_ignores_other_datasets():
    assert parse_release(package("高齢者人口（推計）_令和８年９月15日時点")) is None
    assert parse_release(package("東京都の人口（推計）の概要")) is None


def test_parse_release_requires_both_tables():
    assert parse_release(package("東京都の人口（推計）令和8年9月1日現在", ("_1.csv",))) is None
