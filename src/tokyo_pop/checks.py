"""Data quality checks. A release that fails any check is rejected, not loaded."""

from __future__ import annotations

import pandas as pd


class DataQualityError(Exception):
    pass


def _require(ok: bool | pd.Series, message: str, df: pd.DataFrame | None = None) -> None:
    if isinstance(ok, pd.Series):
        bad = ok[~ok]
        if bad.empty:
            return
        sample = df.loc[bad.index, ["area_code", "area_name"]].head(5) if df is not None else ""
        raise DataQualityError(f"{message} ({len(bad)} rows)\n{sample}")
    if not ok:
        raise DataQualityError(message)


def check_population(df: pd.DataFrame) -> None:
    _require(df["area_code"].is_unique, "duplicate area codes")
    _require(df["area_name_en"].notna(), "area code without an English name (merger?)", df)
    _require((df["level"] == 0).sum() == 1, "expected exactly one prefecture total row")
    _require((df["level"] == 4).sum() >= 60, "too few municipalities - truncated file?")
    _require(df["population"] == df["male"] + df["female"], "population != male + female", df)
    _require(df["population"] > 0, "non-positive population", df)

    total = df.loc[df["level"] == 0].iloc[0]
    municipalities = df.loc[df["level"] == 4]
    for col in ("population", "households", "change_from_prev_month"):
        _require(
            municipalities[col].sum() == total[col],
            f"municipalities do not sum to the prefecture total for {col}",
        )


def check_movement(df: pd.DataFrame) -> None:
    _require(not df.duplicated(["nationality", "area_code"]).any(), "duplicate rows")
    _require(set(df["nationality"]) == {"total", "japanese", "foreign"}, "missing nationality")
    _require(df["interpref_net"] == df["interpref_in"] - df["interpref_out"], "interpref", df)
    _require(df["intrapref_net"] == df["intrapref_in"] - df["intrapref_out"], "intrapref", df)
    _require(df["natural_net"] == df["births"] - df["deaths"], "natural_net", df)
    components = df["interpref_net"] + df["intrapref_net"] + df["natural_net"] + df["other_change"]
    _require(df["net_change"] == components, "net_change != sum of components", df)

    # total = japanese + foreign, except that a census rebasing month adds a
    # correction to the total's other_change that is not split by nationality.
    # Allow that one gap, and only when net_change shows exactly the same gap.
    numeric = df.select_dtypes("int64").columns.drop("level")
    wide = df.set_index(["area_code", "nationality"])[numeric].unstack("nationality")
    gap = {c: wide[c]["total"] - wide[c]["japanese"] - wide[c]["foreign"] for c in numeric}
    for col in numeric.drop(["net_change", "other_change"]):
        _require((gap[col] == 0).all(), f"total != japanese + foreign for {col}")
    _require(
        (gap["net_change"] == gap["other_change"]).all(),
        "total != japanese + foreign beyond the census adjustment",
    )


def check_consistency(population: pd.DataFrame, movement: pd.DataFrame) -> None:
    """The month's net movement must equal the population change in the other table."""
    totals = movement.loc[movement["nationality"] == "total"].set_index("area_code")["net_change"]
    change = population.set_index("area_code")["change_from_prev_month"]
    joined = pd.concat([change, totals], axis=1, join="inner")
    _require(len(joined) >= 60, "too few areas in common between tables")
    _require(
        (joined["change_from_prev_month"] == joined["net_change"]).all(),
        "population change disagrees with movement table",
    )
