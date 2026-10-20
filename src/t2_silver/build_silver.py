
"""Build Silver Parquet from verified Bronze data using Spark and a DQ gate."""

import hashlib
import io
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from src.t2_silver.contract import SCHEMAS
from src.t2_silver.source import BUCKET, create_s3_client
from src.t2_silver.evaluate_dq import main as evaluate_dq
from src.t2_silver.spark_transform import write_with_spark


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SILVER_DIR = PROJECT_ROOT / "data" / "silver"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
LOAD_REPORT = OUTPUT_DIR / "load_report.md"


# ============================================================
# 1. READ AND VERIFY BRONZE MANIFEST
# ============================================================

def load_manifest(s3, table):
    key = f"manifests/{table}.json"

    response = s3.get_object(
        Bucket=BUCKET,
        Key=key,
    )

    with response["Body"] as body:
        manifest = json.loads(body.read().decode("utf-8"))

    versions = manifest.get("versions", [])
    latest_version = manifest.get("latest_version")

    matches = [
        version
        for version in versions
        if version.get("version") == latest_version
    ]

    if len(matches) != 1:
        raise ValueError(
            f"{table}: versi terbaru tidak ditemukan secara unik "
            "di manifest."
        )

    latest = matches[0]

    required_fields = [
        "object_key",
        "sha256",
        "size_bytes",
        "row_count",
        "version",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in latest
    ]

    if missing_fields:
        raise ValueError(
            f"{table}: manifest tidak memiliki field "
            f"{missing_fields}."
        )

    return latest


# ============================================================
# 2. READ AND VERIFY BRONZE CSV
# ============================================================

