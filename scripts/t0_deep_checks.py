
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

def load(name):
    return pd.read_csv(
        RAW / f"{name}.csv",
        dtype="string",
        encoding="utf-8-sig",
        keep_default_na=False,
        low_memory=False,
    )

orders = load("olist_orders_dataset")
items = load("olist_order_items_dataset")
payments = load("olist_order_payments_dataset")
reviews = load("olist_order_reviews_dataset")
geo = load("olist_geolocation_dataset")
products = load("olist_products_dataset")

print("\n=== 1. REVIEW KEY GRAIN ===")
for cols in [["review_id"], ["order_id"], ["review_id", "order_id"]]:
    duplicate_rows = int(reviews.duplicated(cols, keep=False).sum())
    extra_rows = int(reviews.duplicated(cols, keep="first").sum())
    print(
        f"{cols}: rows_in_duplicate_groups={duplicate_rows:,}; "
        f"extra_occurrences={extra_rows:,}"
    )

print("\n=== 2. ORDERS TANPA ITEM / PAYMENT ===")
order_ids = set(orders["order_id"])
item_orders = set(items["order_id"])
payment_orders = set(payments["order_id"])
print(f"Orders without items: {len(order_ids - item_orders):,}")
print(f"Orders without payments: {len(order_ids - payment_orders):,}")

print("\n=== 3. NUMERIC INVALIDS ===")
numeric_cols = {
    "items.price": (items["price"], True),
    "items.freight_value": (items["freight_value"], True),
    "payments.payment_value": (payments["payment_value"], True),
    "products.product_weight_g": (products["product_weight_g"], False),
    "products.product_length_cm": (products["product_length_cm"], False),
    "products.product_height_cm": (products["product_height_cm"], False),
    "products.product_width_cm": (products["product_width_cm"], False),
}
for name, (series, nonnegative) in numeric_cols.items():
    s = pd.to_numeric(series.replace("", pd.NA), errors="coerce")
    malformed = int((series.ne("") & s.isna()).sum())
    negative = int((s < 0).sum()) if nonnegative else 0
    zero = int((s == 0).sum())
    print(
        f"{name}: malformed={malformed:,}; "
        f"negative={negative:,}; zero={zero:,}"
    )

print("\n=== 4. ORDER TIMESTAMP ANOMALIES ===")
date_cols = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]
for col in date_cols:
    orders[col] = pd.to_datetime(orders[col], errors="coerce")

checks = [
    (
        "approved_before_purchase",
        orders["order_approved_at"] < orders["order_purchase_timestamp"],
    ),
    (
        "carrier_before_purchase",
        orders["order_delivered_carrier_date"] < orders["order_purchase_timestamp"],
    ),
    (
        "delivered_before_carrier",
        orders["order_delivered_customer_date"] < orders["order_delivered_carrier_date"],
    ),
    (
        "delivered_before_purchase",
        orders["order_delivered_customer_date"] < orders["order_purchase_timestamp"],
    ),
    (
        "delivered_after_estimate",
        orders["order_delivered_customer_date"] > orders["order_estimated_delivery_date"],
    ),
]
for label, mask in checks:
    print(f"{label}: {int(mask.fillna(False).sum()):,}")

print("\n=== 5. GEOLOCATION ===")
lat = pd.to_numeric(geo["geolocation_lat"], errors="coerce")
lng = pd.to_numeric(geo["geolocation_lng"], errors="coerce")
outside = ~(
    lat.between(-34, 5) & lng.between(-74, -35)
)
print(f"Exact duplicate rows: {int(geo.duplicated().sum()):,}")
print(f"Invalid latitude parse: {int(lat.isna().sum()):,}")
print(f"Invalid longitude parse: {int(lng.isna().sum()):,}")
print(f"Outside approximate Brazil bounds: {int(outside.sum()):,}")
print(f"Distinct zip prefixes: {geo['geolocation_zip_code_prefix'].nunique():,}")

print("\n=== 6. ITEM VS PAYMENT RECONCILIATION ===")
item_values = items.assign(
    price_num=pd.to_numeric(items["price"], errors="coerce"),
    freight_num=pd.to_numeric(items["freight_value"], errors="coerce"),
)
item_totals = item_values.groupby("order_id").apply(
    lambda x: (x["price_num"] + x["freight_num"]).sum(min_count=1),
    include_groups=False,
)
payment_values = payments.assign(
    payment_num=pd.to_numeric(payments["payment_value"], errors="coerce")
)
payment_totals = payment_values.groupby("order_id")["payment_num"].sum(min_count=1)

recon = pd.concat(
    [item_totals.rename("items_plus_freight"),
     payment_totals.rename("payments")],
    axis=1,
)
recon["difference"] = recon["payments"] - recon["items_plus_freight"]
comparable = recon.dropna(subset=["items_plus_freight", "payments"])
print(f"Comparable orders: {len(comparable):,}")
print(f"Absolute difference > 0.01: {(comparable['difference'].abs() > 0.01).sum():,}")
print(f"Absolute difference > 1.00: {(comparable['difference'].abs() > 1.00).sum():,}")
print(f"Orders missing item total: {recon['items_plus_freight'].isna().sum():,}")
print(f"Orders missing payment total: {recon['payments'].isna().sum():,}")
print("\nCatatan: selisih bukan otomatis fraud atau kesalahan; perlu klasifikasi penyebab.")
