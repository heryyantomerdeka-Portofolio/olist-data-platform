
"""Evaluate Olist hard/soft DQ rules without modifying source data."""

from pathlib import Path

import pandas as pd

from src.t2_silver.contract import SCHEMAS, RULES, DQ_GATE

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "outputs"
QUARANTINE_DIR = OUT_DIR / "quarantine"


# ============================================================
# 1. LOAD SOURCE
# ============================================================

def load_sources():
    """Load local CSVs after validating all headers."""
    frames = {}
    pending = {}

    # Validate every header before reading any table.
    for table, contract in SCHEMAS.items():
        path = RAW_DIR / contract["source_file"]

        if not path.exists():
            raise FileNotFoundError(
                f"File sumber tidak ditemukan: {path}"
            )

        header = pd.read_csv(
            path,
            nrows=0,
            encoding="utf-8-sig",
        ).columns.tolist()

        expected = list(contract["columns"])
        missing = [c for c in expected if c not in header]
        unexpected = [c for c in header if c not in expected]

        if (
            missing and DQ_GATE["fail_on_missing_columns"]
        ) or (
            unexpected and DQ_GATE["fail_on_unexpected_columns"]
        ):
            raise ValueError(
                f"Header tidak cocok untuk {table}. "
                f"Kolom hilang={missing}; "
                f"kolom tidak dikenal={unexpected}"
            )

        pending[table] = path

    for table, path in pending.items():
        df = pd.read_csv(
            path,
            dtype=str,
            keep_default_na=False,
            encoding="utf-8-sig",
        )

        df["_source_row_number"] = range(2, len(df) + 2)
        frames[table] = df

    return frames


# ============================================================
# 2. COMMON HELPERS
# ============================================================

def blank(series):
    return series.isna() | series.astype(str).str.strip().eq("")


def numeric(series):
    return pd.to_numeric(series, errors="coerce")


