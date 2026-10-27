"""Clean the raw CSVs into tidy, typed tables.

The published files are made for humans, not machines:

* notes and the table title are appended below the data rows,
* the 区部 / 市部 subtotal rows appear twice (once in the summary, once as a section header),
* headers carry footnote markers such as ``面積（ｋm2）注1）`` that change between releases,
* numbers can have trailing spaces (``95.7 ``), and area names can carry notes (``町村部　注２）``).
"""

from __future__ import annotations

import io
import re
import unicodedata
from datetime import date

import pandas as pd

from .names import AREA_NAMES_EN

_NOTE = re.compile(r"注\s*\d+\)?")

POPULATION_COLUMNS = {
    "地域階層": "level",
    "地域コード": "area_code",
    "地域": "area_name",
    "人口/総数": "population",
    "人口/男": "male",
    "人口/女": "female",
    "面積(km2)": "area_km2",
    "前月人口との増減": "change_from_prev_month",
    "<参考値>世帯数": "households",
}

MOVEMENT_COLUMNS = {
    "国籍": "nationality",
    "地域階層": "level",
    "地域コード": "area_code",
    "地域": "area_name",
    "全体の増減": "net_change",
    "他県との移動/増減": "interpref_net",
    "他県との移動/転入": "interpref_in",
    "他県との移動/転出": "interpref_out",
    "都内間移動/増減": "intrapref_net",
    "都内間移動/転入": "intrapref_in",
    "都内間移動/転出": "intrapref_out",
    "自然動態/増減": "natural_net",
    "自然動態/出生": "births",
    "自然動態/死亡": "deaths",
    "その他の増減": "other_change",
}

NATIONALITIES = {"総数": "total", "日本人": "japanese", "外国人": "foreign"}

LEVELS = {
    0: "prefecture",
    1: "region",  # 区部・市部・町村部
    2: "subregion",  # 郡部・島部
    3: "branch_office",  # 支庁
    4: "municipality",  # 区市町村
}


def normalize_label(text: str) -> str:
    """NFKC-normalize, drop footnote markers and all whitespace."""
    text = unicodedata.normalize("NFKC", str(text))
    text = _NOTE.sub("", text)
    return re.sub(r"\s+", "", text)


def _read(raw: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig", dtype=str)


def _select(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    df = df.rename(columns=normalize_label)
    missing = set(mapping) - set(df.columns)
    if missing:
        raise ValueError(f"expected columns not found: {sorted(missing)}")
    return df[list(mapping)].rename(columns=mapping)


def _data_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows whose hierarchy level is a digit; footnotes fail this test."""
    level = df["level"].str.strip()
    return df[level.str.fullmatch(r"\d", na=False)].copy()


def _to_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.str.strip().str.replace(",", ""), errors="raise").astype("int64")


def _common(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    df["level"] = df["level"].astype(int)
    df["level_name"] = df["level"].map(LEVELS)
    df["area_code"] = df["area_code"].str.strip()
    df["area_name"] = df["area_name"].map(normalize_label)
    df.insert(df.columns.get_loc("area_name") + 1, "area_name_en", df["area_code"].map(AREA_NAMES_EN))
    df.insert(0, "as_of", pd.Timestamp(as_of))
    return df


def clean_population(raw: bytes, as_of: date) -> pd.DataFrame:
    df = _data_rows(_select(_read(raw), POPULATION_COLUMNS))
    df = _common(df, as_of).drop_duplicates(subset="area_code", keep="first")
    for col in ("population", "male", "female", "change_from_prev_month", "households"):
        df[col] = _to_int(df[col])
    df["area_km2"] = pd.to_numeric(df["area_km2"].str.strip(), errors="raise")
    return df.reset_index(drop=True)


def clean_movement(raw: bytes, as_of: date) -> pd.DataFrame:
    """Population movement during the month *before* ``as_of``."""
    df = _data_rows(_select(_read(raw), MOVEMENT_COLUMNS))
    df["nationality"] = df["nationality"].str.strip().map(NATIONALITIES)
    if df["nationality"].isna().any():
        raise ValueError("unknown nationality label in movement table")
    df = _common(df, as_of).drop_duplicates(subset=["nationality", "area_code"], keep="first")
    for col in MOVEMENT_COLUMNS.values():
        if col not in ("nationality", "level", "area_code", "area_name"):
            df[col] = _to_int(df[col])
    return df.reset_index(drop=True)
