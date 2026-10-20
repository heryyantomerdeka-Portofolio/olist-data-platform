
import csv
from pathlib import Path

import pandas as pd

from src.t2_silver.contract import SCHEMAS, validate_contract_definition


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
CHUNK_SIZE = 100_000


def read_header(path: Path) -> list[str]:
    """Membaca header asli tanpa mengubah file."""
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return next(csv.reader(file), [])


def conversion_error_mask(series: pd.Series, data_type: str) -> pd.Series:
    """True jika nilai tidak kosong gagal dikonversi ke tipe kontrak."""
    nonempty = series.notna() & series.astype(str).str.strip().ne("")

    if data_type == "string":
        return pd.Series(False, index=series.index)

    if data_type == "timestamp":
        converted = pd.to_datetime(series, errors="coerce")
    elif data_type == "integer":
        converted = pd.to_numeric(series, errors="coerce")
        fractional = converted.notna() & (converted % 1 != 0)
        return nonempty & (converted.isna() | fractional)
    elif data_type == "decimal":
        converted = pd.to_numeric(series, errors="coerce")
    else:
        raise ValueError(f"Tipe data tidak dikenal: {data_type}")

    return nonempty & converted.isna()


def validate_table(table_name: str, contract: dict) -> dict:
    path = RAW_DIR / contract["source_file"]

    if not path.exists():
        return {
            "table": table_name,
            "status": "FAIL",
            "reason": f"File tidak ditemukan: {path}",
        }

    expected = list(contract["columns"].keys())
    actual = read_header(path)

    missing = [col for col in expected if col not in actual]
    unexpected = [col for col in actual if col not in expected]

    if missing or unexpected:
        return {
            "table": table_name,
            "status": "FAIL",
            "reason": (
                f"Kolom hilang: {missing}; "
                f"kolom tidak dikenal: {unexpected}"
            ),
        }

    conversion_errors = {col: 0 for col in expected}
    row_count = 0

    # Semua kolom dibaca sebagai teks dahulu agar ID dan kode pos
    # tidak berubah akibat inferensi tipe otomatis pandas.
    for chunk in pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
        chunksize=CHUNK_SIZE,
    ):
        row_count += len(chunk)

        for col, data_type in contract["columns"].items():
            invalid = conversion_error_mask(chunk[col], data_type)
            conversion_errors[col] += int(invalid.sum())

    invalid_columns = {
        col: count
        for col, count in conversion_errors.items()
        if count > 0
    }

    return {
        "table": table_name,
        "status": "PASS" if not invalid_columns else "CHECK",
        "rows": row_count,
        "reason": (
            "Tipe data dapat dikonversi."
            if not invalid_columns
            else f"Nilai gagal dikonversi: {invalid_columns}"
        ),
    }


def main():
    validate_contract_definition()

    print("=" * 72)
    print("OLIST DATA PLATFORM — SCHEMA VALIDATION")
    print("=" * 72)

    results = []

    for table_name, contract in SCHEMAS.items():
        result = validate_table(table_name, contract)
        results.append(result)

        print(f"\nTabel  : {result['table']}")
        print(f"Status : {result['status']}")

        if "rows" in result:
            print(f"Baris  : {result['rows']:,}")

        print(f"Detail : {result['reason']}")

    failed = [r for r in results if r["status"] == "FAIL"]
    checked = [r for r in results if r["status"] == "CHECK"]

    print("\n" + "=" * 72)
    print(f"Total tabel : {len(results)}")
    print(f"FAIL        : {len(failed)}")
    print(f"CHECK       : {len(checked)}")

    if failed:
        raise SystemExit(
            "\nSchema validation gagal. Perbaiki file/kolom sebelum "
            "melanjutkan ke proses berikutnya."
        )

    if checked:
        print(
            "\nAda nilai yang gagal dikonversi. Ini belum otomatis "
            "berarti tabel harus dikarantina; periksa detailnya dahulu."
        )
    else:
        print("\nSemua header dan tipe data lolos pemeriksaan awal.")


if __name__ == "__main__":
    main()
