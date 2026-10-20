
from pathlib import Path
import pandas as pd
import json

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "outputs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

csv_files = sorted(DATA_DIR.glob("*.csv"))

if not csv_files:
    raise FileNotFoundError(
        f"Tidak ada CSV ditemukan di {DATA_DIR}. "
        "Periksa lokasi dataset Olist."
    )

summary = []
profile_details = []

for file_path in csv_files:
    print(f"Profiling: {file_path.name}")

    try:
        # Membaca seluruh kolom sebagai string agar
        # ID, kode pos, dan nilai dengan leading zero tetap aman.
        df = pd.read_csv(
            file_path,
            dtype="string",
            low_memory=False
        )

        rows, columns = df.shape
        duplicate_rows = int(df.duplicated().sum())
        missing_cells = int(df.isna().sum().sum())

        summary.append({
            "file": file_path.name,
            "rows": rows,
            "columns": columns,
            "duplicate_rows": duplicate_rows,
            "missing_cells": missing_cells,
            "file_size_mb": round(
                file_path.stat().st_size / (1024 * 1024), 2
            ),
            "status": "SUCCESS"
        })

        profile_details.append(f"\n## {file_path.name}\n")
        profile_details.append(f"- Rows: {rows:,}")
        profile_details.append(f"- Columns: {columns}")
        profile_details.append(
            f"- Fully duplicated rows: {duplicate_rows:,}"
        )
        profile_details.append(
            f"- Missing cells: {missing_cells:,}"
        )
        profile_details.append("\n### Column profile\n")
        profile_details.append(
            "| Column | Data type | Missing | Missing % | Distinct |"
        )
        profile_details.append("|---|---|---:|---:|---:|")

        for col in df.columns:
            missing = int(df[col].isna().sum())
            missing_pct = (
                round(missing / rows * 100, 2) if rows else 0
            )
            distinct = int(df[col].nunique(dropna=True))

            profile_details.append(
                f"| {col} | string | {missing:,} | "
                f"{missing_pct}% | {distinct:,} |"
            )

    except Exception as exc:
        summary.append({
            "file": file_path.name,
            "rows": None,
            "columns": None,
            "duplicate_rows": None,
            "missing_cells": None,
            "file_size_mb": round(
                file_path.stat().st_size / (1024 * 1024), 2
            ),
            "status": f"ERROR: {exc}"
        })

summary_df = pd.DataFrame(summary)

summary_path = OUTPUT_DIR / "profiling_summary.csv"
summary_df.to_csv(summary_path, index=False)

report_path = OUTPUT_DIR / "profile.md"

with report_path.open("w", encoding="utf-8") as f:
    f.write("# Olist Data Profiling Report\n\n")
    f.write(f"CSV files discovered: {len(csv_files)}\n\n")
    f.write("## Summary\n\n")
    f.write(summary_df.to_markdown(index=False))
    f.write("\n\n## Detailed Profiles\n")
    f.write("\n".join(profile_details))
    f.write("\n")

print("\nProfiling selesai.")
print(f"Summary: {summary_path}")
print(f"Report:  {report_path}")
print(summary_df.to_string(index=False))
