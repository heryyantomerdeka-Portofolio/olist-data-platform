
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

PROJECT = Path("/opt/project")
INPUT = str(PROJECT / "data/raw/olist_customers_dataset.csv")
OUTPUT = str(PROJECT / "data/spark_probe/customers")

spark = (
    SparkSession.builder
    .appName("Olist-Bronze-to-Silver-Probe")
    .getOrCreate()
)

try:
    # Baca semua kolom sebagai string terlebih dahulu agar ID
    # dan kode pos tidak kehilangan format aslinya.
    df = (
        spark.read
        .option("header", True)
        .option("encoding", "UTF-8")
        .option("multiLine", True)
        .option("escape", '"')
        .csv(INPUT)
    )

    expected_columns = [
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    ]

    missing = sorted(set(expected_columns) - set(df.columns))
    unexpected = sorted(set(df.columns) - set(expected_columns))

    if missing or unexpected:
        raise ValueError(
            f"Kolom tidak cocok. Missing={missing}, "
            f"Unexpected={unexpected}"
        )

    # Terapkan kontrak tipe data customers.
    df = df.select(
        F.col("customer_id").cast(StringType()),
        F.col("customer_unique_id").cast(StringType()),
        F.col("customer_zip_code_prefix").cast(StringType()),
        F.col("customer_city").cast(StringType()),
        F.col("customer_state").cast(StringType()),
    )

    row_count = df.count()

    print("========== BRONZE TO SILVER PROBE ==========")
    print(f"Input      : {INPUT}")
    print(f"Output     : {OUTPUT}")
    print(f"Jumlah row : {row_count}")
    df.printSchema()

    if row_count != 99441:
        raise ValueError(
            f"Jumlah baris tidak sesuai: {row_count}"
        )

    # Output uji terpisah; tidak menyentuh data/silver yang aktif.
    (
        df.write
        .mode("overwrite")
        .parquet(OUTPUT)
    )

    print("PASS: CSV berhasil ditransformasikan ke Parquet.")

finally:
    spark.stop()
