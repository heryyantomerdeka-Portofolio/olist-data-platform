
"""Fungsi pemeriksaan DQ yang bisa diuji tanpa Docker."""

import pandas as pd


def not_null(series: pd.Series) -> pd.Series:
    """Tandai nilai kosong, termasuk string kosong."""
    text = series.astype("string").str.strip()
    return series.isna() | text.eq("").fillna(True)


def unique_duplicates(
    df: pd.DataFrame,
    columns: list[str],
) -> pd.Series:
    """Tandai baris duplikat setelah kemunculan pertama."""
    return df.duplicated(subset=columns, keep="first")


def zip_5_digits(series: pd.Series) -> pd.Series:
    """Tandai kode pos yang tidak terdiri dari tepat 5 digit."""
    text = series.astype("string").str.strip()
    return ~text.str.fullmatch(r"\d{5}", na=False)


def numeric_range(
    series: pd.Series,
    minimum: float,
    maximum: float,
) -> pd.Series:
    """Tandai nilai kosong atau di luar rentang numerik."""
    values = pd.to_numeric(series, errors="coerce")
    return values.isna() | ~values.between(minimum, maximum)


def nonnegative(series: pd.Series) -> pd.Series:
    """Tandai nilai kosong, tidak numerik, atau negatif."""
    values = pd.to_numeric(series, errors="coerce")
    return values.isna() | values.lt(0)


def positive(series: pd.Series) -> pd.Series:
    """Tandai nilai kosong, tidak numerik, atau <= 0."""
    values = pd.to_numeric(series, errors="coerce")
    return values.isna() | values.le(0)


def foreign_key_orphans(
    child: pd.DataFrame,
    child_column: str,
    parent: pd.DataFrame,
    parent_column: str,
) -> pd.Series:
    """Tandai baris anak yang tidak memiliki pasangan di tabel induk."""
    parent_keys = parent[parent_column].dropna()
    child_keys = child[child_column]

    missing_key = not_null(child_keys)
    orphan = ~child_keys.isin(set(parent_keys))

    return missing_key | orphan


def score_range(series: pd.Series) -> pd.Series:
    """review_score harus bilangan bulat 1–5."""
    values = pd.to_numeric(series, errors="coerce")
    return (
        values.isna()
        | ~values.between(1, 5)
        | (values % 1 != 0)
    )
