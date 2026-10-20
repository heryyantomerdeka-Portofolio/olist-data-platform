
"""
Olist Data Platform — Central Data Contract
Dipakai bersama oleh profiling, Silver, DQ, DDL PostgreSQL, dan unit test.
"""

from dataclasses import dataclass
from typing import Literal


# ============================================================
# 1. SCHEMA CONTRACT
# Tipe data:
# string    : teks/ID/kode pos
# integer   : bilangan bulat
# decimal   : nilai numerik desimal
# timestamp : tanggal dan waktu
# ============================================================

SCHEMAS = {
    "customers": {
        "source_file": "olist_customers_dataset.csv",
        "columns": {
            "customer_id": "string",
            "customer_unique_id": "string",
            "customer_zip_code_prefix": "string",
            "customer_city": "string",
            "customer_state": "string",
        },
        "primary_key": ["customer_id"],
    },
    "geolocation": {
        "source_file": "olist_geolocation_dataset.csv",
        "columns": {
            "geolocation_zip_code_prefix": "string",
            "geolocation_lat": "decimal",
            "geolocation_lng": "decimal",
            "geolocation_city": "string",
            "geolocation_state": "string",
        },
        # Tidak memakai primary key: satu kode pos dapat memiliki
        # banyak koordinat dan baris duplikat perlu diprofilkan.
        "primary_key": [],
    },
    "orders": {
        "source_file": "olist_orders_dataset.csv",
        "columns": {
            "order_id": "string",
            "customer_id": "string",
            "order_status": "string",
            "order_purchase_timestamp": "timestamp",
            "order_approved_at": "timestamp",
            "order_delivered_carrier_date": "timestamp",
            "order_delivered_customer_date": "timestamp",
            "order_estimated_delivery_date": "timestamp",
        },
        "primary_key": ["order_id"],
    },
    "order_items": {
        "source_file": "olist_order_items_dataset.csv",
        "columns": {
            "order_id": "string",
            "order_item_id": "integer",
            "product_id": "string",
            "seller_id": "string",
            "shipping_limit_date": "timestamp",
            "price": "decimal",
            "freight_value": "decimal",
        },
        "primary_key": ["order_id", "order_item_id"],
    },
    "order_payments": {
        "source_file": "olist_order_payments_dataset.csv",
        "columns": {
            "order_id": "string",
            "payment_sequential": "integer",
            "payment_type": "string",
            "payment_installments": "integer",
            "payment_value": "decimal",
        },
        "primary_key": ["order_id", "payment_sequential"],
    },
    "order_reviews": {
        "source_file": "olist_order_reviews_dataset.csv",
        "columns": {
            "review_id": "string",
            "order_id": "string",
            "review_score": "integer",
            "review_comment_title": "string",
            "review_comment_message": "string",
            "review_creation_date": "timestamp",
            "review_answer_timestamp": "timestamp",
        },
        # review_id dapat muncul lebih dari sekali di data sumber;
        # validasi keunikannya dilakukan sebagai aturan DQ.
        "primary_key": [],
    },
    "products": {
        "source_file": "olist_products_dataset.csv",
        "columns": {
            "product_id": "string",
            "product_category_name": "string",
            "product_name_lenght": "integer",
            "product_description_lenght": "integer",
            "product_photos_qty": "integer",
            "product_weight_g": "decimal",
            "product_length_cm": "decimal",
            "product_height_cm": "decimal",
            "product_width_cm": "decimal",
        },
        "primary_key": ["product_id"],
    },
    "sellers": {
        "source_file": "olist_sellers_dataset.csv",
        "columns": {
            "seller_id": "string",
            "seller_zip_code_prefix": "string",
            "seller_city": "string",
            "seller_state": "string",
        },
        "primary_key": ["seller_id"],
    },
    "category_translation": {
        "source_file": "product_category_name_translation.csv",
        "columns": {
            "product_category_name": "string",
            "product_category_name_english": "string",
        },
        "primary_key": ["product_category_name"],
    },
}


# ============================================================
# 2. RULE CONTRACT
# type:
#   hard = pelanggaran mengarantina baris
#   soft = pelanggaran dicatat, baris tetap lolos
#
# check adalah identifier untuk fungsi pemeriksaan yang nanti
# diimplementasikan di validator.
# ============================================================

@dataclass(frozen=True)
class DQRule:
    name: str
    table: str
    type: Literal["hard", "soft"]
    action: Literal["quarantine", "warn"]
    check: str
    description: str


