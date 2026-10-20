
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "raw"

products = pd.read_csv(
    DATA / "olist_products_dataset.csv",
    dtype="string"
)

translations = pd.read_csv(
    DATA / "product_category_name_translation.csv",
    dtype="string"
)

category_col = "product_category_name"

translated_categories = set(
    translations[category_col].dropna()
)

# Kategori yang tidak memiliki pasangan terjemahan.
unmatched = products.loc[
    products[category_col].notna()
    & ~products[category_col].isin(translated_categories),
    ["product_id", category_col]
]

# Kategori yang kosong.
missing = products.loc[
    products[category_col].isna(),
    ["product_id", category_col]
]

print("=== Kategori tidak ditemukan dalam translation ===")
print(f"Jumlah baris: {len(unmatched)}")
print(unmatched.to_string(index=False))

print("\n=== Kategori produk kosong ===")
print(f"Jumlah baris: {len(missing)}")
print(missing.to_string(index=False))

print("\n=== Nilai kategori yang tidak cocok ===")
print(unmatched[category_col].value_counts(dropna=False))
