# Olist Data Platform — T5 Mart & Dashboard Report

**Status:** Draft — enam data mart berhasil dibuat dan validasi awal lulus  
**Tanggal:** 17 Oktober 2026  
**Sumber:** PostgreSQL `dw.*`, `mart.*`, dan `stream.consumer_metrics`

> Catatan: Judul Q1–Q4 pada laporan ini mengelompokkan area sales, delivery, seller, dan customer RFM. Cocokkan dengan redaksi pertanyaan resmi pada brief capstone sebelum pengumpulan akhir.

## 1. Executive Summary

| Area | Hasil utama | Kesimpulan |
|---|---|---|
| Sales | Merchandise revenue R$13.221.498,11; freight R$2.198.275,64 | Nilai barang dan freight dipisahkan agar definisi penjualan jelas. |
| Delivery | 6.534 order terlambat dari 96.470 order dengan status keterlambatan diketahui; late rate 6,77% | Denominator tidak memasukkan order dengan `is_late IS NULL`. |
| Seller | 1.271 dari 3.095 seller memiliki minimal 10 order | Seller eligible lebih layak dibandingkan dengan ambang volume yang sama. |
| Customer RFM | 93.358 customer dengan order delivered; tanggal referensi 2018-10-17 | Frequency score menggunakan aturan berbasis jumlah order. |
| Reconciliation | 98.362 dari 99.441 order matched atau 98,91% | Target minimal 98% tercapai. |
| Unexplained difference | 30 order dengan total selisih absolut R$78,87 | Memerlukan investigasi lanjutan. |
| Stream | 6 batch, 1.954 pesan diterima, 382 event baru, 1.568 duplikat, 16 out-of-order, 4 DLQ | Freshness baru merepresentasikan batch yang tercatat. |

## 2. Q1 — Monthly Sales

**Pertanyaan:** Berapa nilai penjualan bulanan berdasarkan kategori produk dan state customer?

**Jawaban:** Order berstatus `delivered` menghasilkan merchandise revenue sebesar **R$13.221.498,11**, sedangkan freight tercatat sebesar **R$2.198.275,64**. Mart `mart.monthly_sales` berisi 11.853 kombinasi bulan, kategori, dan state.

### Definisi metrik

- Hanya order dengan `order_status = 'delivered'`.
- Merchandise revenue = `SUM(fact_order_item.price)`.
- Freight = `SUM(fact_order_item.freight_value)`, ditampilkan terpisah.
- State customer ditentukan dari ZIP pada order yang dipetakan ke `dw.dim_geo`; ZIP yang tidak terpetakan diberi label `unknown`.
- Satu order dapat memiliki beberapa kategori. Karena itu, jumlah order pada setiap kategori tidak boleh dijumlahkan untuk menghitung total order unik.

### Query penelusuran

```sql
SELECT
    month_start,
    category,
    customer_state,
    delivered_orders,
    merchandise_revenue,
    freight_revenue
FROM mart.monthly_sales
ORDER BY month_start, merchandise_revenue DESC;
```

### Insight

Nilai merchandise dan freight perlu dilaporkan terpisah agar pertumbuhan penjualan barang tidak tercampur dengan biaya pengiriman. Dashboard perlu memperlihatkan tren bulanan dan kategori dengan kontribusi merchandise revenue terbesar.

## 3. Q2 — Delivery Performance

**Pertanyaan:** Bagaimana performa pengiriman dan hubungannya dengan skor review?

**Jawaban:** Terdapat 6.534 order terlambat dari 96.470 order dengan status ketepatan pengiriman diketahui. Late rate tercatat **6,77%**.

### Definisi metrik

- Late rate = `late_orders / known_delivery_orders × 100`.
- Denominator hanya menghitung order dengan `is_late IS NOT NULL`.
- Rata-rata hari pengiriman dihitung dari waktu pembelian sampai waktu barang diterima customer pada order delivered yang memiliki timestamp lengkap.
- Review score berasal dari `dw.fact_review`.

### Query penelusuran

```sql
SELECT
    month_start,
    customer_state,
    known_delivery_orders,
    late_orders,
    on_time_orders,
    late_rate_pct,
    avg_delivery_days,
    avg_review_score
FROM mart.delivery_performance
ORDER BY month_start, late_rate_pct DESC;
```

### Insight