def rule_mask(rule, df, frames):
    """Return Boolean mask: True means the row violates a rule."""
    name = rule.name

    # Required values
    required_columns = {
        "H001_CUSTOMER_ID_REQUIRED": "customer_id",
        "H007_ORDER_ID_REQUIRED": "order_id",
        "H019_PRODUCT_ID_REQUIRED": "product_id",
        "H021_SELLER_ID_REQUIRED": "seller_id",
        "H024_TRANSLATION_CATEGORY_REQUIRED": "product_category_name",
    }

    if name in required_columns:
        return blank(df[required_columns[name]])

    # Unique identifiers: keep the first occurrence.
    unique_columns = {
        "H002_CUSTOMER_ID_UNIQUE": ["customer_id"],
        "H008_ORDER_ID_UNIQUE": ["order_id"],
        "H020_PRODUCT_ID_UNIQUE": ["product_id"],
        "H022_SELLER_ID_UNIQUE": ["seller_id"],
    }

    if name in unique_columns:
        return df.duplicated(
            subset=unique_columns[name],
            keep="first",
        )

    # Postal codes must be five-digit strings.
    zip_columns = {
        "H003_CUSTOMER_ZIP_FORMAT": "customer_zip_code_prefix",
        "H004_GEO_ZIP_FORMAT": "geolocation_zip_code_prefix",
        "H023_SELLER_ZIP_FORMAT": "seller_zip_code_prefix",
    }

    if name in zip_columns:
        values = df[zip_columns[name]].astype(str).str.strip()
        return ~values.str.fullmatch(r"\d{5}", na=False)

    # Geographic coordinates
    if name == "H005_GEO_LAT_RANGE":
        values = numeric(df["geolocation_lat"])
        return values.isna() | ~values.between(-90, 90)

    if name == "H006_GEO_LNG_RANGE":
        values = numeric(df["geolocation_lng"])
        return values.isna() | ~values.between(-180, 180)

    # Foreign keys against source parent tables.
    fk_rules = {
        "H009_ORDER_CUSTOMER_FK": (
            "customer_id", "customers", "customer_id"
        ),
        "H010_ITEM_ORDER_FK": (
            "order_id", "orders", "order_id"
        ),
        "H011_ITEM_PRODUCT_FK": (
            "product_id", "products", "product_id"
        ),
        "H012_ITEM_SELLER_FK": (
            "seller_id", "sellers", "seller_id"
        ),
        "H015_PAYMENT_ORDER_FK": (
            "order_id", "orders", "order_id"
        ),
        "H017_REVIEW_ORDER_FK": (
            "order_id", "orders", "order_id"
        ),
    }

    if name in fk_rules:
        child_col, parent_table, parent_col = fk_rules[name]

        child_keys = df[child_col].astype(str).str.strip()
        parent_keys = (
            frames[parent_table][parent_col]
            .astype(str)
            .str.strip()
        )

        valid_parent_keys = set(parent_keys[~blank(parent_keys)])

        return blank(child_keys) | ~child_keys.isin(valid_parent_keys)

    # Monetary values must be valid and nonnegative.
    nonnegative_columns = {
        "H013_ITEM_PRICE_NONNEGATIVE": "price",
        "H014_ITEM_FREIGHT_NONNEGATIVE": "freight_value",
        "H016_PAYMENT_VALUE_NONNEGATIVE": "payment_value",
    }

    if name in nonnegative_columns:
        values = numeric(df[nonnegative_columns[name]])
        return values.isna() | values.lt(0)

    # Review scores: integer between 1 and 5.
    if name == "H018_REVIEW_SCORE_RANGE":
        values = numeric(df["review_score"])
        return (
            values.isna()
            | ~values.between(1, 5)
            | (values % 1 != 0)
        )

    # ---------------- SOFT RULES ----------------

    if name == "S001_CUSTOMER_STATE_PRESENT":
        return blank(df["customer_state"])

    if name == "S002_GEO_COORDINATE_DUPLICATE":
        columns = list(SCHEMAS["geolocation"]["columns"])
        return df.duplicated(subset=columns, keep="first")

    if name == "S003_ORDER_APPROVAL_MISSING":
        return blank(df["order_approved_at"])

    if name == "S004_ORDER_DELIVERY_CHRONOLOGY":
        purchase = pd.to_datetime(
            df["order_purchase_timestamp"], errors="coerce"
        )
        carrier = pd.to_datetime(
            df["order_delivered_carrier_date"], errors="coerce"
        )
        delivered = pd.to_datetime(
            df["order_delivered_customer_date"], errors="coerce"
        )

        return (
            (
                carrier.notna()
                & purchase.notna()
                & (carrier < purchase)
            )
            | (
                delivered.notna()
                & carrier.notna()
                & (delivered < carrier)
            )
        )

    if name == "S005_ITEM_SHIPPING_LIMIT":
        orders = frames["orders"][
            ["order_id", "order_purchase_timestamp"]
        ].drop_duplicates("order_id")

        merged = df[["order_id", "shipping_limit_date"]].merge(
            orders,
            on="order_id",
            how="left",
            sort=False,
        )

        shipping = pd.to_datetime(
            merged["shipping_limit_date"], errors="coerce"
        )
        purchase = pd.to_datetime(
            merged["order_purchase_timestamp"], errors="coerce"
        )

        # Restore the original row index.
        merged.index = df.index

        return (
            shipping.notna()
            & purchase.notna()
            & (shipping < purchase)
        )

    if name == "S006_PAYMENT_INSTALLMENTS":
        values = numeric(df["payment_installments"])
        return values.isna() | values.le(0)

    if name == "S007_REVIEW_COMMENT_EMPTY":
        return (
            blank(df["review_comment_title"])
            & blank(df["review_comment_message"])
        )

    if name == "S008_PRODUCT_DIMENSIONS":
        columns = [
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ]

        bad = pd.Series(False, index=df.index)

        for column in columns:
            values = numeric(df[column])
            bad |= values.notna() & values.le(0)

        return bad

    raise NotImplementedError(
        f"Rule belum memiliki implementasi: {name} ({rule.check})"
    )


# ============================================================
# 3. MAIN DQ EVALUATION
# ============================================================