RULES = [
    # ---------------- HARD RULES ----------------
    DQRule(
        "H001_CUSTOMER_ID_REQUIRED", "customers", "hard",
        "quarantine", "not_null",
        "customer_id wajib terisi.",
    ),
    DQRule(
        "H002_CUSTOMER_ID_UNIQUE", "customers", "hard",
        "quarantine", "unique",
        "customer_id harus unik.",
    ),
    DQRule(
        "H003_CUSTOMER_ZIP_FORMAT", "customers", "hard",
        "quarantine", "zip_5_digits",
        "Kode pos pelanggan harus berupa 5 digit teks.",
    ),
    DQRule(
        "H004_GEO_ZIP_FORMAT", "geolocation", "hard",
        "quarantine", "zip_5_digits",
        "Kode pos geolokasi harus berupa 5 digit teks.",
    ),
    DQRule(
        "H005_GEO_LAT_RANGE", "geolocation", "hard",
        "quarantine", "latitude_range",
        "Latitude harus berada di antara -90 dan 90.",
    ),
    DQRule(
        "H006_GEO_LNG_RANGE", "geolocation", "hard",
        "quarantine", "longitude_range",
        "Longitude harus berada di antara -180 dan 180.",
    ),
    DQRule(
        "H007_ORDER_ID_REQUIRED", "orders", "hard",
        "quarantine", "not_null",
        "order_id wajib terisi.",
    ),
    DQRule(
        "H008_ORDER_ID_UNIQUE", "orders", "hard",
        "quarantine", "unique",
        "order_id harus unik.",
    ),
    DQRule(
        "H009_ORDER_CUSTOMER_FK", "orders", "hard",
        "quarantine", "foreign_key",
        "customer_id harus ditemukan pada customers.",
    ),
    DQRule(
        "H010_ITEM_ORDER_FK", "order_items", "hard",
        "quarantine", "foreign_key",
        "order_id harus ditemukan pada orders.",
    ),
    DQRule(
        "H011_ITEM_PRODUCT_FK", "order_items", "hard",
        "quarantine", "foreign_key",
        "product_id harus ditemukan pada products.",
    ),
    DQRule(
        "H012_ITEM_SELLER_FK", "order_items", "hard",
        "quarantine", "foreign_key",
        "seller_id harus ditemukan pada sellers.",
    ),
    DQRule(
        "H013_ITEM_PRICE_NONNEGATIVE", "order_items", "hard",
        "quarantine", "nonnegative",
        "price tidak boleh negatif.",
    ),
    DQRule(
        "H014_ITEM_FREIGHT_NONNEGATIVE", "order_items", "hard",
        "quarantine", "nonnegative",
        "freight_value tidak boleh negatif.",
    ),
    DQRule(
        "H015_PAYMENT_ORDER_FK", "order_payments", "hard",
        "quarantine", "foreign_key",
        "order_id pembayaran harus ditemukan pada orders.",
    ),
    DQRule(
        "H016_PAYMENT_VALUE_NONNEGATIVE", "order_payments", "hard",
        "quarantine", "nonnegative",
        "payment_value tidak boleh negatif.",
    ),
    DQRule(
        "H017_REVIEW_ORDER_FK", "order_reviews", "hard",
        "quarantine", "foreign_key",
        "order_id review harus ditemukan pada orders.",
    ),
    DQRule(
        "H018_REVIEW_SCORE_RANGE", "order_reviews", "hard",
        "quarantine", "range_1_to_5",
        "review_score harus berada di antara 1 dan 5.",
    ),
    DQRule(
        "H019_PRODUCT_ID_REQUIRED", "products", "hard",
        "quarantine", "not_null",
        "product_id wajib terisi.",
    ),
    DQRule(
        "H020_PRODUCT_ID_UNIQUE", "products", "hard",
        "quarantine", "unique",
        "product_id harus unik.",
    ),
    DQRule(
        "H021_SELLER_ID_REQUIRED", "sellers", "hard",
        "quarantine", "not_null",
        "seller_id wajib terisi.",
    ),
    DQRule(
        "H022_SELLER_ID_UNIQUE", "sellers", "hard",
        "quarantine", "unique",
        "seller_id harus unik.",
    ),
    DQRule(
        "H023_SELLER_ZIP_FORMAT", "sellers", "hard",
        "quarantine", "zip_5_digits",
        "Kode pos penjual harus berupa 5 digit teks.",
    ),
    DQRule(
        "H024_TRANSLATION_CATEGORY_REQUIRED", "category_translation", "hard",
        "quarantine", "not_null",
        "Nama kategori sumber pada tabel terjemahan wajib terisi.",
    ),

    # ---------------- SOFT RULES ----------------
    DQRule(
        "S001_CUSTOMER_STATE_PRESENT", "customers", "soft",
        "warn", "not_null",
        "Catat pelanggan yang tidak memiliki kode state.",
    ),
    DQRule(
        "S002_GEO_COORDINATE_DUPLICATE", "geolocation", "soft",
        "warn", "duplicate",
        "Hitung koordinat atau baris geolokasi duplikat.",
    ),
    DQRule(
        "S003_ORDER_APPROVAL_MISSING", "orders", "soft",
        "warn", "not_null",
        "Catat order yang belum memiliki waktu persetujuan.",
    ),
    DQRule(
        "S004_ORDER_DELIVERY_CHRONOLOGY", "orders", "soft",
        "warn", "timestamp_order",
        "Periksa urutan waktu purchase, carrier, dan delivery.",
    ),
    DQRule(
        "S005_ITEM_SHIPPING_LIMIT", "order_items", "soft",
        "warn", "timestamp_order",
        "Periksa shipping limit yang lebih awal dari purchase.",
    ),
    DQRule(
        "S006_PAYMENT_INSTALLMENTS", "order_payments", "soft",
        "warn", "positive",
        "Catat nilai cicilan yang tidak positif.",
    ),
    DQRule(
        "S007_REVIEW_COMMENT_EMPTY", "order_reviews", "soft",
        "warn", "not_null",
        "Hitung review tanpa komentar; tidak mengarantina baris.",
    ),
    DQRule(
        "S008_PRODUCT_DIMENSIONS", "products", "soft",
        "warn", "positive_dimensions",
        "Catat dimensi atau berat produk yang tidak positif.",
    ),
]