Late rate sebesar 6,77% memberikan baseline performa pengiriman. Dashboard sebaiknya membandingkan late rate dan rata-rata review menurut bulan serta state untuk mencari pola yang perlu diinvestigasi. Perbedaan skor review tidak membuktikan bahwa keterlambatan menyebabkan penurunan kepuasan.

## 4. Q3 — Seller Scorecard

**Pertanyaan:** Seller mana yang dapat dibandingkan berdasarkan volume, keterlambatan, dan review?

**Jawaban:** Dari 3.095 seller, sebanyak **1.271 seller** memiliki setidaknya 10 order sehingga memenuhi ambang minimum perbandingan.

### Definisi metrik

- Volume dihitung berdasarkan order unik per seller, bukan jumlah baris item.
- `is_eligible_for_comparison = TRUE` jika `total_orders >= 10`.
- Merchandise revenue dihitung dari nilai `price` item yang terkait dengan seller.
- Freight ditampilkan sebagai metrik terpisah.
- Seller dengan kurang dari 10 order tetap disimpan, tetapi sebaiknya tidak dibandingkan secara langsung dengan seller ber-volume besar.

### Query penelusuran

```sql
SELECT
    seller_id,
    seller_state,
    total_orders,
    delivered_orders,
    late_orders,
    late_order_rate_pct,
    avg_review_score,
    merchandise_revenue,
    is_eligible_for_comparison
FROM mart.seller_scorecard
WHERE is_eligible_for_comparison
ORDER BY late_order_rate_pct DESC NULLS LAST;
```

### Insight

Hanya 1.271 dari 3.095 seller yang memenuhi ambang volume. Dashboard perlu menampilkan jumlah order bersama late rate dan review score agar seller dengan sampel kecil tidak terlihat setara dengan seller yang memiliki volume besar.

## 5. Q4 — Customer RFM Segmentation

**Pertanyaan:** Bagaimana segmentasi customer berdasarkan Recency, Frequency, dan Monetary?

**Jawaban:** `mart.customer_rfm` berisi **93.358 customer** dengan setidaknya satu order delivered. Tanggal referensi recency adalah **17 Oktober 2018**, berdasarkan tanggal pembelian maksimum pada dataset yang digunakan.

### Definisi metrik

- **Recency:** jumlah hari dari tanggal referensi dataset ke tanggal order delivered terakhir customer.
- **Frequency:** jumlah order delivered unik customer.
- **Monetary:** total nilai `price` item dari order delivered, tidak termasuk freight.
- Frequency score menggunakan aturan, bukan quintile mentah:
  - 1 order: skor 1
  - 2 order: skor 2
  - 3–4 order: skor 3
  - 5–7 order: skor 4
  - 8 order atau lebih: skor 5
- Recency score menggunakan rentang hari yang ditetapkan dalam SQL mart.
- Monetary score memakai `NTILE(5)` berdasarkan nilai monetary.

### Distribusi frequency score

| Frequency score | Jumlah customer |
|---:|---:|
| 1 | 90.557 |
| 2 | 2.573 |
| 3 | 209 |
| 4 | 17 |
| 5 | 2 |
| **Total** | **93.358** |

### Query penelusuran

```sql
SELECT
    recency_score,
    frequency_score,
    monetary_score,
    COUNT(*) AS customers,
    ROUND(AVG(monetary_value), 2) AS avg_monetary_value
FROM mart.customer_rfm
GROUP BY recency_score, frequency_score, monetary_score
ORDER BY recency_score DESC, frequency_score DESC, monetary_score DESC;
```

### Insight

Distribusi sangat terkonsentrasi pada customer dengan satu order delivered. Segmentasi RFM dapat membantu mengidentifikasi customer yang relatif baru, sering membeli, atau memiliki monetary value tinggi, tetapi label segmen harus diperlakukan sebagai aturan analitis dan bukan hasil eksperimen pemasaran.

## 6. Order Reconciliation

**Pertanyaan:** Apakah nilai item dan pembayaran cocok pada level order?

**Hasil:** **98.362 dari 99.441 order matched (98,91%)**, melampaui target minimum 98%. Sebanyak 30 order belum terjelaskan, dengan total selisih absolut **R$78,87**.

