import pytest
from conftest import AS_OF

from tokyo_pop.checks import (
    DataQualityError,
    check_consistency,
    check_movement,
    check_population,
)
from tokyo_pop.transform import clean_movement, clean_population, normalize_label


def test_normalize_label_strips_footnotes_and_width():
    assert normalize_label("面積（ｋm2）注1）") == "面積(km2)"
    assert normalize_label("町村部　注２）") == "町村部"
    assert normalize_label("人口／総数") == "人口/総数"


def test_clean_population(population_raw):
    df = clean_population(population_raw, AS_OF)
    # Footnotes dropped, the duplicated 区部 / 市部 header rows removed.
    assert df["area_code"].is_unique
    assert len(df) == 72
    assert (df["level"] == 4).sum() == 62
    total = df.loc[df["level"] == 0].iloc[0]
    assert total["population"] == 14_296_683
    assert df.loc[df["area_code"] == "13550", "area_name"].item() == "町村部"
    assert df["population"].dtype == "int64"
    check_population(df)


def test_clean_movement(movement_raw):
    df = clean_movement(movement_raw, AS_OF)
    assert set(df["nationality"]) == {"total", "japanese", "foreign"}
    assert len(df) == 3 * 72
    check_movement(df)


def test_tables_agree(population_raw, movement_raw):
    check_consistency(
        clean_population(population_raw, AS_OF), clean_movement(movement_raw, AS_OF)
    )


def test_check_population_rejects_bad_sum(population_raw):
    df = clean_population(population_raw, AS_OF)
    df.loc[df["area_code"] == "13101", ["population", "male"]] += 1
    with pytest.raises(DataQualityError, match="sum to the prefecture total"):
        check_population(df)


def test_check_movement_rejects_broken_components(movement_raw):
    df = clean_movement(movement_raw, AS_OF)
    df.loc[0, "births"] += 1
    with pytest.raises(DataQualityError, match="natural_net"):
        check_movement(df)


def test_check_movement_allows_census_adjustment_only_in_other_change(movement_raw):
    df = clean_movement(movement_raw, AS_OF)
    total = (df["nationality"] == "total") & (df["area_code"] == "13000")
    df.loc[total, ["other_change", "net_change"]] += 100
    check_movement(df)  # a rebasing correction: accepted

    df.loc[total, "births"] += 100
    df.loc[total, "natural_net"] += 100
    df.loc[total, "net_change"] += 100
    with pytest.raises(DataQualityError, match=r"japanese \+ foreign"):
        check_movement(df)
