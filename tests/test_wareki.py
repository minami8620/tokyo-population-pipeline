from datetime import date

import pytest

from tokyo_pop.wareki import parse_wareki


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("令和8年9月1日", date(2026, 9, 1)),
        ("令和８年１０月１日現在", date(2026, 10, 1)),  # full-width digits
        ("令和元年5月1日", date(2019, 5, 1)),  # first year written as 元
        ("平成31年4月30日", date(2019, 4, 30)),
        ("昭和64年1月7日", date(1989, 1, 7)),
        ("東京都の人口（推計）_令和7年10月", date(2025, 10, 1)),  # month only
    ],
)
def test_parse_wareki(text, expected):
    assert parse_wareki(text) == expected


def test_parse_wareki_rejects_text_without_era():
    with pytest.raises(ValueError):
        parse_wareki("2026年9月1日")
