
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]
SILVER_DIR = ROOT / "data" / "silver"
OUTPUT_DIR = ROOT / "outputs"
REPORT_PATH = OUTPUT_DIR / "postgres_load_report.json"

TABLE_NAMES = [
    "category_translation",
    "customers",
    "geolocation",
    "orders",
    "order_items",
    "order_payments",
    "order_reviews",
    "products",
    "sellers",
]


def load_project_env() -> None:
    """Load .env values without overwriting existing environment variables."""
    env_path = ROOT / ".env"

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value.startswith(("'", '"')) and value.endswith(
            ("'", '"')
        ):
            value = value[1:-1]

        if key and key not in os.environ:
            os.environ[key] = value


def get_connection_config() -> dict:
    load_project_env()

    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError(
            "POSTGRES_PASSWORD belum tersedia. "
            "Isi variabel tersebut di file .env."
        )

    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5433")),
        "dbname": os.getenv("POSTGRES_DB", "olist"),
        "user": os.getenv("POSTGRES_USER", "olist"),
        "password": password,
        "connect_timeout": 10,
    }


def postgres_type(arrow_type: pa.DataType) -> str:
    """Map supported Parquet types to PostgreSQL types."""
    if pa.types.is_dictionary(arrow_type):
        return postgres_type(arrow_type.value_type)

    if pa.types.is_string(arrow_type) or pa.types.is_large_string(
        arrow_type
    ):
        return "TEXT"

    if pa.types.is_boolean(arrow_type):
        return "BOOLEAN"

    if pa.types.is_integer(arrow_type):
        return "BIGINT"

    if pa.types.is_floating(arrow_type):
        return "DOUBLE PRECISION"

    if pa.types.is_decimal(arrow_type):
        return f"NUMERIC({arrow_type.precision},{arrow_type.scale})"

    if pa.types.is_date(arrow_type):
        return "DATE"

    if pa.types.is_timestamp(arrow_type):
        if arrow_type.tz:
            return "TIMESTAMPTZ"
        return "TIMESTAMP"

    if pa.types.is_time(arrow_type):
        return "TIME"

    raise TypeError(
        f"Tipe Parquet belum didukung: {arrow_type}"
    )


def create_table(cursor, table_name: str, parquet_path: Path) -> int:
    parquet_file = pq.ParquetFile(parquet_path)
    arrow_schema = parquet_file.schema_arrow

    if not arrow_schema.names:
        raise ValueError(f"Tidak ada kolom: {parquet_path.name}")

    column_definitions = []

    for field in arrow_schema:
        column_definitions.append(
            sql.SQL("{} {}").format(
                sql.Identifier(field.name),
                sql.SQL(postgres_type(field.type)),
            )
        )

    cursor.execute(
        sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} ({})").format(
            sql.Identifier("raw"),
            sql.Identifier(table_name),
            sql.SQL(", ").join(column_definitions),
        )
    )

    return parquet_file.metadata.num_rows


def copy_parquet(cursor, table_name: str, parquet_path: Path) -> int:
    """Stream a Parquet file through a temporary CSV into PostgreSQL COPY."""
    parquet_file = pq.ParquetFile(parquet_path)
    expected_rows = parquet_file.metadata.num_rows

    copy_statement = sql.SQL(
        "COPY {}.{} ({}) FROM STDIN WITH "
        "(FORMAT CSV, NULL '\\N')"
    ).format(
        sql.Identifier("raw"),
        sql.Identifier(table_name),
        sql.SQL(", ").join(
            sql.Identifier(name)
            for name in parquet_file.schema_arrow.names
        ),
    )

    copied_rows = 0

    with tempfile.TemporaryDirectory(prefix="olist_t3_") as temp_dir:
        csv_path = Path(temp_dir) / f"{table_name}.csv"

        with pa.OSFile(str(csv_path), "wb") as sink:
            writer_options = pacsv.WriteOptions(
                include_header=False,
                null_string="\\N",
            )

            writer = pacsv.CSVWriter(
                sink,
                parquet_file.schema_arrow,
                write_options=writer_options,
            )

            for batch in parquet_file.iter_batches(batch_size=50_000):
                writer.write_batch(batch)

            writer.close()

        with cursor.copy(copy_statement) as copy:
            with csv_path.open("rb") as csv_file:
                while chunk := csv_file.read(1024 * 1024):
                    copy.write(chunk)

        # COPY's row count is available from the command tag.
        copied_rows = int(cursor.rowcount)

    if copied_rows != expected_rows:
        raise RuntimeError(
            f"{table_name}: sumber {expected_rows:,} baris, "
            f"COPY {copied_rows:,} baris."
        )

    return copied_rows


def main() -> bool:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    missing_files = [
        name
        for name in TABLE_NAMES
        if not (SILVER_DIR / f"{name}.parquet").is_file()
    ]

    if missing_files:
        raise FileNotFoundError(
            "File Silver tidak ditemukan: " + ", ".join(missing_files)
        )

    config = get_connection_config()
    report = {
        "stage": "T3",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "database": config["dbname"],
        "schema": "raw",
        "tables": {},
        "status": "FAILED",
    }

    print(
        f"PostgreSQL: {config['host']}:{config['port']}/"
        f"{config['dbname']}"
    )
    print(f"Memuat {len(TABLE_NAMES)} tabel Silver ke skema raw...")

    # One transaction for all tables: if anything fails, rollback everything.
    with psycopg.connect(**config) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                    sql.Identifier("raw")
                )
            )

            expected_counts = {}

            for table_name in TABLE_NAMES:
                path = SILVER_DIR / f"{table_name}.parquet"
                expected_counts[table_name] = create_table(
                    cursor, table_name, path
                )

            # Truncate and reload in the same transaction.
            cursor.execute(
                sql.SQL("TRUNCATE TABLE {}").format(
                    sql.SQL(", ").join(
                        sql.Identifier("raw", name)
                        for name in TABLE_NAMES
                    )
                )
            )

            for table_name in TABLE_NAMES:
                path = SILVER_DIR / f"{table_name}.parquet"
                expected = expected_counts[table_name]

                copied = copy_parquet(cursor, table_name, path)

                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                        sql.Identifier("raw"),
                        sql.Identifier(table_name),
                    )
                )
                actual = cursor.fetchone()[0]

                if actual != expected or actual != copied:
                    raise RuntimeError(
                        f"Validasi gagal untuk {table_name}: "
                        f"Silver={expected}, COPY={copied}, DB={actual}"
                    )

                report["tables"][table_name] = {
                    "silver_rows": expected,
                    "copied_rows": copied,
                    "database_rows": actual,
                    "status": "PASS",
                }

                print(f"PASS {table_name}: {actual:,} baris")

        # psycopg commits when the connection context exits successfully.

    report["status"] = "PASS"
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["total_rows"] = sum(
        item["database_rows"] for item in report["tables"].values()
    )

    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nT3 berhasil: {report['total_rows']:,} total baris.")
    print(f"Laporan: {REPORT_PATH}")
    return True


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"\nT3 gagal: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