def read_verified_csv(s3, table, contract):
    manifest = load_manifest(s3, table)

    response = s3.get_object(
        Bucket=BUCKET,
        Key=manifest["object_key"],
    )

    with response["Body"] as body:
        raw_bytes = body.read()

    actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    if actual_sha256 != manifest["sha256"]:
        raise ValueError(
            f"{table}: SHA-256 tidak cocok dengan manifest."
        )

    if len(raw_bytes) != manifest["size_bytes"]:
        raise ValueError(
            f"{table}: ukuran file tidak cocok. "
            f"Aktual={len(raw_bytes)}, "
            f"manifest={manifest['size_bytes']}."
        )

    df = pd.read_csv(
        io.BytesIO(raw_bytes),
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    expected_columns = list(contract["columns"])
    actual_columns = list(df.columns)

    missing = [
        column
        for column in expected_columns
        if column not in actual_columns
    ]

    unexpected = [
        column
        for column in actual_columns
        if column not in expected_columns
    ]

    if missing or unexpected:
        raise ValueError(
            f"{table}: header tidak sesuai kontrak. "
            f"Kolom hilang={missing}; "
            f"kolom tak terduga={unexpected}."
        )

    if len(df) != manifest["row_count"]:
        raise ValueError(
            f"{table}: jumlah baris CSV {len(df)} tidak cocok "
            f"dengan manifest {manifest['row_count']}."
        )

    return df[expected_columns].copy(), manifest


# ============================================================
# 3. WRITE AND VERIFY SPARK PARQUET
# ============================================================

def write_staged_parquet(table, df, contract, staging_dir):
    """Write Parquet with Spark in Docker and verify the result."""

    expected_columns = list(contract["columns"])

    if list(df.columns) != expected_columns:
        raise ValueError(
            f"{table}: kolom input tidak cocok dengan kontrak. "
            f"Aktual={list(df.columns)}; "
            f"kontrak={expected_columns}."
        )

    staged_path, spark_rows = write_with_spark(
        df=df,
        contract=contract,
        table=table,
        staging_dir=staging_dir,
    )

    staged_path = Path(staged_path)

    if not staged_path.is_file():
        raise FileNotFoundError(
            f"{table}: Spark tidak menghasilkan file Parquet: "
            f"{staged_path}"
        )

    parquet_file = pq.ParquetFile(staged_path)

    try:
        actual_rows = parquet_file.metadata.num_rows
        actual_columns = parquet_file.schema_arrow.names
    finally:
        parquet_file.close()

    if actual_rows != len(df) or spark_rows != len(df):
        raise ValueError(
            f"{table}: jumlah baris tidak cocok. "
            f"Input={len(df)}, "
            f"Spark={spark_rows}, "
            f"Parquet={actual_rows}."
        )

    if actual_columns != expected_columns:
        raise ValueError(
            f"{table}: schema Parquet tidak cocok. "
            f"Aktual={actual_columns}; "
            f"kontrak={expected_columns}."
        )

    return staged_path, actual_rows


# ============================================================
# 4. WRITE LOAD REPORT
# ============================================================

def write_load_report(
    records,
    status,
    message=None,
    total_seconds=None,
):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Olist Silver Load Report",
        "",
        f"**Status pipeline:** {status}",
        "",
    ]

    if message:
        lines.extend([
            f"**Pesan:** {message}",
            "",
        ])

    lines.extend([
        "| Tabel | Bronze version | Baris sumber | Baris diterima | Karantina | Baris Parquet | Durasi (detik) | Status |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ])

    for record in records:
        lines.append(
            f"| {record['table']} "
            f"| {record.get('version', '-')} "
            f"| {record.get('source_rows', 0)} "
            f"| {record.get('accepted_rows', 0)} "
            f"| {record.get('quarantined_rows', 0)} "
            f"| {record.get('parquet_rows', 0)} "
            f"| {record.get('duration_seconds', 0):.3f} "
            f"| {record.get('status', 'NOT_RUN')} |"
        )

    if total_seconds is not None:
        lines.extend([
            "",
            f"**Total durasi:** {total_seconds:.3f} detik",
        ])

    lines.extend([
        "",
        "Jumlah baris Parquet harus sama dengan jumlah baris diterima.",
        "Baris sumber = baris diterima + baris karantina.",
        "",
    ])

    LOAD_REPORT.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# ============================================================
# 5. COMMIT STAGED FILES WITH ROLLBACK
# ============================================================

def commit_staged_files(staged_files, staging_dir):
    """Replace Silver files and restore previous files on failure."""

    committed_tables = []

    try:
        for table, staged_path in staged_files.items():
            output_path = SILVER_DIR / f"{table}.parquet"
            backup_path = staging_dir / f"{table}.backup.parquet"

            had_original = output_path.exists()

            if had_original:
                os.replace(output_path, backup_path)

            # Register before replacing the staged file. If the second
            # os.replace fails, rollback can restore the original file.
            committed_tables.append({
                "table": table,
                "output_path": output_path,
                "backup_path": backup_path,
                "had_original": had_original,
            })

            os.replace(staged_path, output_path)

    except Exception as commit_error:
        rollback_errors = []

        for item in reversed(committed_tables):
            output_path = item["output_path"]
            backup_path = item["backup_path"]

            try:
                if output_path.exists():
                    output_path.unlink()

                if item["had_original"]:
                    if backup_path.exists():
                        os.replace(backup_path, output_path)
                    else:
                        raise FileNotFoundError(
                            f"Backup tidak ditemukan: {backup_path}"
                        )

            except Exception as rollback_error:
                rollback_errors.append(
                    f"{item['table']}: {rollback_error}"
                )

        if rollback_errors:
            raise RuntimeError(
                f"Commit gagal: {commit_error}. "
                "Rollback juga mengalami kegagalan: "
                + "; ".join(rollback_errors)
                + f". Periksa backup di {staging_dir}."
            ) from commit_error

        raise


# ============================================================
# 6. MAIN: BRONZE -> DQ GATE -> SPARK SILVER
# ============================================================

def build_all():
    started_at = time.perf_counter()

    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    records = []
    staging_files = {}

    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=".silver_staging_",
            dir=SILVER_DIR,
        )
    )

    try:
        # ----------------------------------------------------
        # A. Verify all Bronze tables before processing.
        # ----------------------------------------------------
        print("\n=== T2: BRONZE VERIFICATION ===")

        s3 = create_s3_client()
        source_frames = {}

        for table, contract in SCHEMAS.items():
            table_started = time.perf_counter()

            print(f"\nMemverifikasi Bronze: {table}")

            df, manifest = read_verified_csv(
                s3,
                table,
                contract,
            )

            source_frames[table] = df

            records.append({
                "table": table,
                "version": manifest["version"],
                "source_rows": len(df),
                "accepted_rows": 0,
                "quarantined_rows": 0,
                "parquet_rows": 0,
                "duration_seconds": (
                    time.perf_counter() - table_started
                ),
                "status": "BRONZE_VERIFIED",
            })

            print(f"Versi   : {manifest['version']}")
            print(f"SHA-256 : {manifest['sha256']}")
            print(f"Baris   : {len(df):,}")
            print("Status  : PASS")

        # ----------------------------------------------------
        # B. Evaluate DQ across all tables.
        # ----------------------------------------------------
        print("\n=== T2: DATA QUALITY GATE ===")

        dq_result = evaluate_dq(
            source_frames=source_frames,
        )

        for record in records:
            table = record["table"]
            mask = dq_result["quarantine_masks"][table]

            quarantined_count = int(mask.sum())
            accepted_count = (
                len(source_frames[table]) - quarantined_count
            )

            record["quarantined_rows"] = quarantined_count
            record["accepted_rows"] = accepted_count

            record["status"] = (
                "DQ_FAIL"
                if not dq_result["passed"]
                else (
                    "PASS+KARANTINA"
                    if quarantined_count
                    else "DQ_PASS"
                )
            )

        if not dq_result["passed"]:
            failed_tables = ", ".join(
                dq_result["failed_tables"]
            )

            raise RuntimeError(
                "DQ GATE FAIL. Silver tidak diganti. "
                f"Tabel yang melampaui ambang: {failed_tables}"
            )

        print("\nDQ GATE PASS. Melanjutkan persiapan Silver.")

        # ----------------------------------------------------
        # C. Filter accepted rows and stage every Spark Parquet.
        # Silver final files are not changed in this phase.
        # ----------------------------------------------------
        print("\n=== T2: BUILD SILVER STAGING WITH SPARK ===")

        for record in records:
            table = record["table"]
            contract = SCHEMAS[table]
            table_started = time.perf_counter()

            mask = dq_result["quarantine_masks"][table]

            accepted_df = source_frames[table].loc[
                ~mask,
                list(contract["columns"]),
            ].reset_index(drop=True)

            try:
                staged_path, parquet_rows = write_staged_parquet(
                    table,
                    accepted_df,
                    contract,
                    staging_dir,
                )
            finally:
                del accepted_df

            staging_files[table] = staged_path
            record["parquet_rows"] = parquet_rows

            record["status"] = (
                "PASS+KARANTINA"
                if record["quarantined_rows"]
                else "PASS"
            )

            record["duration_seconds"] += (
                time.perf_counter() - table_started
            )

            print(f"\nTabel         : {table}")
            print(f"Baris sumber  : {record['source_rows']:,}")
            print(f"Baris diterima: {record['accepted_rows']:,}")
            print(f"Karantina     : {record['quarantined_rows']:,}")
            print(f"Parquet rows  : {record['parquet_rows']:,}")
            print(f"File staging  : {staged_path}")
            print("Status        : PASS")

            if record["parquet_rows"] != record["accepted_rows"]:
                raise ValueError(
                    f"{table}: jumlah baris Parquet tidak sama "
                    "dengan jumlah baris diterima."
                )

        # ----------------------------------------------------
        # D. Commit only after all tables are staged and validated.
        # ----------------------------------------------------
        print("\n=== T2: COMMIT SILVER ===")

        commit_staged_files(
            staging_files,
            staging_dir,
        )

        for record in records:
            record["status"] = (
                "PASS+KARANTINA"
                if record["quarantined_rows"]
                else "PASS"
            )

            print(
                f"{record['table']}: "
                f"{SILVER_DIR / (record['table'] + '.parquet')}"
            )

        elapsed = time.perf_counter() - started_at

        write_load_report(
            records,
            status="PASS",
            total_seconds=elapsed,
        )

        print("\n=== T2 COMPLETE ===")
        print(f"Silver directory : {SILVER_DIR}")
        print(f"DQ report        : {OUTPUT_DIR / 'dq_report.md'}")
        print(f"Load report      : {LOAD_REPORT}")
        print(f"Total duration   : {elapsed:.3f} seconds")
        print("Status           : PASS")

        return {
            "passed": True,
            "records": records,
            "duration_seconds": elapsed,
        }

    except Exception as exc:
        elapsed = time.perf_counter() - started_at

        for record in records:
            if record["status"] != "DQ_FAIL":
                record["status"] = "NOT_COMMITTED"

        write_load_report(
            records,
            status="FAIL",
            message=str(exc),
            total_seconds=elapsed,
        )

        print(f"\nT2 FAIL: {exc}")
        print("Periksa outputs/dq_report.md dan outputs/load_report.md.")

        raise

    finally:
        if staging_dir.exists():
            try:
                shutil.rmtree(staging_dir)
            except OSError as cleanup_error:
                print(
                    "PERINGATAN: staging directory tidak dapat "
                    f"dibersihkan: {staging_dir}. "
                    f"Detail: {cleanup_error}"
                )


if __name__ == "__main__":
    build_all()