| Kelas | Order | Interpretasi |
|---|---:|---|
| `matched` | 98.362 | Nilai item + freight cocok dengan total payment dalam toleransi 0,01. |
| `without_items` | 775 | Tidak ada baris item untuk order. |
| `installment_related` | 266 | Ada selisih dan payment memiliki installment lebih dari satu. Ini indikator, bukan bukti penyebab. |
| `unexplained` | 30 | Selisih belum terjelaskan oleh aturan klasifikasi. |
| `voucher_related` | 7 | Ada selisih dan order memiliki payment voucher. Ini indikator, bukan bukti penyebab. |
| `without_payment` | 1 | Ada item tetapi tidak ditemukan baris payment. |

### Definisi

- `item_plus_freight = SUM(price + freight_value)`.
- `paid_value = SUM(payment_value)`.
- Order dianggap `matched` jika selisih absolut ≤ 0,01.
- `unexplained_abs_difference` hanya menjumlahkan selisih absolut dari kelas `unexplained`.
- Label voucher dan installment merupakan indikator diagnostik, bukan penyebab yang telah dibuktikan.

### Query penelusuran

```sql
SELECT
    order_id,
    order_status,
    item_value,
    item_plus_freight,
    paid_value,
    difference_paid_minus_items_freight,
    has_voucher,
    has_installments
FROM mart.order_reconciliation
WHERE reconciliation_class = 'unexplained'
ORDER BY ABS(difference_paid_minus_items_freight) DESC;
```

### Pertanyaan untuk tim finance Olist

Untuk 30 order unexplained, dapatkah tim finance mengonfirmasi apakah selisih terkait dengan diskon, refund, pembatalan parsial, atau penyesuaian pembayaran yang tidak tercakup dalam kolom sumber yang digunakan? Bukti transaksi pada level order diperlukan sebelum menetapkan penyebab final.

## 7. Stream Status dan Freshness

Enam batch tercatat antara **17 Oktober 2026 03:01:46 UTC** dan **17 Oktober 2026 03:37:17 UTC**.

| Metrik | Hasil |
|---|---:|
| Batch tercatat | 6 |
| Messages received | 1.954 |
| New events | 382 |
| Duplicates ignored | 1.568 |
| Out-of-order | 16 |
| DLQ count | 4 |
| Rata-rata freshness p50 | 50.324,30 ms |
| Maksimum freshness p95 | 82.114,87 ms |

Freshness p50/p95 dilaporkan dalam milidetik sesuai kolom sumber. Enam batch belum cukup untuk menyimpulkan kestabilan throughput jangka panjang. Jika lag meningkat saat replay, dokumentasikan sebagai keterbatasan atau eksperimen lanjutan dan investigasi DLQ serta event out-of-order secara terpisah.

### Query penelusuran

```sql
SELECT
    batch_minute,
    batches,
    messages_received,
    new_events,
    duplicates_ignored,
    out_of_order,
    dlq_count,
    avg_freshness_p50_ms,
    avg_freshness_p95_ms,
    max_freshness_p95_ms
FROM mart.stream_freshness
ORDER BY batch_minute;
```

## 8. Batasan Analisis

1. Redaksi resmi Q1–Q4 perlu dicocokkan dengan brief capstone sebelum pengumpulan akhir.
2. Merchandise revenue bukan profit dan bukan total payment.
3. Pemetaan state bergantung pada ZIP customer yang tersedia pada `dw.dim_geo`; nilai `unknown` perlu dipantau.
4. Klasifikasi voucher/installment bersifat heuristik.
5. RFM hanya mencakup customer dengan order delivered dan memakai tanggal referensi dataset, bukan tanggal saat ini.
6. Stream freshness hanya berdasarkan enam batch yang tercatat dan bukan SLA jangka panjang.
7. Setiap angka dashboard harus dapat ditelusuri dari mart ke fact table yang mendasarinya.

## 9. Status Implementasi T5

- [x] Enam mart terbentuk di schema `mart`.
- [x] Reconciliation matched rate mencapai 98,91%.
- [x] Late rate menggunakan denominator dengan `is_late` diketahui.
- [x] Seller eligibility menggunakan ambang minimum 10 order.
- [x] Frequency RFM menggunakan skor berbasis aturan.
- [x] Stream freshness, DLQ, dan out-of-order dilaporkan.
- [x] Laporan awal disusun dari hasil validasi mart.
- [ ] Ekspor mart ke bucket MinIO `gold`.
- [ ] Dashboard dengan visual untuk Q1–Q4 dan freshness.
- [ ] Cocokkan redaksi Q1–Q4 dengan brief resmi.
