from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "dw_report.md"

SQL = r"""
SELECT 'TABLE', 'dim_date', COUNT(*) FROM dw.dim_date
UNION ALL SELECT 'TABLE', 'dim_customer', COUNT(*) FROM dw.dim_customer
UNION ALL SELECT 'TABLE', 'dim_product', COUNT(*) FROM dw.dim_product
UNION ALL SELECT 'TABLE', 'dim_seller', COUNT(*) FROM dw.dim_seller
UNION ALL SELECT 'TABLE', 'dim_geo', COUNT(*) FROM dw.dim_geo
UNION ALL SELECT 'TABLE', 'fact_order', COUNT(*) FROM dw.fact_order
UNION ALL SELECT 'TABLE', 'fact_order_item', COUNT(*) FROM dw.fact_order_item
UNION ALL SELECT 'TABLE', 'fact_payment', COUNT(*) FROM dw.fact_payment
UNION ALL SELECT 'TABLE', 'fact_review', COUNT(*) FROM dw.fact_review
UNION ALL
SELECT 'CHECK', 'duplicate_fact_order_item_grain', COUNT(*)
FROM (
    SELECT order_id, order_item_id
    FROM dw.fact_order_item
    GROUP BY order_id, order_item_id
    HAVING COUNT(*) > 1
) x
UNION ALL
SELECT 'CHECK', 'duplicate_fact_review_grain', COUNT(*)
FROM (
    SELECT order_id FROM dw.fact_review
    GROUP BY order_id HAVING COUNT(*) > 1
) x
UNION ALL
SELECT 'CHECK', 'invalid_is_late_rows', COUNT(*)
FROM dw.fact_order
WHERE (
    order_status <> 'delivered'
    OR order_delivered_customer_date IS NULL
    OR order_estimated_delivery_date IS NULL
) AND is_late IS NOT NULL
UNION ALL
SELECT 'CHECK', 'invalid_geolocation_rows', COUNT(*)
FROM dw.dim_geo
WHERE is_unknown = FALSE
  AND (
      latitude IS NULL OR longitude IS NULL
      OR latitude NOT BETWEEN -34.0 AND 6.0
      OR longitude NOT BETWEEN -74.0 AND -34.0
  )
UNION ALL
SELECT 'CHECK', 'unvalidated_foreign_keys', COUNT(*)
FROM pg_constraint c
JOIN pg_namespace n ON n.oid = c.connamespace
WHERE n.nspname = 'dw'
  AND c.contype = 'f'
  AND NOT c.convalidated
UNION ALL
SELECT 'METRIC', 'orders_without_items',
       COUNT(*) FILTER (WHERE NOT has_items)
FROM dw.fact_order
UNION ALL
SELECT 'METRIC', 'orders_without_payments',
       COUNT(*) FILTER (WHERE NOT has_payments)
FROM dw.fact_order
UNION ALL
SELECT 'METRIC', 'source_review_rows', COUNT(*)
FROM raw.order_reviews
UNION ALL
SELECT 'METRIC', 'deduplicated_review_orders', COUNT(*)
FROM dw.fact_review
UNION ALL
SELECT 'METRIC', 'primary_key_count', COUNT(*)
FROM pg_constraint c
JOIN pg_namespace n ON n.oid = c.connamespace
WHERE n.nspname = 'dw' AND c.contype = 'p'
UNION ALL
SELECT 'METRIC', 'foreign_key_count', COUNT(*)
FROM pg_constraint c
JOIN pg_namespace n ON n.oid = c.connamespace
WHERE n.nspname = 'dw' AND c.contype = 'f'
ORDER BY 1, 2;
"""


def main():
    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "postgres",
            "psql", "-X", "-A", "-t", "-F", "\t",
            "-v", "ON_ERROR_STOP=1", "-U", "olist", "-d", "olist",
        ],
        input=SQL,
        text=True,
        cwd=ROOT,
        capture_output=True,
    )

    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    tables = {}
    checks = {}
    metrics = {}

    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 3:
            continue
        kind, name, value = fields
        if kind == "TABLE":
            tables[name] = int(value)
        elif kind == "CHECK":
            checks[name] = int(value)
        elif kind == "METRIC":
            metrics[name] = int(value)

    expected_tables = {
        "dim_date", "dim_customer", "dim_product", "dim_seller",
        "dim_geo", "fact_order", "fact_order_item",
        "fact_payment", "fact_review",
    }
    passed = (
        set(tables) == expected_tables
        and all(value == 0 for value in checks.values())
        and metrics.get("primary_key_count") == 9
        and metrics.get("foreign_key_count") == 18
    )

    lines = [
        "# T4 — Data Warehouse Report",
        "",
        f"**Status validasi: {'PASS' if passed else 'FAIL'}**",
        "",
        "## Jumlah baris",
        "",
        "| Tabel | Baris |",
        "|---|---:|",
    ]
    lines.extend(f"| `{name}` | {count:,} |" for name, count in sorted(tables.items()))

    lines += [
        "",
        "## Pemeriksaan integritas",
        "",
        "| Pemeriksaan | Jumlah masalah | Status |",
        "|---|---:|---|",
    ]
    lines.extend(
        f"| `{name}` | {count} | {'PASS' if count == 0 else 'FAIL'} |"
        for name, count in sorted(checks.items())
    )

    lines += [
        "",
        "## Metrik tambahan",
        "",
        "| Metrik | Nilai |",
        "|---|---:|",
    ]
    lines.extend(f"| `{name}` | {value:,} |" for name, value in sorted(metrics.items()))

    lines += [
        "",
        "## Catatan desain",
        "",
        "- `dim_customer` menggunakan satu baris per `customer_unique_id`.",
        "- SCD Type 1 mempertahankan atribut terbaru; riwayat atribut lama tidak disimpan.",
        "- `fact_review` memilih review terbaru per order berdasarkan creation timestamp, answer timestamp, lalu review ID sebagai tie-breaker.",
        "- `review_count` menyimpan jumlah review sumber untuk order yang memiliki review.",
        "- `is_late` bernilai NULL bila status belum delivered atau tanggal aktual/estimasi tidak tersedia; perbandingan memakai tanggal kalender.",
        "- Geografi yang tidak cocok dipetakan ke baris UNKNOWN; koordinat di luar batas geografis yang ditetapkan dikeluarkan.",
        "- `is_incomplete_month` menandai batas rentang tanggal sumber, bukan menjamin kelengkapan ekstraksi.",
        "",
    ]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Laporan dibuat: {OUTPUT}")
    print(f"Status validasi: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
