
import argparse
import sys
from pathlib import Path
import subprocess


def run_t0():
    print("T0 - Persiapan environment")
    root = Path(__file__).resolve().parent
    raw_dir = root / "data" / "raw"
    env_file = root / ".env"

    required_files = [
        "olist_customers_dataset.csv",
        "olist_geolocation_dataset.csv",
        "olist_orders_dataset.csv",
        "olist_order_items_dataset.csv",
        "olist_order_payments_dataset.csv",
        "olist_order_reviews_dataset.csv",
        "olist_products_dataset.csv",
        "olist_sellers_dataset.csv",
        "product_category_name_translation.csv",
    ]

    missing = [
        name for name in required_files
        if not (raw_dir / name).is_file()
    ]

    if missing:
        raise FileNotFoundError(
            "CSV wajib tidak ditemukan di data/raw: "
            + ", ".join(missing)
        )

    if not env_file.is_file():
        raise FileNotFoundError(
            f"File konfigurasi .env tidak ditemukan: {env_file}"
        )

    from dotenv import load_dotenv
    import importlib.util
    import os

    load_dotenv(env_file, override=False)

    required_env = [
        "MINIO_ROOT_PASSWORD",
        "POSTGRES_PASSWORD",
    ]
    missing_env = [
        key for key in required_env
        if not os.getenv(key)
    ]

    if missing_env:
        raise RuntimeError(
            "Variabel environment wajib belum tersedia: "
            + ", ".join(missing_env)
        )

    required_modules = ["pandas", "boto3", "dotenv"]
    missing_modules = [
        name for name in required_modules
        if importlib.util.find_spec(name) is None
    ]

    if missing_modules:
        raise RuntimeError(
            "Dependensi Python belum tersedia: "
            + ", ".join(missing_modules)
        )

    print(f"PASS: {len(required_files)} file CSV ditemukan.")
    print("PASS: file .env tersedia dan variabel wajib terisi.")
    print("PASS: dependensi pandas, boto3, dan python-dotenv tersedia.")
    print("Status: T0 PASS; pemeriksaan tidak mengubah data.")


def run_t1():
    print("T1 - Bronze ingestion")
    root = Path(__file__).resolve().parent

    from dotenv import load_dotenv

    env_file = root / ".env"
    if not env_file.is_file():
        raise FileNotFoundError(
            f"File konfigurasi .env tidak ditemukan: {env_file}"
        )

    # Muat environment sebelum modul ingestion membaca os.getenv().
    load_dotenv(env_file, override=False)

    from scripts.ingest_bronze import main as ingest_bronze

    # main() melempar exception jika autentikasi, bucket, atau
    # proses ingestion gagal. Exception diteruskan ke pipeline.
    ingest_bronze()

    report = root / "outputs" / "bronze_report.md"
    if not report.is_file():
        raise RuntimeError(
            "Ingestion selesai tanpa menghasilkan bronze_report.md."
        )

    print("Status: T1 selesai; laporan Bronze tersedia.")



def run_t2():
    """T2: Build Silver, lalu load tabel raw ke PostgreSQL."""
    print("\n=== T2: SILVER + POSTGRESQL ===")

    from src.t2_silver.build_silver import build_all
    from scripts.ingest_to_postgres import main as load_postgres

    # Langkah 1: membangun Silver dari Bronze.
    result = build_all()

    if not result or not result.get("passed"):
        raise RuntimeError("T2 Silver gagal.")

    print("\nSilver berhasil dibangun.")

    # Langkah 2: memuat Silver ke PostgreSQL.
    loaded = load_postgres()

    if not loaded:
        raise RuntimeError("T2 gagal memuat data ke PostgreSQL.")

    print("\nT2 selesai: Silver dan PostgreSQL berhasil.")


def run_t3(mode, extra_args=None):
    """T3: Jalankan Kafka streaming producer atau consumer."""
    if extra_args is None:
        extra_args = []

    print(f"\n=== T3: KAFKA STREAMING ({mode}) ===")

    root = Path(__file__).resolve().parent

    modules = {
        "producer": "scripts.streaming_producer",
        "consumer": "scripts.streaming_consumer",
    }

    if mode not in modules:
        raise ValueError(f"Mode T3 tidak valid: {mode}")

    command = [
        sys.executable,
        "-m",
        modules[mode],
        *extra_args,
    ]

    print("Menjalankan:", " ".join(command))

    result = subprocess.run(
        command,
        cwd=root,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"T3 {mode} gagal dengan exit code {result.returncode}"
        )

    print(f"PASS: T3 {mode} selesai.")

    

