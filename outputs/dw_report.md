# T4 — Data Warehouse Report

**Status validasi: PASS**

## Jumlah baris

| Tabel | Baris |
|---|---:|
| `dim_customer` | 96,096 |
| `dim_date` | 1,314 |
| `dim_geo` | 19,011 |
| `dim_product` | 32,951 |
| `dim_seller` | 3,095 |
| `fact_order` | 99,441 |
| `fact_order_item` | 112,650 |
| `fact_payment` | 103,886 |
| `fact_review` | 98,673 |

## Pemeriksaan integritas

| Pemeriksaan | Jumlah masalah | Status |
|---|---:|---|
| `duplicate_fact_order_item_grain` | 0 | PASS |
| `duplicate_fact_review_grain` | 0 | PASS |
| `invalid_geolocation_rows` | 0 | PASS |
| `invalid_is_late_rows` | 0 | PASS |
| `unvalidated_foreign_keys` | 0 | PASS |

## Metrik tambahan

| Metrik | Nilai |
|---|---:|
| `deduplicated_review_orders` | 98,673 |
| `foreign_key_count` | 18 |
| `orders_without_items` | 775 |
| `orders_without_payments` | 1 |
| `primary_key_count` | 9 |
| `source_review_rows` | 99,224 |

## Catatan desain

- `dim_customer` menggunakan satu baris per `customer_unique_id`.
- SCD Type 1 mempertahankan atribut terbaru; riwayat atribut lama tidak disimpan.
- `fact_review` memilih review terbaru per order berdasarkan creation timestamp, answer timestamp, lalu review ID sebagai tie-breaker.
- `review_count` menyimpan jumlah review sumber untuk order yang memiliki review.
- `is_late` bernilai NULL bila status belum delivered atau tanggal aktual/estimasi tidak tersedia; perbandingan memakai tanggal kalender.
- Geografi yang tidak cocok dipetakan ke baris UNKNOWN; koordinat di luar batas geografis yang ditetapkan dikeluarkan.
- `is_incomplete_month` menandai batas rentang tanggal sumber, bukan menjamin kelengkapan ekstraksi.
