
import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


def read_csv(filename):
    with (RAW / filename).open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        return list(csv.DictReader(f))


def report_duplicates(filename, columns):
    data = read_csv(filename)
    groups = defaultdict(list)

    for row in data:
        key = tuple(row[c] for c in columns)
        groups[key].append(row)

    duplicates = {
        key: group
        for key, group in groups.items()
        if len(group) > 1
    }

    print(f"\n{filename}: duplicate key = {columns}")
    print(f"Duplicate groups: {len(duplicates):,}")
    print(
        "Rows in duplicate groups: "
        f"{sum(len(g) for g in duplicates.values()):,}"
    )

    for key, group in list(duplicates.items())[:5]:
        print(f"\n  Key: {key}")
        for row in group[:3]:
            print(f"    {row}")


def main():
    print("=" * 75)
    print("OLIST QUALITY INVESTIGATION")
    print("=" * 75)

    # 1. Kunci gabungan.
    report_duplicates(
        "olist_order_items_dataset.csv",
        ["order_id", "order_item_id"],
    )
    report_duplicates(
        "olist_order_payments_dataset.csv",
        ["order_id", "payment_sequential"],
    )

    # 2. Investigasi review_id berulang.
    reviews = read_csv("olist_order_reviews_dataset.csv")
    review_groups = defaultdict(list)

    for row in reviews:
        review_groups[row["review_id"]].append(row)

    duplicated_reviews = {
        key: group
        for key, group in review_groups.items()
        if len(group) > 1
    }

    identical_groups = 0
    different_groups = 0
    same_order_groups = 0
    different_order_groups = 0

    print("\nREVIEW ID INVESTIGATION")

    for review_id, group in duplicated_reviews.items():
        signatures = {
            tuple(sorted(row.items()))
            for row in group
        }

        if len(signatures) == 1:
            identical_groups += 1
        else:
            different_groups += 1

        order_ids = {row["order_id"] for row in group}

        if len(order_ids) == 1:
            same_order_groups += 1
        else:
            different_order_groups += 1

    print(f"Duplicate review_id groups: {len(duplicated_reviews):,}")
    print(f"Groups with identical rows: {identical_groups:,}")
    print(f"Groups with differing rows: {different_groups:,}")
    print(f"Groups associated with same order: {same_order_groups:,}")
    print(f"Groups associated with multiple orders: {different_order_groups:,}")

    print("\nExamples of duplicate review_id:")
    shown = 0
    for review_id, group in duplicated_reviews.items():
        print(f"\n  review_id={review_id}")
        for row in group[:3]:
            print(f"    order_id={row['order_id']}, "
                  f"score={row['review_score']}, "
                  f"title={row['review_comment_title']!r}, "
                  f"message={row['review_comment_message']!r}")
        shown += 1
        if shown == 5:
            break

    # 3. Pola nilai kosong pada atribut produk.
    products = read_csv("olist_products_dataset.csv")
    product_columns = [
        "product_category_name",
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]

    missing_patterns = Counter()
    for row in products:
        missing = tuple(
            c for c in product_columns if not row[c].strip()
        )
        if missing:
            missing_patterns[missing] += 1

    print("\nPRODUCT NULL PATTERNS")
    for pattern, count in missing_patterns.most_common():
        print(f"  {count:,} rows: {pattern}")

    # 4. Status order dibandingkan dengan tanggal kosong.
    orders = read_csv("olist_orders_dataset.csv")
    date_columns = [
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
    ]

    status_counts = Counter()
    status_missing = Counter()

    for row in orders:
        status = row["order_status"]
        status_counts[status] += 1

        for column in date_columns:
            if not row[column].strip():
                status_missing[(status, column)] += 1

    print("\nORDER STATUS COUNTS")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count:,}")

    print("\nMISSING DATES BY ORDER STATUS")
    for (status, column), count in sorted(status_missing.items()):
        print(f"  {status} | {column}: {count:,}")

    # 5. Urutan tanggal yang tidak masuk akal.
    parse_format = "%Y-%m-%d %H:%M:%S"
    chronology_checks = [
        ("order_purchase_timestamp", "order_approved_at"),
        ("order_approved_at", "order_delivered_carrier_date"),
        ("order_delivered_carrier_date", "order_delivered_customer_date"),
    ]

    print("\nCHRONOLOGY CHECKS")

    for earlier, later in chronology_checks:
        checked = 0
        violations = []

        for row in orders:
            a = row[earlier].strip()
            b = row[later].strip()

            if not a or not b:
                continue

            try:
                dt_a = datetime.strptime(a, parse_format)
                dt_b = datetime.strptime(b, parse_format)
            except ValueError:
                continue

            checked += 1
            if dt_b < dt_a:
                violations.append((row["order_id"], a, b))

        print(
            f"  {earlier} <= {later}: "
            f"checked={checked:,}, violations={len(violations):,}"
        )

        for order_id, a, b in violations[:3]:
            print(f"    order_id={order_id}: {a} -> {b}")

    print("\n" + "=" * 75)
    print("INVESTIGATION SELESAI")
    print("Belum ada data sumber yang diubah.")


if __name__ == "__main__":
    main()
