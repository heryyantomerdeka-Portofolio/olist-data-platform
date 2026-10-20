from pathlib import Path
from io import BytesIO
import os

import boto3
import pandas as pd
from sqlalchemy import URL, create_engine, text
from botocore.client import Config
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
OUTPUT_DIR = ROOT / "outputs" / "gold"

def load_env(path):
    if not path.exists():
        raise FileNotFoundError(f".env tidak ditemukan: {path}")

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)

load_env(ENV_FILE)

required = ["POSTGRES_PASSWORD", "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD"]
missing = [key for key in required if not os.getenv(key)]
if missing:
    raise RuntimeError(f"Variabel .env belum tersedia: {', '.join(missing)}")

db_url = URL.create(
    drivername="postgresql+psycopg2",
    username=os.getenv("POSTGRES_USER", "olist"),
    password=os.environ["POSTGRES_PASSWORD"],
    host="localhost",
    port=5433,
    database=os.getenv("POSTGRES_DB", "olist"),
)

engine = create_engine(db_url)

endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000").strip()
if not endpoint.startswith(("http://", "https://")):
    endpoint = f"http://{endpoint}"

# Untuk eksekusi dari Windows, gunakan endpoint MinIO yang dipublikasikan.
if endpoint.split("://", 1)[-1].startswith(("minio:", "olist-minio:")):
    endpoint = "http://localhost:9000"

s3 = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=os.environ["MINIO_ROOT_USER"],
    aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
    region_name="us-east-1",
    config=Config(signature_version="s3v4"),
)

bucket = "gold"
prefix = "t5_marts"

try:
    s3.head_bucket(Bucket=bucket)
    print(f"Bucket tersedia: {bucket}")
except ClientError as exc:
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    code = exc.response.get("Error", {}).get("Code", "")
    if status == 404 or code in ("404", "NoSuchBucket", "NotFound"):
        s3.create_bucket(Bucket=bucket)
        print(f"Bucket dibuat: {bucket}")
    else:
        raise RuntimeError(
            f"Gagal memeriksa bucket {bucket}; periksa endpoint dan kredensial MinIO."
        ) from exc

marts = [
    "customer_rfm",
    "delivery_performance",
    "monthly_sales",
    "order_reconciliation",
    "seller_scorecard",
    "stream_freshness",
]

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
results = []

with engine.connect() as conn:
    for mart in marts:
        table = f"mart.{mart}"
        print(f"\nMemproses {table}...")

        expected = conn.execute(
            text(f'SELECT COUNT(*) FROM "{ "mart" }"."{mart}"')
        ).scalar_one()

        df = pd.read_sql_query(
            text(f'SELECT * FROM "{ "mart" }"."{mart}"'),
            conn,
        )

        if len(df) != expected:
            raise RuntimeError(
                f"{table}: jumlah baris query {len(df)} != COUNT(*) {expected}"
            )

        buffer = BytesIO()
        df.to_parquet(buffer, index=False, engine="pyarrow")
        buffer.seek(0)

        local_file = OUTPUT_DIR / f"{mart}.parquet"
        local_file.write_bytes(buffer.getvalue())

        key = f"{prefix}/{mart}.parquet"
        buffer.seek(0)
        s3.upload_fileobj(
            buffer,
            bucket,
            key,
            ExtraArgs={"ContentType": "application/vnd.apache.parquet"},
        )

        # Baca ulang objek yang sudah diunggah dan validasi jumlah baris.
        downloaded = BytesIO()
        s3.download_fileobj(bucket, key, downloaded)
        downloaded.seek(0)
        exported_df = pd.read_parquet(downloaded, engine="pyarrow")

        if len(exported_df) != expected:
            raise RuntimeError(
                f"Validasi gagal untuk {key}: sumber={expected}, "
                f"hasil ekspor={len(exported_df)}"
            )

        results.append({
            "mart": table,
            "source_rows": expected,
            "exported_rows": len(exported_df),
            "columns": len(exported_df.columns),
            "status": "PASS",
            "s3_uri": f"s3://{bucket}/{key}",
        })

        print(f"PASS | {expected:,} baris | s3://{bucket}/{key}")

report = pd.DataFrame(results)
report_path = OUTPUT_DIR / "export_validation.csv"
report.to_csv(report_path, index=False)

print("\n=== RINGKASAN EKSPOR ===")
print(report.to_string(index=False))
print(f"\nLaporan validasi: {report_path}")
print("Selesai: seluruh mart berhasil diekspor dan divalidasi.")
