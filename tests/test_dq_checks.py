import pandas as pd

from src.t2_silver.dq_checks import (
    not_null,
    unique_duplicates,
    zip_5_digits,
    numeric_range,
    nonnegative,
    positive,
    foreign_key_orphans,
    score_range,
)


def test_not_null():
    s = pd.Series(["abc", "", None, "  "])
    assert not_null(s).tolist() == [False, True, True, True]


def test_unique_duplicates():
    df = pd.DataFrame({"id": ["A", "B", "A"]})
    assert unique_duplicates(df, ["id"]).tolist() == [False, False, True]


def test_zip_5_digits():
    s = pd.Series(["01234", "12345", "1234", "12A45", None])
    assert zip_5_digits(s).tolist() == [False, False, True, True, True]


def test_numeric_range():
    s = pd.Series(["-91", "0", "45", "91", "bad"])
    assert numeric_range(s, -90, 90).tolist() == [True, False, False, True, True]


def test_nonnegative():
    s = pd.Series(["0", "12.5", "-1", "bad"])
    assert nonnegative(s).tolist() == [False, False, True, True]


def test_positive():
    s = pd.Series(["1", "0", "-2", "bad"])
    assert positive(s).tolist() == [False, True, True, True]


def test_foreign_key_orphans():
    parent = pd.DataFrame({"id": ["A", "B"]})
    child = pd.DataFrame({"parent_id": ["A", "C", None]})
    result = foreign_key_orphans(child, "parent_id", parent, "id")
    assert result.tolist() == [False, True, True]


def test_score_range():
    s = pd.Series(["1", "5", "0", "6", "2.5", "bad"])
    assert score_range(s).tolist() == [False, False, True, True, True, True]
