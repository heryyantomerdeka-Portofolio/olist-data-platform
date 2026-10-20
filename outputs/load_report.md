# Olist Silver Load Report

**Status pipeline:** PASS

| Tabel | Bronze version | Baris sumber | Baris diterima | Karantina | Baris Parquet | Durasi (detik) | Status |
|---|---|---:|---:|---:|---:|---:|---|
| customers | 1 | 99441 | 99441 | 0 | 99441 | 168.548 | PASS |
| geolocation | 1 | 1000163 | 1000163 | 0 | 1000163 | 101.202 | PASS |
| orders | 1 | 99441 | 99441 | 0 | 99441 | 67.219 | PASS |
| order_items | 1 | 112650 | 112650 | 0 | 112650 | 65.738 | PASS |
| order_payments | 1 | 103886 | 103886 | 0 | 103886 | 43.882 | PASS |
| order_reviews | 1 | 99224 | 99224 | 0 | 99224 | 59.446 | PASS |
| products | 1 | 32951 | 32951 | 0 | 32951 | 37.903 | PASS |
| sellers | 1 | 3095 | 3095 | 0 | 3095 | 29.858 | PASS |
| category_translation | 1 | 71 | 71 | 0 | 71 | 29.410 | PASS |

**Total durasi:** 635.158 detik

Jumlah baris Parquet harus sama dengan jumlah baris diterima.
Baris sumber = baris diterima + baris karantina.
