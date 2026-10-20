# Olist Data Platform — Data Quality Rules

## 1. Tujuan

Mendokumentasikan pemeriksaan kualitas data awal untuk dataset Olist. File CSV mentah tidak boleh diubah selama proses profiling dan validasi.

## 2. Aturan kualitas data

| ID | Tabel | Aturan | Tindakan |
|---|---|---|---|
| DQ-01 | Semua tabel | File harus tersedia, header sesuai kontrak, dan dapat dibaca | Gagalkan validasi jika tidak terpenuhi |
| DQ-02 | customers | `customer_id` harus unik dan tidak kosong | Tandai pelanggaran |
| DQ-03 | orders | `order_id` harus unik dan tidak kosong | Tandai pelanggaran |
| DQ-04 | order_items | Kombinasi `order_id + order_item_id` harus unik | Tandai pelanggaran |
| DQ-05 | order_payments | Kombinasi `order_id + payment_sequential` harus unik | Tandai pelanggaran |
| DQ-06 | products | `product_id` harus unik dan tidak kosong | Tandai pelanggaran |
| DQ-07 | sellers | `seller_id` harus unik dan tidak kosong | Tandai pelanggaran |
| DQ-08 | orders, order_items, payments, reviews | Foreign key harus merujuk ke record induk yang tersedia | Catat jumlah ID yang tidak cocok |
| DQ-09 | orders | Tanggal pembelian tidak boleh kosong; urutan tanggal diperiksa | Tandai pelanggaran |
| DQ-10 | orders | Tanggal persetujuan dan pengiriman yang kosong dievaluasi berdasarkan status order | Jangan otomatis mengisi nilai kosong |
| DQ-11 | reviews | `review_id` berulang harus diinvestigasi | Jangan menghapus atau mengasumsikan ID tunggal unik sebelum aturan bisnis ditentukan |
| DQ-12 | products | Nilai kosong pada atribut produk dicatat | Jangan otomatis mengisi atau menghapus produk |
| DQ-13 | reviews | Judul dan komentar kosong diperbolehkan untuk sementara | Pertahankan nilai kosong |
| DQ-14 | order_items, order_payments | Nilai numerik dan batas yang masuk akal harus diperiksa pada tahap berikutnya | Catat nilai tidak valid |
| DQ-15 | geolocation | Duplikasi dan validitas koordinat perlu diperiksa | Jangan menganggap prefix lokasi harus unik |

## 3. Hasil baseline

- 9 dari 9 file lolos pemeriksaan nama, kolom, dan jumlah baris.
- Keenam pemeriksaan relasi foreign key menghasilkan 0 ID yang tidak cocok.
- Kunci gabungan order item dan pembayaran tidak memiliki duplikasi.
- Ditemukan 789 grup `review_id` berulang yang memerlukan investigasi.
- Ditemukan 1.359 pelanggaran urutan tanggal persetujuan terhadap pengiriman ke carrier dan 23 pelanggaran urutan tanggal carrier terhadap penerimaan pelanggan.
- Nilai kosong ditemukan pada tanggal order, atribut produk, dan komentar review.

## 4. Kebijakan penanganan

1. Data mentah tidak diubah.
2. Anomali dicatat dengan tabel, kolom, aturan, dan jumlah pelanggaran.
3. Transformasi hanya dilakukan pada layer berikutnya dengan aturan yang terdokumentasi.
4. Nilai kosong tidak otomatis dianggap sebagai kesalahan.
5. Setiap keputusan deduplikasi harus mempunyai alasan dan bukti.

## 5. Status

Baseline profiling selesai. Investigasi lebih lanjut diperlukan untuk duplikasi `review_id`, kronologi tanggal, dan validitas nilai numerik.
