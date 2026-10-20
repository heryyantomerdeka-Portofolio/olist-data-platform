
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

checks = []


# =========================================================
# 1. LOAD DATA
# =========================================================

def load_table(name):
    path = DATA / f"{name}.csv"

    if not path.exists():
        print(f"SKIP: file tidak ditemukan: {path.name}")
        return None

    return pd.read_csv(
        path,
        dtype="string",
        low_memory=False
    )


# =========================================================
# 2. HELPER UNTUK MENYIMPAN HASIL VALIDASI
# =========================================================

def add_check(check, status, failed_rows=None, details=""):
    checks.append({
        "check": check,
        "status": status,
        "failed_rows": failed_rows,
        "details": details
    })


# =========================================================
# 3. VALIDASI UNIQUE KEY
# =========================================================

def check_unique(df, table, columns):
    if df is None:
        return

    missing_columns = [
        col for col in columns if col not in df.columns
    ]

    if missing_columns:
        add_check(
            f"{table}: unique {columns}",
            "MISSING_COLUMN",
            None,
            f"Kolom tidak ditemukan: {missing_columns}"
        )
        return

    subset = df[columns]

    null_mask = subset.isna().any(axis=1)
    duplicate_mask = subset.duplicated(keep=False)

    # Hitung baris bermasalah tanpa menghitung ganda
    # jika suatu baris sekaligus null dan duplicate.
    failed_mask = null_mask | duplicate_mask

    null_rows = int(null_mask.sum())
    duplicate_rows = int(duplicate_mask.sum())
    failed_count = int(failed_mask.sum())

    add_check(
        f"{table}: unique {columns}",
        "PASS" if failed_count == 0 else "FAIL",
        failed_count,
        (
            f"null rows={null_rows}; "
            f"rows participating in duplicates={duplicate_rows}"
        )
    )


# =========================================================
# 4. VALIDASI FOREIGN KEY
# =========================================================

def check_fk(
    child, child_table, child_col,
    parent, parent_table, parent_col
):
    check_name = (
        f"{child_table}.{child_col} -> "
        f"{parent_table}.{parent_col}"
    )

    if child is None or parent is None:
        add_check(
            check_name,
            "SKIPPED",
            None,
            "Tabel anak atau induk tidak tersedia"
        )
        return

    missing_columns = []

    if child_col not in child.columns:
        missing_columns.append(f"{child_table}.{child_col}")

    if parent_col not in parent.columns:
        missing_columns.append(f"{parent_table}.{parent_col}")

    if missing_columns:
        add_check(
            check_name,
            "MISSING_COLUMN",
            None,
            f"Kolom tidak ditemukan: {missing_columns}"
        )
        return

    child_values = child[child_col]
    parent_values = set(parent[parent_col].dropna())

    null_mask = child_values.isna()
    non_null_values = child_values[~null_mask]

    orphan_mask = ~non_null_values.isin(parent_values)

    null_rows = int(null_mask.sum())
    orphan_rows = int(orphan_mask.sum())

    add_check(
        check_name,
        "PASS" if orphan_rows == 0 else "FAIL",
        orphan_rows,
        (
            f"orphan rows={orphan_rows}; "
            f"null rows={null_rows}. "
            "Null values dilaporkan terpisah dari orphan."
        )
    )


# =========================================================
# 5. VALIDASI CAKUPAN TERJEMAHAN KATEGORI
# =========================================================

def check_category_translation(products, translations):
    check_name = "products.category_translation_coverage"

    if products is None or translations is None:
        add_check(
            check_name,
            "SKIPPED",
            None,
            "Tabel products atau category translation tidak tersedia"
        )
        return

    product_col = "product_category_name"
    translation_col = "product_category_name"

    if (
        product_col not in products.columns
        or translation_col not in translations.columns
    ):
        add_check(
            check_name,
            "MISSING_COLUMN",
            None,
            "Kolom product_category_name tidak ditemukan"
        )
        return

    product_categories = products[product_col]
    translated_categories = set(
        translations[translation_col].dropna()
    )

    missing_mask = product_categories.isna()

    non_null_categories = product_categories[~missing_mask]
    unmapped_mask = ~non_null_categories.isin(
        translated_categories
    )

    missing_rows = int(missing_mask.sum())
    unmapped_rows = int(unmapped_mask.sum())

    unmapped_values = sorted(
        non_null_categories[unmapped_mask].unique().tolist()
    )

    # Kategori yang tidak diterjemahkan adalah WARNING,
    # bukan otomatis kegagalan integritas data.
    status = "WARNING" if unmapped_rows > 0 else "PASS"

    add_check(
        check_name,
        status,
        unmapped_rows,
        (
            f"unmapped non-null rows={unmapped_rows}; "
            f"missing category rows={missing_rows}; "
            f"unmapped categories={unmapped_values}. "
            "Pertahankan kategori asli; hasil terjemahan "
            "boleh NULL."
        )
    )


# =========================================================
# 6. LOAD SELURUH TABEL
# =========================================================

orders = load_table("olist_orders_dataset")
customers = load_table("olist_customers_dataset")
items = load_table("olist_order_items_dataset")
payments = load_table("olist_order_payments_dataset")
products = load_table("olist_products_dataset")
sellers = load_table("olist_sellers_dataset")
reviews = load_table("olist_order_reviews_dataset")

translations = load_table(
    "product_category_name_translation"
)


# =========================================================
# 7. CEK UNIQUE KEY
# =========================================================

check_unique(orders, "orders", ["order_id"])

check_unique(
    customers,
    "customers",
    ["customer_id"]
)

check_unique(
    items,
    "order_items",
    ["order_id", "order_item_id"]
)

check_unique(
    payments,
    "order_payments",
    ["order_id", "payment_sequential"]
)

check_unique(
    products,
    "products",
    ["product_id"]
)

check_unique(
    sellers,
    "sellers",
    ["seller_id"]
)

check_unique(
    reviews,
    "order_reviews",
    ["review_id", "order_id"]
)

check_unique(
    translations,
    "category_translation",
    ["product_category_name"]
)


# =========================================================
# 8. CEK FOREIGN KEY
# =========================================================

check_fk(
    orders, "orders", "customer_id",
    customers, "customers", "customer_id"
)

check_fk(
    items, "order_items", "order_id",
    orders, "orders", "order_id"
)

check_fk(
    items, "order_items", "product_id",
    products, "products", "product_id"
)

check_fk(
    items, "order_items", "seller_id",
    sellers, "sellers", "seller_id"
)

check_fk(
    payments, "order_payments", "order_id",
    orders, "orders", "order_id"
)

check_fk(
    reviews, "order_reviews", "order_id",
    orders, "orders", "order_id"
)


# =========================================================
# 9. CEK CAKUPAN TERJEMAHAN KATEGORI
# =========================================================

check_category_translation(products, translations)


# =========================================================
# 10. EXPORT LAPORAN
# =========================================================

report = pd.DataFrame(checks)

report_path = OUT / "key_validation.csv"
report.to_csv(report_path, index=False)

print("\n=== KEY VALIDATION REPORT ===")
print(report.to_string(index=False))

print("\n=== VALIDATION SUMMARY ===")
print(
    report["status"]
    .value_counts(dropna=False)
    .to_string()
)

print(f"\nReport saved to: {report_path}")
