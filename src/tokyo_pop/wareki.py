"""Parse Japanese era dates (和暦) such as 令和8年9月1日 into ``datetime.date``."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

# First Gregorian year of each era, minus one (so year N of the era = offset + N).
ERA_OFFSETS = {
    "令和": 2018,
    "平成": 1988,
    "昭和": 1925,
}

_PATTERN = re.compile(
    r"(?P<era>令和|平成|昭和)\s*(?P<year>元|\d+)\s*年\s*(?P<month>\d+)\s*月\s*(?:(?P<day>\d+)\s*日)?"
)


def parse_wareki(text: str) -> date:
    """Return the first era date found in ``text``.

    Handles full-width digits (令和８年), the first year written as 元 (令和元年),
    and month-only dates (令和8年9月 -> the 1st of that month).
    """
    normalized = unicodedata.normalize("NFKC", text)
    match = _PATTERN.search(normalized)
    if not match:
        raise ValueError(f"no Japanese era date found in {text!r}")
    year = 1 if match["year"] == "元" else int(match["year"])
    day = int(match["day"]) if match["day"] else 1
    return date(ERA_OFFSETS[match["era"]] + year, int(match["month"]), day)
