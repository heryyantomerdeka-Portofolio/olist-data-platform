
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

FILES = [
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

# Kolom yang akan diperiksa untuk duplikasi.
KEYS = {
    "olist_customers_dataset.csv": ["customer_id"],
    "olist_orders_dataset.csv": ["order_id"],
    "olist_products_dataset.csv": ["product_id"],
    "olist_sellers_dataset.csv": ["seller_id"],
    "olist_order_items_dataset.csv": ["order_id", "order_item_id"],
    "olist_order_payments_dataset.csv": ["order_id", "payment_sequential"],
    "olist_order_reviews_dataset.csv": ["review_id"],
}

# Kolom tanggal untuk melihat rentang waktu.
DATE_COLUMNS = {
    "olist_orders_dataset.csv": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "olist_order_reviews_dataset.csv": [
        "review_creation_date",
        "review_answer_timestamp",
    ],
}

# Kolom foreign key yang dibandingkan dengan tabel induk.
RELATIONSHIPS = [
    (
        "olist_orders_dataset.csv",
        "customer_id",
        "olist_customers_dataset.csv",
        "customer_id",
    ),
    (
        "olist_order_items_dataset.csv",
        "order_id",
        "olist_orders_dataset.csv",
        "order_id",
    ),
    (
        "olist_order_items_dataset.csv",
        "product_id",
        "olist_products_dataset.csv",
        "product_id",
    ),
    (
        "olist_order_items_dataset.csv",
        "seller_id",
        "olist_sellers_dataset.csv",
        "seller_id",
    ),
    (
        "olist_order_payments_dataset.csv",
        "order_id",
        "olist_orders_dataset.csv",
        "order_id",
    ),
    (
        "olist_order_reviews_dataset.csv",
        "order_id",
        "olist_orders_dataset.csv",
        "order_id",
    ),
]


def rows(filename):
    path = RAW / filename
    with path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        yield from csv.DictReader(f)


def load_key_set(filename, column):
    return {
        row[column]
        for row in rows(filename)
        if row.get(column, "").strip()
    }


def main():
    output = []

    def log(message=""):
        print(message)
        output.append(message)

    log("OLIST DATA QUALITY PROFILING")
    log(f"Source: {RAW}")
    log("=" * 75)

    # 1. Completeness, jumlah baris, dan duplikasi.
    log("\n1. COMPLETENESS & DUPLICATES")

    for filename in FILES:
        nulls = Counter()
        duplicates = Counter()
        seen = {key: set() for key in KEYS.get(filename, [])}
        total = 0

        for row in rows(filename):
            total += 1

            for column, value in row.items():
                if value is None or value.strip() == "":
                    nulls[column] += 1

            for key in seen:
                value = row.get(key, "")
                if value:
                    if value in seen[key]:
                        duplicates[key] += 1
                    else:
                        seen[key].add(value)

        log(f"\n[{filename}]")
        log(f"Rows: {total:,}")

        log("Null values:")
        if nulls:
            for column, count in sorted(nulls.items()):
                log(f"  {column}: {count:,} ({count / total:.2%})")
        else:
            log("  Tidak ada nilai kosong.")

        if seen:
            log("Duplicate key values (kemunculan tambahan):")
            for key in seen:
                log(f"  {key}: {duplicates[key]:,}")
        else:
            log("Duplicate key check: tidak dikonfigurasi.")

    # 2. Rentang tanggal.
    log("\n\n2. DATE RANGES")

    for filename, columns in DATE_COLUMNS.items():
        values = {column: [] for column in columns}

        for row in rows(filename):
            for column in columns:
                value = row.get(column, "").strip()
                if value:
                    values[column].append(value)

        log(f"\n[{filename}]")
        for column, dates in values.items():
            if dates:
                log(
                    f"  {column}: "
                    f"min={min(dates)} | max={max(dates)}"
                )
            else:
                log(f"  {column}: tidak ada nilai terisi")

    # 3. Referential integrity.
    log("\n\n3. REFERENTIAL INTEGRITY")

    parent_cache = {}

    for child_file, child_col, parent_file, parent_col in RELATIONSHIPS:
        cache_key = (parent_file, parent_col)

        if cache_key not in parent_cache:
            parent_cache[cache_key] = load_key_set(
                parent_file, parent_col
            )

        parent_keys = parent_cache[cache_key]
        total = 0
        missing = 0

        for row in rows(child_file):
            value = row.get(child_col, "").strip()

            if not value:
                continue

            total += 1
            if value not in parent_keys:
                missing += 1

        log(
            f"{child_file}.{child_col} -> "
            f"{parent_file}.{parent_col}"
        )
        log(
            f"  Checked: {total:,} | "
            f"Unmatched: {missing:,}"
        )

    log("\n" + "=" * 75)
    log("PROFILING SELESAI")
    log("Catatan: hasil ini diagnosis awal, bukan keputusan untuk menghapus data.")

    report_path = REPORTS / "profiling_report.txt"
    report_path.write_text("\n".join(output), encoding="utf-8")
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