def run_t4():
    print("T4 - Data Warehouse")

    root = Path(__file__).resolve().parent
    sql_file = root / "sql" / "t4_star_schema.sql"

    if not sql_file.exists():
        raise FileNotFoundError(
            f"SQL T4 tidak ditemukan: {sql_file}"
        )

    sql = sql_file.read_text(encoding="utf-8")

    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "postgres",
            "psql", "-X",
            "-v", "ON_ERROR_STOP=1",
            "-U", "olist",
            "-d", "olist",
        ],
        input=sql,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Eksekusi SQL T4 gagal.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    print(result.stdout)
    print("Status: T4 berhasil dijalankan.")

    
def run_t5():
    print("T5 - Data Mart dan Ekspor Gold")

    root = Path(__file__).resolve().parent

    # 1. Jalankan SQL untuk membangun ulang keenam data mart.
    sql_file = root / "sql" / "t5_data_marts.sql"

    if not sql_file.exists():
        raise FileNotFoundError(
            f"File SQL T5 tidak ditemukan: {sql_file}"
        )

    sql = sql_file.read_text(encoding="utf-8")

    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "postgres",
            "psql", "-X",
            "-v", "ON_ERROR_STOP=1",
            "-U", "olist",
            "-d", "olist",
        ],
        input=sql,
        capture_output=True,
        text=True,
        cwd=root,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Eksekusi SQL T5 gagal.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    print(result.stdout)
    print("PASS: enam data mart berhasil dibangun.")

    # 2. Ekspor mart ke Parquet dan MinIO Gold.
    exporter = root / "scripts" / "export_marts_to_gold.py"

    if not exporter.exists():
        raise FileNotFoundError(
            f"Script ekspor Gold tidak ditemukan: {exporter}"
        )

    result = subprocess.run(
        [sys.executable, str(exporter)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Ekspor T5 ke Gold gagal.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    print(result.stdout)
    print("PASS: T5 selesai; seluruh mart berhasil diekspor.")



def run_t6():
    """T6: Jalankan tes otomatis proyek."""
    print("\n=== T6: TESTING DAN VALIDASI ===")

    root = Path(__file__).resolve().parent

    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-q",
    ]

    print("Menjalankan:", " ".join(command))

    result = subprocess.run(
        command,
        cwd=root,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"T6 gagal dengan exit code {result.returncode}"
        )

    print("PASS: seluruh tes yang dijalankan berhasil.")

    


def main():
    parser = argparse.ArgumentParser(
        description="Olist Data Platform Pipeline"
    )
    parser.add_argument(
        "stage",
        choices=["T0", "T1", "T2", "T3", "T4", "T5", "T6"],
        help="Tahap pipeline yang akan dijalankan",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["producer", "consumer"],
        help="Mode producer atau consumer; wajib dipilih jika stage T3",
    )

    
    
    if len(sys.argv) >= 3 and sys.argv[1] == "T3":
        stage = sys.argv[1]
        mode = sys.argv[2]
        extra_args = sys.argv[3:]

        if mode not in ["producer", "consumer"]:
            parser.error("Mode T3 harus producer atau consumer.")

        run_t3(mode, extra_args)
        return

    args = parser.parse_args()
    extra_args = []


    if args.stage == "T3":
        if args.mode is None:
            parser.error(
                "T3 memerlukan mode producer atau consumer."
            )

        run_t3(args.mode, extra_args)
        return

    if args.stage == "T6":
        if args.mode is not None or extra_args:
            parser.error("T6 tidak menerima mode atau argumen tambahan.")

        run_t6()
        return

    if args.mode is not None or extra_args:
        parser.error(
            "Mode hanya didukung untuk T3."
        )

    stages = {
        "T0": run_t0,
        "T1": run_t1,
        "T2": run_t2,
        "T4": run_t4,
        "T5": run_t5,
    }

    
    stages[args.stage]()


if __name__ == "__main__":
    main()