def main(source_frames=None):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

    if source_frames is None:
        print("Memuat CSV lokal dan memvalidasi header...")
        frames = load_sources()
    else:
        print("Menggunakan data yang sudah dibaca dari Bronze...")
        frames = {}

        for table, df in source_frames.items():
            frames[table] = df.copy().reset_index(drop=True)

    # Ensure every contracted table exists.
    for table, contract in SCHEMAS.items():
        if table not in frames:
            raise ValueError(
                f"Data sumber tidak tersedia untuk tabel: {table}"
            )

        df = frames[table]
        expected = list(contract["columns"])

        missing = [c for c in expected if c not in df.columns]
        unexpected = [
            c for c in df.columns
            if c not in expected and c != "_source_row_number"
        ]

        if (
            missing and DQ_GATE["fail_on_missing_columns"]
        ) or (
            unexpected and DQ_GATE["fail_on_unexpected_columns"]
        ):
            raise ValueError(
                f"Kontrak tidak cocok untuk {table}. "
                f"Kolom hilang={missing}; "
                f"kolom tidak dikenal={unexpected}"
            )

        # Stable row numbers for quarantine investigation.
        if "_source_row_number" not in df.columns:
            df["_source_row_number"] = range(2, len(df) + 2)

        frames[table] = df.reset_index(drop=True)

    quarantine_masks = {
        table: pd.Series(False, index=df.index, dtype=bool)
        for table, df in frames.items()
    }

    quarantine_reasons = {
        table: [[] for _ in range(len(df))]
        for table, df in frames.items()
    }

    rule_counts = []

    # --------------------------------------------------------
    # Evaluate the 24 hard and 8 soft contract rules.
    # --------------------------------------------------------

    for rule in RULES:
        df = frames[rule.table]

        mask = (
            rule_mask(rule, df, frames)
            .reindex(df.index, fill_value=False)
            .fillna(False)
            .astype(bool)
        )

        count = int(mask.sum())

        rule_counts.append({
            "rule": rule.name,
            "table": rule.table,
            "type": rule.type,
            "action": rule.action,
            "violations": count,
            "description": rule.description,
        })

        if rule.type == "hard":
            quarantine_masks[rule.table] |= mask

            for idx in df.index[mask]:
                quarantine_reasons[rule.table][idx].append(rule.name)

        print(f"{rule.name}: {count:,} pelanggaran")

    # --------------------------------------------------------
    # Additional hard checks:
    # required fields, contract primary keys, and data types.
    # --------------------------------------------------------

    required_columns = {
        "customers": [
            "customer_id", "customer_unique_id",
        ],
        "geolocation": [
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
        ],
        "orders": [
            "order_id", "customer_id", "order_status",
            "order_purchase_timestamp",
        ],
        "order_items": [
            "order_id", "order_item_id", "product_id",
            "seller_id", "shipping_limit_date",
            "price", "freight_value",
        ],
        "order_payments": [
            "order_id", "payment_sequential", "payment_type",
            "payment_installments", "payment_value",
        ],
        "order_reviews": [
            "review_id", "order_id", "review_score",
        ],
        "products": ["product_id"],
        "sellers": ["seller_id"],
        "category_translation": [
            "product_category_name",
            "product_category_name_english",
        ],
    }

    def register_hard_violation(
        table, rule_name, mask, description
    ):
        df = frames[table]

        mask = (
            mask.reindex(df.index, fill_value=False)
            .fillna(False)
            .astype(bool)
        )

        rule_counts.append({
            "rule": rule_name,
            "table": table,
            "type": "hard",
            "action": "quarantine",
            "violations": int(mask.sum()),
            "description": description,
        })

        quarantine_masks[table] |= mask

        for idx in df.index[mask]:
            if rule_name not in quarantine_reasons[table][idx]:
                quarantine_reasons[table][idx].append(rule_name)

    # Required fields.
    for table, columns in required_columns.items():
        df = frames[table]

        for column in columns:
            register_hard_violation(
                table,
                f"H_REQUIRED_{column.upper()}",
                blank(df[column]),
                f"{column} wajib terisi.",
            )

    # Contract primary keys, including composite keys.
    for table, contract in SCHEMAS.items():
        primary_key = contract["primary_key"]

        if not primary_key:
            continue

        df = frames[table]
        key_values = df[primary_key].astype(str).apply(
            lambda col: col.str.strip()
        )

        # Empty keys are handled by required-field rules where applicable.
        duplicate_mask = key_values.duplicated(
            subset=primary_key,
            keep="first",
        )

        register_hard_violation(
            table,
            f"H_PRIMARY_KEY_UNIQUE_{table.upper()}",
            duplicate_mask,
            f"Primary key {primary_key} harus unik.",
        )

    # Invalid nonempty values for declared data types.
    for table, contract in SCHEMAS.items():
        df = frames[table]

        for column, data_type in contract["columns"].items():
            values = df[column]
            nonempty = ~blank(values)

            if data_type == "integer":
                parsed = numeric(values)
                invalid = nonempty & (
                    parsed.isna() | (parsed % 1 != 0)
                )

            elif data_type == "decimal":
                parsed = numeric(values)
                invalid = nonempty & parsed.isna()

            elif data_type == "timestamp":
                parsed = pd.to_datetime(values, errors="coerce")
                invalid = nonempty & parsed.isna()

            else:
                continue

            register_hard_violation(
                table,
                f"H_TYPE_{column.upper()}",
                invalid,
                (
                    f"Nilai nonkosong pada {column} "
                    f"tidak sesuai tipe {data_type}."
                ),
            )

    # --------------------------------------------------------
    # Referential integrity after quarantine.
    # If a parent row is quarantined, its children are checked
    # again. Repeat until no new child rows are quarantined.
    # --------------------------------------------------------

    foreign_keys = [
        ("orders", "customer_id", "customers", "customer_id"),
        ("order_items", "order_id", "orders", "order_id"),
        ("order_items", "product_id", "products", "product_id"),
        ("order_items", "seller_id", "sellers", "seller_id"),
        ("order_payments", "order_id", "orders", "order_id"),
        ("order_reviews", "order_id", "orders", "order_id"),
    ]

    cascade_rule_counts = {}

    changed = True

    while changed:
        changed = False

        for child_table, child_col, parent_table, parent_col in foreign_keys:
            child_df = frames[child_table]
            parent_df = frames[parent_table]

            valid_parent_mask = ~quarantine_masks[parent_table]

            valid_parent_keys = set(
                parent_df.loc[valid_parent_mask, parent_col]
                .astype(str)
                .str.strip()
            )

            child_keys = child_df[child_col].astype(str).str.strip()

            invalid_fk = (
                ~quarantine_masks[child_table]
                & (
                    blank(child_keys)
                    | ~child_keys.isin(valid_parent_keys)
                )
            )

            if not invalid_fk.any():
                continue

            rule_name = (
                f"H_FK_AFTER_QUARANTINE_{child_table.upper()}_"
                f"{child_col.upper()}"
            )

            count = int(invalid_fk.sum())

            quarantine_masks[child_table] |= invalid_fk

            for idx in child_df.index[invalid_fk]:
                if rule_name not in quarantine_reasons[child_table][idx]:
                    quarantine_reasons[child_table][idx].append(rule_name)

            if rule_name not in cascade_rule_counts:
                cascade_rule_counts[rule_name] = {
                    "rule": rule_name,
                    "table": child_table,
                    "type": "hard",
                    "action": "quarantine",
                    "violations": 0,
                    "description": (
                        f"{child_col} tidak memiliki baris induk "
                        "yang lolos pemeriksaan hard rules."
                    ),
                }

            cascade_rule_counts[rule_name]["violations"] += count
            changed = True

    rule_counts.extend(cascade_rule_counts.values())

    # --------------------------------------------------------
    # Generate quarantine files and table summaries.
    # --------------------------------------------------------

    # Remove stale quarantine files from previous evaluations.
    for table in SCHEMAS:
        stale_path = QUARANTINE_DIR / f"{table}_quarantine.csv"

        if stale_path.exists():
            stale_path.unlink()

    table_summaries = []

    for table, df in frames.items():
        mask = quarantine_masks[table]
        quarantined = df.loc[mask].copy()

        quarantined["_quarantine_reasons"] = [
            "|".join(quarantine_reasons[table][idx])
            for idx in quarantined.index
        ]

        if not quarantined.empty:
            path = QUARANTINE_DIR / f"{table}_quarantine.csv"
            quarantined.to_csv(
                path,
                index=False,
                encoding="utf-8-sig",
            )

        total = len(df)
        quarantine_count = int(mask.sum())
        accepted_count = total - quarantine_count

        quarantine_pct = (
            quarantine_count / total * 100
            if total
            else 0.0
        )

        threshold = DQ_GATE["max_quarantine_pct_by_table"].get(
            table,
            DQ_GATE["max_quarantine_pct_default"],
        )

        if quarantine_pct > threshold:
            verdict = "FAIL"
        elif quarantine_count:
            verdict = "PASS+KARANTINA"
        else:
            verdict = "PASS"

        table_summaries.append({
            "table": table,
            "source_rows": total,
            "quarantined_rows": quarantine_count,
            "accepted_rows": accepted_count,
            "quarantine_pct": quarantine_pct,
            "threshold_pct": threshold,
            "verdict": verdict,
        })

    # --------------------------------------------------------
    # Write DQ report.
    # --------------------------------------------------------

    report = [
        "# Olist Data Quality Report",
        "",
        "> Evaluasi data sumber. Data sumber tidak diubah.",
        "",
        "## Ringkasan per tabel",
        "",
        "| Tabel | Baris sumber | Karantina unik | Baris diterima | % karantina | Ambang | Verdict |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]

    for item in table_summaries:
        report.append(
            f"| {item['table']} | {item['source_rows']} | "
            f"{item['quarantined_rows']} | {item['accepted_rows']} | "
            f"{item['quarantine_pct']:.4f}% | "
            f"{item['threshold_pct']:.2f}% | {item['verdict']} |"
        )

    report.extend([
        "",
        "## Pelanggaran per aturan",
        "",
        "| Rule | Tabel | Jenis | Aksi | Jumlah pelanggaran | Deskripsi |",
        "|---|---|---|---|---:|---|",
    ])

    for item in rule_counts:
        description = item["description"].replace("|", "\\|")
        report.append(
            f"| {item['rule']} | {item['table']} | {item['type']} | "
            f"{item['action']} | {item['violations']} | {description} |"
        )

    report.extend([
        "",
        "## Interpretasi",
        "",
        "- Hard rule: pelanggaran mengarantina baris.",
        "- Soft rule: pelanggaran hanya dicatat; baris tetap diterima.",
        "- Karantina unik dihitung per baris, meskipun melanggar beberapa aturan.",
        "- Baris anak yang merujuk ke induk yang dikarantina ikut diperiksa ulang.",
        "- FAIL berarti persentase karantina melampaui ambang.",
        "- PASS+KARANTINA berarti ada baris dikarantina tetapi masih di bawah ambang.",
        "- PASS berarti tidak ada baris yang dikarantina.",
        "- Baris sumber = baris diterima + baris karantina.",
        "",
        "Catatan: aturan kontrak dan pemeriksaan tambahan dicatat terpisah. "
        "Jumlah pelanggaran per aturan tidak boleh dijumlahkan untuk memperoleh "
        "jumlah baris karantina karena satu baris dapat melanggar beberapa aturan.",
    ])

    report_path = OUT_DIR / "dq_report.md"
    report_path.write_text("\n".join(report), encoding="utf-8")

    print("\nVerdict per tabel:")

    for item in table_summaries:
        print(
            f"{item['table']}: {item['verdict']} — "
            f"{item['quarantined_rows']:,} karantina "
            f"({item['quarantine_pct']:.4f}%)"
        )

    print(f"\nLaporan  : {report_path}")
    print(f"Karantina: {QUARANTINE_DIR}")

    failed_tables = [
        item["table"]
        for item in table_summaries
        if item["verdict"] == "FAIL"
    ]

    result = {
        "passed": not failed_tables,
        "failed_tables": failed_tables,
        "table_summaries": table_summaries,
        "rule_counts": rule_counts,
        "quarantine_masks": quarantine_masks,
        "quarantine_reasons": quarantine_reasons,
        "frames": frames,
    }

    if failed_tables:
        print("\nDQ GATE: FAIL")
        print("Tabel yang melampaui ambang karantina:")

        for table in failed_tables:
            print(f"- {table}")
    else:
        print("\nDQ GATE: PASS")

    return result


if __name__ == "__main__":
    result = main()
    raise SystemExit(0 if result["passed"] else 1)
