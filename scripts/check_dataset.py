
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

# Jumlah record yang diharapkan, tidak termasuk header.
EXPECTED = {
    "olist_customers_dataset.csv": (
        99441,
        [
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ],
    ),
    "olist_geolocation_dataset.csv": (
        1000163,
        [
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "geolocation_city",
            "geolocation_state",
        ],
    ),
    "olist_orders_dataset.csv": (
        99441,
        [
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    ),
    "olist_order_items_dataset.csv": (
        112650,
        [
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ],
    ),
    "olist_order_payments_dataset.csv": (
        103886,
        [
            "order_id",
            "payment_sequential",
            "payment_type",
            "payment_installments",
            "payment_value",
        ],
    ),
    "olist_order_reviews_dataset.csv": (
        99224,
        [
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ],
    ),
    "olist_products_dataset.csv": (
        32951,
        [
            "product_id",
            "product_category_name",
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ],
    ),
    "olist_sellers_dataset.csv": (
        3095,
        [
            "seller_id",
            "seller_zip_code_prefix",
            "seller_city",
            "seller_state",
        ],
    ),
    "product_category_name_translation.csv": (
        71,
        [
            "product_category_name",
            "product_category_name_english",
        ],
    ),
}


def inspect_csv(filename, expected_rows, expected_columns):
    path = RAW_DIR / filename

    if not path.is_file():
        return False, f"MISSING FILE: {filename}"

    if path.stat().st_size == 0:
        return False, f"EMPTY FILE: {filename}"

    try:
        # utf-8-sig membaca UTF-8 biasa maupun BOM,
        # tanpa mengubah file sumber.
        with path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as file:
            reader = csv.reader(file)

            header = next(reader, None)

            if header is None:
                return False, f"EMPTY CSV: {filename}"

            actual_rows = sum(1 for _ in reader)

        if header != expected_columns:
            return False, (
                f"KOLOM TIDAK SESUAI: {filename}\n"
                f"  Expected: {expected_columns}\n"
                f"  Actual:   {header}"
            )

        if actual_rows != expected_rows:
            return False, (
                f"JUMLAH BARIS TIDAK SESUAI: {filename}\n"
                f"  Expected: {expected_rows:,}\n"
                f"  Actual:   {actual_rows:,}"
            )

        size_mb = path.stat().st_size / (1024 * 1024)

        return True, (
            f"PASS | {filename} | "
            f"{actual_rows:,} rows | {size_mb:.2f} MB"
        )

    except (OSError, UnicodeError, csv.Error) as exc:
        return False, f"ERROR: {filename}: {exc}"


def main():
    print("=" * 75)
    print("OLIST DATASET CHECK")
    print(f"Source: {RAW_DIR}")
    print("=" * 75)

    passed = 0
    failed = 0

    # Periksa semua file yang diwajibkan.
    for filename, (rows, columns) in EXPECTED.items():
        ok, message = inspect_csv(filename, rows, columns)
        print(message)

        if ok:
            passed += 1
        else:
            failed += 1

    # Deteksi file CSV tambahan yang tidak ada di kontrak awal.
    actual_files = {
        path.name for path in RAW_DIR.glob("*.csv")
    }
    expected_files = set(EXPECTED)

    extra_files = actual_files - expected_files

    if extra_files:
        print("\nCSV tambahan:")
        for filename in sorted(extra_files):
            print(f"  REVIEW: {filename}")

    print("\n" + "=" * 75)
    print(f"PASS: {passed}/{len(EXPECTED)}")
    print(f"FAIL: {failed}/{len(EXPECTED)}")
    print("=" * 75)

    if failed:
        print("VERDICT: FAIL — periksa pesan di atas.")
        return 1

    print("VERDICT: PASS — semua file, kolom, dan baris sesuai.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