# ============================================================
# 3. DQ GATE CONFIGURATION
# Ambang ini merupakan nilai awal dan harus dievaluasi dari
# hasil profiling. Jangan menganggapnya sebagai hasil pengukuran.
# ============================================================

DQ_GATE = {
    # Jika proporsi baris yang dikarantina melewati ambang ini,
    # tabel berstatus FAIL dan tidak dimuat ke PostgreSQL.
    "max_quarantine_pct_default": 2.0,

    # Ambang awal khusus geolokasi karena sumber berisi banyak
    # titik untuk kode pos yang sama. Evaluasi setelah profiling.
    "max_quarantine_pct_by_table": {
        "geolocation": 5.0,
    },

    # Skema/tabel yang header-nya tidak cocok harus dihentikan
    # sebelum ada perubahan pada PostgreSQL.
    "fail_on_missing_columns": True,
    "fail_on_unexpected_columns": True,
}


# ============================================================
# 4. HELPER FUNCTIONS
# ============================================================

def get_table_contract(table_name: str) -> dict:
    """Mengambil kontrak sebuah tabel."""
    if table_name not in SCHEMAS:
        raise KeyError(f"Tabel tidak terdaftar dalam kontrak: {table_name}")
    return SCHEMAS[table_name]


def get_rules(
    table_name: str | None = None,
    rule_type: str | None = None,
) -> list[DQRule]:
    """Mengambil semua aturan, atau memfilter berdasarkan tabel/jenis."""
    result = RULES

    if table_name is not None:
        result = [r for r in result if r.table == table_name]

    if rule_type is not None:
        if rule_type not in {"hard", "soft"}:
            raise ValueError("rule_type harus 'hard' atau 'soft'.")
        result = [r for r in result if r.type == rule_type]

    return result


def validate_contract_definition() -> None:
    """Memastikan definisi kontrak internal konsisten."""
    if len(SCHEMAS) != 9:
        raise ValueError(f"Harus ada 9 tabel, ditemukan {len(SCHEMAS)}.")

    known_tables = set(SCHEMAS)

    for table_name, contract in SCHEMAS.items():
        if not contract["columns"]:
            raise ValueError(f"Kolom kontrak kosong: {table_name}")

        for column_name, data_type in contract["columns"].items():
            if data_type not in {
                "string", "integer", "decimal", "timestamp"
            }:
                raise ValueError(
                    f"Tipe data tidak dikenal: {table_name}.{column_name} "
                    f"({data_type})"
                )

    for rule in RULES:
        if rule.table not in known_tables:
            raise ValueError(
                f"Rule {rule.name} menunjuk tabel yang tidak dikenal: "
                f"{rule.table}"
            )

        if rule.type == "hard" and rule.action != "quarantine":
            raise ValueError(f"Hard rule {rule.name} harus quarantine.")

        if rule.type == "soft" and rule.action != "warn":
            raise ValueError(f"Soft rule {rule.name} harus warn.")


def print_contract_summary() -> None:
    """Menampilkan ringkasan kontrak untuk pemeriksaan awal."""
    validate_contract_definition()

    hard_count = len(get_rules(rule_type="hard"))
    soft_count = len(get_rules(rule_type="soft"))

    print(f"Jumlah tabel : {len(SCHEMAS)}")
    print(f"Hard rules  : {hard_count}")
    print(f"Soft rules  : {soft_count}")

    for table_name, contract in SCHEMAS.items():
        print(
            f"- {table_name}: "
            f"{len(contract['columns'])} kolom; "
            f"source={contract['source_file']}"
        )


if __name__ == "__main__":
    print_contract_summary()
