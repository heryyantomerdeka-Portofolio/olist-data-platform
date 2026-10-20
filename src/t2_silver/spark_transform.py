"""Spark-based type casting and Parquet writer for T2 Silver."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPARK_CONTAINER = "olist-spark-worker"
CONTAINER_PROJECT = "/opt/project"


def write_with_spark(df, contract, table, staging_dir):
    """Run the Spark job in Docker and return (Parquet path, row count)."""
    columns = list(contract["columns"].keys())
    staging_dir = Path(staging_dir)
    input_path = staging_dir / f"{table}_spark_input.csv"
    output_path = staging_dir / f"{table}.parquet"

    if list(df.columns) != columns:
        raise ValueError(
            f"{table}: kolom input tidak sesuai kontrak. "
            f"Expected={columns}; actual={list(df.columns)}"
        )

    # CSV is temporary transport between the Windows Python process
    # and Spark, through the existing Docker bind mount.
    df.to_csv(input_path, index=False, encoding="utf-8")

    def container_path(path):
        return (
            CONTAINER_PROJECT
            + "/"
            + path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
        )

    script_path = (
        f"{CONTAINER_PROJECT}/src/t2_silver/spark_transform.py"
    )

    command = [
        "docker", "exec", SPARK_CONTAINER,
        "/opt/spark/bin/spark-submit",
        "--master", "spark://spark-master:7077",
        "--executor-memory", "480m",
        "--total-executor-cores", "1",
        script_path,
        "--job",
        table,
        container_path(input_path),
        container_path(output_path),
        ",".join(columns),
        ",".join(contract["columns"][c] for c in columns),
    ]

    try:
        subprocess.run(command, check=True)
        if not output_path.is_file():
            raise RuntimeError(
                f"{table}: Spark tidak menghasilkan file {output_path}"
            )
        return output_path, len(df)
    finally:
        input_path.unlink(missing_ok=True)


def run_spark_job(table, input_path, output_path, columns, data_types):
    """Spark-container entry point."""
    from pyspark.sql import SparkSession, functions as F
    from pyspark.sql.types import StringType, LongType, DoubleType
    columns = columns.split(",")
    data_types = data_types.split(",")

    if len(columns) != len(data_types):
        raise ValueError("Daftar kolom dan tipe data tidak sama panjang.")

    spark = (
        SparkSession.builder
        .appName(f"Olist-T2-Silver-{table}")
        .config("spark.sql.ansi.enabled", "false")
        .getOrCreate()
    )

    output_path = Path(output_path)
    temp_output = Path(str(output_path) + ".spark_output")

    try:
        raw = (
            spark.read
            .format("csv")
            .option("header", "true")
            .option("inferSchema", "false")
            .option("encoding", "UTF-8")
            .option("nullValue", "")
            .option("multiLine", "true")
            .option("quote", '"')
            .option("escape", '"')
            .option("mode", "FAILFAST")
            .csv(input_path)
        )


        if raw.columns != columns:
            raise ValueError(
                f"{table}: kolom CSV berubah. "
                f"Expected={columns}; actual={raw.columns}"
            )

        
        invalid_checks = []
        invalid_conditions = {}
        expressions = []

        for index, (name, kind) in enumerate(zip(columns, data_types)):
            source = F.col(name)
            nonempty = source.isNotNull() & (source != "")

            if kind == "string":
                converted = (
                    F.when(source == "", F.lit(None).cast("string"))
                    .otherwise(source.cast(StringType()))
                )

            elif kind == "integer":
                numeric = source.cast(DoubleType())
                converted = source.cast(LongType())

                invalid = nonempty & (
                    numeric.isNull()
                    | converted.isNull()
                    | ((numeric % F.lit(1)) != 0)
                )
                invalid_conditions[name] = invalid
                invalid_checks.append(
                    F.sum(F.when(invalid, 1).otherwise(0))
                    .alias(f"invalid_{index}")
                )

            elif kind == "decimal":
                converted = source.cast(DoubleType())
                invalid = nonempty & converted.isNull()
                invalid_conditions[name] = invalid
                invalid_checks.append(
                    F.sum(F.when(invalid, 1).otherwise(0))
                    .alias(f"invalid_{index}")
                )

            elif kind == "timestamp":
                converted = F.to_timestamp(source)
                invalid = nonempty & converted.isNull()
                invalid_conditions[name] = invalid
                invalid_checks.append(
                    F.sum(F.when(invalid, 1).otherwise(0))
                    .alias(f"invalid_{index}")
                )

            else:
                raise ValueError(
                    f"{table}.{name}: tipe kontrak tidak dikenal: {kind}"
                )

            expressions.append(converted.alias(name))

        # Detect invalid values before writing any Parquet output.
        if invalid_checks:
            invalid_counts = raw.agg(*invalid_checks).first()
            count_values = invalid_counts.asDict()

            problems = {
                columns[int(name.split("_")[1])]: int(value or 0)
                for name, value in count_values.items()
                if int(value or 0) > 0
            }
            if problems:
                samples = {}

                for name in problems:
                    condition = invalid_conditions[name]

                    rows = (
                        raw.filter(condition)
                        .select(name)
                        .limit(10)
                        .collect()
                    )

                    samples[name] = [
                        row[name] for row in rows
                    ]

                raise ValueError(
                    f"{table}: nilai gagal dikonversi: {problems}; "
                    f"contoh nilai bermasalah: {samples}"
                )
        typed = raw.select(*expressions)

        if typed.columns != columns:
            raise ValueError(f"{table}: urutan kolom hasil tidak sesuai.")

        if temp_output.exists():
            shutil.rmtree(temp_output)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # One part file is needed by the existing atomic commit function.
        typed.coalesce(1).write.mode("errorifexists").parquet(
            str(temp_output),
            compression="snappy",
        )

        # Read back and validate the actual Parquet artifact.
        part_files = list(temp_output.glob("part-*.parquet"))
        if len(part_files) != 1:
            raise ValueError(
                f"{table}: diharapkan satu part-file, "
                f"tetapi ditemukan {len(part_files)}."
            )

        os.replace(part_files[0], output_path)
        print(f"SPARK PASS: {table}; columns={len(columns)}")

    finally:
        if temp_output.exists():
            shutil.rmtree(temp_output, ignore_errors=True)
        spark.stop()


if __name__ == "__main__":
    if len(sys.argv) == 7 and sys.argv[1] == "--job":
        _, _, table, input_path, output_path, columns, data_types = sys.argv
        run_spark_job(
            table, input_path, output_path, columns, data_types
        )
    else:
        raise SystemExit("Argumen Spark job tidak valid.")
