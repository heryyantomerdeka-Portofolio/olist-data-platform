
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

ENDPOINT_URL = os.getenv(
    "MINIO_ENDPOINT",
    "http://localhost:9000",
)

ACCESS_KEY = os.getenv("MINIO_ROOT_USER")
SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD")
BUCKET = os.getenv("S3_BUCKET", "bronze")

print("DEBUG endpoint :", ENDPOINT_URL)
print("DEBUG bucket   :", BUCKET)
print("DEBUG access key tersedia :", bool(ACCESS_KEY))
print("DEBUG secret key tersedia :", bool(SECRET_KEY))

# ============================================================
# 2. VALIDATE CONFIGURATION
# ============================================================

def validate_config():
    missing = []

    if not ENDPOINT_URL:
        missing.append("MINIO_ENDPOINT")

    if not ACCESS_KEY:
        missing.append("MINIO_ROOT_USER")

    if not SECRET_KEY:
        missing.append("MINIO_ROOT_PASSWORD")

    if not BUCKET:
        missing.append("S3_BUCKET")

    if missing:
        raise ValueError(
            "Konfigurasi .env belum lengkap: "
            + ", ".join(missing)
        )


# ============================================================
# 3. CREATE S3 CLIENT
# ============================================================

def create_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=30,
            retries={"max_attempts": 2},
        ),
    )


# ============================================================
# 4. CHECK BUCKET AND LIST BRONZE OBJECTS
# ============================================================

def inspect_bucket(s3):
    print(f"\nEndpoint : {ENDPOINT_URL}")
    print(f"Bucket   : {BUCKET}")
    print("-" * 60)

    print("Memeriksa akses bucket...")

    s3.head_bucket(Bucket=BUCKET)

    print("SUCCESS: bucket dapat diakses.")
    print("\nMembaca daftar objek Bronze...")

    paginator = s3.get_paginator("list_objects_v2")

    object_count = 0

    for page in paginator.paginate(Bucket=BUCKET):
        for obj in page.get("Contents", []):
            object_count += 1

            print(
                f"{object_count:03d}. "
                f"{obj['Key']} "
                f"({obj['Size']:,} bytes)"
            )

    if object_count == 0:
        print("Bucket dapat diakses, tetapi belum ada objek.")

    print("-" * 60)
    print(f"Total objek: {object_count}")


# ============================================================
# 5. MAIN
# ============================================================

def main():
    print("=" * 60)
    print("OLIST DATA PLATFORM - T2 SILVER SOURCE")
    print("=" * 60)

    try:
        validate_config()
        s3 = create_s3_client()
        inspect_bucket(s3)

        print("\nPemeriksaan source selesai.")

    except ClientError as exc:
        error = exc.response.get("Error", {})
        metadata = exc.response.get("ResponseMetadata", {})

        print("\nERROR: operasi MinIO/S3 gagal.")
        print(f"Code   : {error.get('Code')}")
        print(f"Message: {error.get('Message')}")
        print(f"HTTP   : {metadata.get('HTTPStatusCode')}")

        sys.exit(1)

    except BotoCoreError as exc:
        print(f"\nERROR koneksi S3: {exc}")
        sys.exit(1)

    except (ValueError, OSError) as exc:
        print(f"\nERROR konfigurasi: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
