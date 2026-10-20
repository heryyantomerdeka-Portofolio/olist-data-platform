
from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "outputs"
REPORT_PATH = OUTPUT_DIR / "bronze_report.md"

BUCKET = "bronze"
ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "olistadmin")
SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD")

FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def inspect_file(path: Path) -> dict:
    """Hash bytes and count CSV data rows without loading the whole file."""
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    size_bytes = 0

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            sha256.update(chunk)
            md5.update(chunk)
            size_bytes += len(chunk)

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        next(reader, None)  # header
        row_count = sum(1 for _ in reader)

    return {
        "sha256": sha256.hexdigest(),
        "md5": md5.hexdigest(),
        "size_bytes": size_bytes,
        "row_count": row_count,
    }


def get_manifest(s3, key: str) -> dict | None:
    try:
        response = s3.get_object(Bucket=BUCKET, Key=key)
        body = response["Body"].read()
        return json.loads(body.decode("utf-8"))
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        status = exc.response.get("ResponseMetadata", {}).get(
            "HTTPStatusCode"
        )
        if code in {"NoSuchKey", "NoSuchObject", "NotFound", "404"} or status == 404:
            return None
        raise


def object_exists(s3, key: str) -> bool:
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        status = exc.response.get("ResponseMetadata", {}).get(
            "HTTPStatusCode"
        )
        if code in {"NoSuchKey", "NotFound", "404"} or status == 404:
            return False
        raise


def write_manifest(s3, key: str, manifest: dict) -> None:
    payload = json.dumps(
        manifest, indent=2, ensure_ascii=False
    ).encode("utf-8")

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=payload,
        ContentType="application/json",
    )


def ingest_file(s3, table: str, filename: str) -> dict:
    path = RAW_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"CSV tidak ditemukan: {path}")

    stats = inspect_file(path)
    manifest_key = f"manifests/{table}.json"
    manifest = get_manifest(s3, manifest_key)

    if manifest is None:
        manifest = {
            "table": table,
            "source_filename": filename,
            "created_at": now_utc(),
            "latest_version": 0,
            "versions": [],
        }

    versions = manifest.setdefault("versions", [])
    latest = versions[-1] if versions else None

    # Same as latest version: don't upload data or rewrite the manifest.
    if latest and latest["sha256"] == stats["sha256"]:
        return {
            "file": filename,
            "table": table,
            "status": "unchanged",
            "version": latest["version"],
            **stats,
            "ingested_at": latest["ingested_at"],
        }

    version = len(versions) + 1
    object_key = (
        f"olist/{table}/sha256={stats['sha256']}/{filename}"
    )
    ingested_at = now_utc()

    # If this exact content already exists from an earlier version,
    # reuse it rather than uploading identical bytes again.
    if not object_exists(s3, object_key):
        s3.upload_file(
            str(path),
            BUCKET,
            object_key,
            ExtraArgs={
                "ContentType": "application/octet-stream",
                "Metadata": {
                    "sha256": stats["sha256"],
                    "md5": stats["md5"],
                    "source_filename": filename,
                    "row_count": str(stats["row_count"]),
                },
            },
        )

    version_record = {
        "version": version,
        "sha256": stats["sha256"],
        "md5": stats["md5"],
        "size_bytes": stats["size_bytes"],
        "row_count": stats["row_count"],
        "source_filename": filename,
        "object_key": object_key,
        "ingested_at": ingested_at,
    }
    versions.append(version_record)

    manifest.update({
        "table": table,
        "source_filename": filename,
        "latest_version": version,
        "latest_object_key": object_key,
        "latest_sha256": stats["sha256"],
        "updated_at": ingested_at,
        "versions": versions,
    })

    write_manifest(s3, manifest_key, manifest)

    return {
        "file": filename,
        "table": table,
        "status": "uploaded" if version == 1 else "new_version",
        "version": version,
        **stats,
        "ingested_at": ingested_at,
    }


def write_report(results: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Bronze Ingestion Report",
        "",
        f"Generated at (UTC): {now_utc()}",
        "",
        "| File | Status | Version | Rows | Size (bytes) | SHA-256 | Ingested at (UTC) |",
        "|---|---|---:|---:|---:|---|---|",
    ]

    for result in results:
        lines.append(
            f"| {result['file']} "
            f"| {result['status']} "
            f"| {result['version']} "
            f"| {result['row_count']} "
            f"| {result['size_bytes']} "
            f"| `{result['sha256']}` "
            f"| {result['ingested_at']} |"
        )

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not SECRET_KEY:
        raise RuntimeError(
            "MINIO_ROOT_PASSWORD belum diset di environment PowerShell."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
    )

    # Fail clearly if the bucket is missing or inaccessible.
    s3.head_bucket(Bucket=BUCKET)

    results = []
    for table, filename in FILES.items():
        result = ingest_file(s3, table, filename)
        results.append(result)
        print(
            f"{result['status']:12} "
            f"{filename:45} "
            f"rows={result['row_count']:,} "
            f"version={result['version']}"
        )

    write_report(results)
    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()

