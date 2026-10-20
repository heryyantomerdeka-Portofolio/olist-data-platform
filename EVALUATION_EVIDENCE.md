# Olist Data Platform — Evaluation Evidence

**Tanggal evaluasi:** 19 Oktober 2026

## 1. Ringkasan Status

Dokumen ini merangkum bukti evaluasi Olist Data Platform berdasarkan laporan yang tersedia, automated tests, dan pengujian streaming terbaru. Status PASS pada laporan mengacu pada hasil pemeriksaan yang tercatat, bukan jaminan bahwa seluruh tahapan dapat dijalankan ulang melalui satu entry point.

| Tahap | Bukti utama | Status evaluasi |
|---|---|---|
| T0 — Environment | Docker services dan konfigurasi proyek | Perlu verifikasi entry point |
| T1 — Bronze ingestion | `outputs/bronze_report.md` | Bukti ingestion tersedia; entry point perlu verifikasi |
| T2 — Silver | `outputs/load_report.md` | PASS berdasarkan laporan |
| T3 — PostgreSQL load | `outputs/postgres_load_report.json` | PASS berdasarkan laporan |
| T4 — Data Warehouse | `outputs/dw_report.md` | PASS berdasarkan laporan |
| T5 — Data Mart dan Gold | `outputs/marts_report.md`, `outputs/gold/export_validation.csv` | 6 mart tervalidasi berdasarkan laporan |
| T6 — Streaming | Producer reports, failure tests, automated tests, dan pengujian event sintetis | Event baru dan replay idempoten PASS; beberapa skenario end-to-end masih perlu dibuktikan |

**Catatan status:** hasil laporan yang tersimpan bisa berasal dari waktu eksekusi yang berbeda. Karena itu, status evaluasi tidak boleh dianggap sebagai hasil satu kali eksekusi end-to-end yang seragam.

## 2. Bronze Ingestion

**Artefak:** `outputs/bronze_report.md`

Bronze ingestion mencatat sembilan file sumber dari dataset Olist. Laporan menyertakan informasi versi objek dan checksum SHA-256 untuk setiap file.

| Tabel sumber | Jumlah baris |
|---|---:|
| `customers` | 99.441 |
| `geolocation` | 1.000.163 |
| `orders` | 99.441 |
| `order_items` | 112.650 |
| `order_payments` | 103.886 |
| `order_reviews` | 99.224 |
| `products` | 32.951 |
| `sellers` | 3.095 |
| `category_translation` | 71 |
| **Total** | **1.550.922** |

### Bukti yang tersedia

- Sembilan file sumber tercatat dalam laporan.
- Versi objek dan SHA-256 tercatat untuk setiap file.
- Status `unchanged` menunjukkan file tidak berubah dibandingkan versi yang menjadi acuan laporan saat itu.

### Batasan

Keberadaan `outputs/bronze_report.md` membuktikan adanya artefak hasil ingestion. Namun, entry point T1 perlu diperiksa untuk memastikan ingestion dapat dijalankan ulang secara konsisten melalui `pipeline.py`.

**Status:** bukti ingestion tersedia; keterulangan melalui entry point perlu diverifikasi.

## 3. Silver dan Data Quality

**Artefak:** `outputs/load_report.md`

Berdasarkan laporan Silver, proses menghasilkan data yang telah melalui transformasi dan pemeriksaan kualitas data.

| Metrik | Hasil laporan |
|---|---:|
| Jumlah tabel | 9 |
| Total baris Silver | 1.550.922 |
| Total baris karantina | 0 |
| Durasi proses Silver | 635,158 detik |

Laporan menyatakan bahwa jumlah baris Parquet cocok dengan jumlah baris yang diterima pada seluruh tabel.

### Peringatan soft-rule

| Aturan kualitas data | Jumlah pelanggaran |
|---|---:|
| Geolocation duplicate | 261.831 |
| Order tanpa approval timestamp | 160 |
| Anomali kronologi pengiriman | 189 |
| Payment installment tidak positif | 2 |
| Review tanpa komentar | 56.537 |
| Dimensi atau berat produk tidak positif | 4 |

### Interpretasi

- Nol baris karantina tidak berarti semua data bebas dari masalah kualitas.
- Soft-rule dapat mencatat anomali yang dipertahankan untuk analisis atau ditangani melalui aturan transformasi.
- Jumlah pelanggaran dari berbagai aturan tidak boleh dijumlahkan untuk menyatakan jumlah baris bermasalah unik. Satu baris dapat melanggar lebih dari satu aturan.
- Angka pada tabel di atas merupakan angka yang tercatat dalam laporan dan belum tentu mencerminkan hasil eksekusi ulang terbaru.

**Status:** PASS berdasarkan laporan Silver yang tersedia.

## 4. PostgreSQL Load

**Artefak:** `outputs/postgres_load_report.json`

Laporan PostgreSQL mencatat pemuatan data ke schema `raw`.

| Metrik | Hasil laporan |
|---|---|
| Database | `olist` |
| Schema | `raw` |
| Total baris | 1.550.922 |
| Status laporan | PASS |

Jumlah baris Silver, jumlah baris yang disalin, dan jumlah baris pada database cocok pada tabel yang tercakup dalam laporan.

Durasi Silver sebesar 635,158 detik berasal dari laporan proses Silver. Timestamp pada laporan PostgreSQL menunjukkan waktu penyelesaian load yang terpisah. Keduanya tidak boleh dianggap sebagai satu pengukuran durasi yang sama.

### Batasan

Status ini berdasarkan artefak laporan yang tersedia. Untuk menetapkan baseline evaluasi final, laporan perlu dicocokkan dengan versi kode dan hasil eksekusi yang sama.

**Status:** PASS berdasarkan laporan PostgreSQL yang tersedia.

## 5. Data Warehouse

**Artefak:** `outputs/dw_report.md`

Laporan Data Warehouse mencatat jumlah baris berikut.

| Tabel | Jumlah baris |
|---|---:|
| `dim_customer` | 96.096 |
| `dim_date` | 1.314 |
| `dim_geo` | 19.011 |
| `dim_product` | 32.951 |
| `dim_seller` | 3.095 |
| `fact_order` | 99.441 |
| `fact_order_item` | 112.650 |
| `fact_payment` | 103.886 |
| `fact_review` | 98.673 |

### Pemeriksaan integritas yang dilaporkan

| Pemeriksaan | Hasil |
|---|---:|
| Duplikat pada grain fact order item | 0 |
| Duplikat pada grain fact review | 0 |
| Invalid geolocation rows | 0 |
| Invalid `is_late` rows | 0 |
| Foreign key yang belum tervalidasi | 0 |
| Foreign key | 18 |
| Primary key | 9 |

### Catatan grain dan pemodelan

- `dim_customer` menggunakan `customer_unique_id` sebagai grain pelanggan.
- `fact_review` memilih satu review terbaru per order.
- Terdapat 775 order tanpa item.
- Terdapat 1 order tanpa payment.
- SCD Type 1 menyimpan atribut terbaru, bukan riwayat perubahan atribut.

Perbedaan jumlah antara tabel sumber dan tabel dimensi atau fakta harus dibaca sesuai grain masing-masing. Jumlah baris yang berbeda tidak otomatis menunjukkan kegagalan load.

**Status:** PASS berdasarkan pemeriksaan grain dan integritas yang tercatat dalam laporan.

## 6. Data Mart dan Gold Export

**Artefak utama:**
- `outputs/marts_report.md`
- `outputs/gold/export_validation.csv`
- `outputs/olist-data-platform.pbix`

### 6.1 Ringkasan metrik bisnis

Berdasarkan `outputs/marts_report.md`, hasil yang tercatat adalah sebagai berikut.

| Metrik | Hasil laporan |
|---|---:|
| Merchandise revenue | R$13.221.498,11 |
| Freight revenue | R$2.198.275,64 |
| Order dengan status keterlambatan diketahui | 96.470 |
| Late delivery | 6.534 |
| Late rate | 6,77% |
| Seller eligible untuk perbandingan | 1.271 dari 3.095 |
| Customer RFM | 93.358 |
| Order reconciliation matched | 98.362 dari 99.441 |
| Reconciliation matched rate | 98,91% |
| Order unexplained | 30 |
| Total selisih absolut untuk order unexplained | R$78,87 |

Late rate dihitung terhadap 96.470 order yang memiliki status keterlambatan diketahui, bukan seluruh 99.441 order.

Selisih rekonsiliasi perlu ditafsirkan berdasarkan definisi perhitungan, perlakuan pembulatan, dan komponen transaksi yang termasuk dalam perbandingan.

### 6.2 Validasi ekspor Gold

Berdasarkan `outputs/gold/export_validation.csv`, keenam mart memiliki jumlah baris sumber dan ekspor yang sama.

| Mart | Baris sumber | Baris ekspor |
|---|---:|---:|
| `customer_rfm` | 93.358 | 93.358 |
| `delivery_performance` | 584 | 584 |
| `monthly_sales` | 11.853 | 11.853 |
| `order_reconciliation` | 99.441 | 99.441 |
| `seller_scorecard` | 3.095 | 3.095 |
| `stream_freshness` | 6 | 6 |

**Status ekspor:** keenam mart berstatus PASS berdasarkan laporan validasi.

Kecocokan jumlah baris menunjukkan kesesuaian kuantitas data sumber dan ekspor. Hal itu tidak dengan sendirinya membuktikan bahwa setiap nilai, definisi bisnis, dan agregasi telah benar; pemeriksaan tersebut perlu mengacu pada aturan masing-masing mart.

### 6.3 Power BI dashboard

File dashboard tersedia di `outputs/olist-data-platform.pbix`.

Keberadaan file membuktikan bahwa artefak dashboard tersedia. Evaluasi akhir tetap perlu memeriksa kesesuaian visual, definisi metrik, filter, dan kesimpulan dashboard dengan mart serta pertanyaan Q1–Q4 pada brief resmi capstone.

Dashboard yang tersedia tidak boleh dianggap telah lulus evaluasi visual hanya karena file `.pbix` sudah ada.

**Status:** enam mart tervalidasi berdasarkan laporan ekspor; dashboard tersedia dan perlu ditinjau terhadap brief resmi.

## 7. Streaming dan Failure Testing

### 7.1 Artefak pengujian

Bukti streaming yang tersedia meliputi:

- `outputs/failure_tests.md`
- `outputs/producer_report.json`
- `outputs/stream_fault_injection.json`
- Automated test suite
- Pengujian event sintetis pada 19 Oktober 2026

### 7.2 Automated tests

Pada eksekusi terakhir yang tercatat dalam sesi pengembangan, hasil automated test suite adalah:

`33 passed in 18.81s`

Perintah pengujian:

```powershell
python -m pytest -q
```

Hasil tersebut lebih baru daripada catatan historis 29 passed dalam dokumen sebelumnya. Angka 33 passed digunakan sebagai hasil terakhir yang diketahui, tetapi test suite tetap perlu dijalankan ulang pada versi final sebelum demo.

### 7.3 Failure tests sebelumnya

| Skenario | Bukti yang tercatat | Batasan |
|---|---|---|
| F1 — Producer replay | Event duplikat diabaikan tanpa menambah baris duplikat | Berlaku untuk skenario yang diuji |
| F2 — Crash sebelum offset commit | Consumer dijalankan ulang dengan consumer group yang sama; pemrosesan ulang bersifat idempoten | Tidak mencakup semua kemungkinan crash |
| F3 — Replay 148 pesan | 148 duplikat diabaikan, 0 event baru, 0 DLQ | Berlaku untuk batch tersebut |
| F4 — Broker tidak tersedia | Koneksi gagal saat broker mati dan pulih setelah broker dijalankan kembali | Bukan bukti retry berhasil saat broker masih mati |
| F5 — Validasi pesan | Unit test untuk field wajib yang hilang dan timestamp tidak valid lulus | Belum membuktikan alur Kafka-to-DLQ end-to-end |

Producer report sebelumnya mencatat 2 source orders, 6 unique base events, dan 0 fault yang diinjeksi. Hasil itu hanya merepresentasikan eksekusi producer tersebut.

### 7.4 Pengujian tambahan — Event baru

**Tanggal:** 19 Oktober 2026  
**Topic:** `olist.t6-smoke-20261019`

Pengujian menggunakan event sintetis dengan identitas:

- `event_id`: `TEST-T6-IDEMPOTENCY-20261019`
- `order_id`: `TEST-ORDER-T6-20261019`
- `status`: `created`

Pada pengiriman dan konsumsi pertama, hasil consumer adalah:

| Metrik | Hasil |
|---|---:|
| Messages received | 1 |
| New events | 1 |
| Duplicates ignored | 0 |
| Out-of-order | 0 |
| DLQ count | 0 |

**Hasil: PASS.** Consumer berhasil memproses event baru dan mencatatnya sebagai event baru.

### 7.5 Pengujian tambahan — Replay event yang sama

Event dengan `event_id` yang sama dikirim kembali ke topic pengujian. Pengujian replay menggunakan consumer group baru untuk membaca pesan replay, kemudian memverifikasi perilaku idempotensi pada database.

Hasil consumer:

| Metrik | Hasil |
|---|---:|
| Messages received | 1 |
| New events | 0 |
| Duplicates ignored | 1 |
| Out-of-order | 0 |
| DLQ count | 0 |

**Hasil: PASS.** Event replay dikenali sebagai duplikat dan tidak dimasukkan sebagai event baru.

Hasil tersebut konsisten dengan implementasi `INSERT ... ON CONFLICT (event_id) DO NOTHING` pada tabel `stream.order_events`.

### 7.6 Kesimpulan evaluasi T6

Pengujian tambahan membuktikan dua perilaku penting pada jalur pemrosesan event sintetis:

1. Event baru berhasil disimpan.
2. Replay dengan `event_id` yang sama diabaikan tanpa menghasilkan event baru.

Pengujian ini tidak membuktikan seluruh jaminan reliability sistem. Uji DLQ end-to-end, pengukuran freshness menyeluruh, dan pengujian kegagalan tambahan tetap perlu dinilai sesuai cakupan implementasi final.

**Status T6:** pemrosesan event baru dan idempotensi replay PASS pada pengujian sintetis. Status keseluruhan T6 belum boleh dinyatakan sepenuhnya selesai sebelum entry point dan skenario end-to-end yang relevan diverifikasi.

## 8. Batasan dan Pekerjaan Lanjutan

### 8.1 Pipeline entry point

Status implementasi T0, T1, dan T6 pada `pipeline.py` perlu diverifikasi terhadap kode aktual. Jika masih berupa placeholder, implementasi tersebut harus diselesaikan atau dokumentasi harus menjelaskan batasan entry point secara eksplisit.

Tidak boleh diklaim bahwa seluruh tahapan bisa dijalankan melalui satu perintah jika sebagian tahap belum terhubung ke implementasi yang sebenarnya.

### 8.2 Orchestration

Airflow tidak ditemukan pada konfigurasi Docker Compose yang diperiksa. Oleh karena itu, orchestration terjadwal melalui Airflow belum boleh diklaim selesai.

### 8.3 Dead-letter queue

Pengujian unit validasi pesan belum cukup untuk membuktikan bahwa pesan malformed melewati jalur Kafka-to-DLQ secara end-to-end. Uji tersebut perlu dijalankan dan hasil aktualnya dicatat sebelum DLQ dinyatakan terverifikasi sepenuhnya.

### 8.4 Freshness

Klaim freshness di bawah 60 detik perlu didukung pengukuran end-to-end dari waktu event dibuat sampai event tersedia di target yang ditentukan. Statistik dari sejumlah kecil batch tidak otomatis membuktikan SLA tersebut untuk keseluruhan pipeline.

### 8.5 Benchmark skala 100x

Klaim skala 100x memerlukan benchmark terukur dengan:
- Volume data dan skenario pembanding yang jelas.
- Durasi proses.
- Throughput.
- Penggunaan resource.
- Kondisi environment dan konfigurasi yang dicatat.

Tanpa bukti tersebut, klaim skala 100x belum dapat dinyatakan tervalidasi.

### 8.6 Rekonsiliasi transaksi

Sebanyak 30 order tercatat sebagai unexplained dengan total selisih absolut R$78,87. Selisih tersebut perlu ditelusuri menggunakan bukti transaksi dan aturan rekonsiliasi yang berlaku.

### 8.7 Definisi Q1–Q4

Definisi dan hasil mart perlu dicocokkan dengan brief resmi capstone untuk memastikan pertanyaan bisnis, metrik, dan visual dashboard sesuai dengan persyaratan evaluasi.

### 8.8 Konsistensi baseline

Laporan T0–T6 berasal dari eksekusi pada waktu yang berbeda. Jika dibutuhkan satu baseline evaluasi final, tahapan yang relevan perlu dijalankan ulang terhadap versi kode dan konfigurasi yang sama.

### 8.9 Data sintetis

Pengujian T6 menambahkan event sintetis ke tabel streaming. Sebelum demo atau evaluasi final, data uji tersebut perlu dibersihkan secara terarah atau diberi penanda yang jelas. Pembersihan harus dilakukan setelah bukti pengujian tersimpan dan tidak boleh menghapus data produksi atau data streaming lain.

## 9. Reproducibility dan Persiapan Demo

### 9.1 Automated tests

Jalankan dari direktori utama proyek:

```powershell
python -m pytest -q
```

Catat hasil aktual dari eksekusi terakhir, termasuk jumlah test yang lulus atau gagal. Jangan menganggap hasil historis tetap berlaku setelah perubahan kode.

### 9.2 Environment

Sebelum demo:

- Pastikan Docker services yang dibutuhkan tersedia dan sehat.
- Pastikan file `.env` tersedia secara lokal.
- Jangan menyimpan kredensial, password, token, atau file `.env` ke repository.
- Pastikan konfigurasi topic Kafka dan koneksi PostgreSQL sesuai dengan environment yang digunakan.
- Pastikan laporan sesuai dengan versi kode yang akan dipresentasikan.

### 9.3 Artefak dan dokumentasi

Pastikan artefak berikut tersedia dan konsisten:

- `outputs/bronze_report.md`
- `outputs/load_report.md`
- `outputs/postgres_load_report.json`
- `outputs/dw_report.md`
- `outputs/marts_report.md`
- `outputs/gold/export_validation.csv`
- `outputs/producer_report.json`
- `outputs/stream_fault_injection.json`
- `outputs/failure_tests.md`
- `outputs/olist-data-platform.pbix`
- `EVALUATION_EVIDENCE.md`
- `README.md`
- `RUNBOOK.md`

Daftar ini adalah checklist artefak yang diharapkan, bukan klaim bahwa semuanya telah diperiksa ulang pada satu eksekusi final.

### 9.4 Repository

Sebelum Git diinstal dan repository disiapkan:

- Periksa struktur direktori dan entry point.
- Pastikan file data mentah dan kredensial tidak ikut di-commit.
- Pastikan file laporan dan kode yang dibutuhkan untuk reproduksi tercakup dalam dokumentasi.
- Pastikan perintah menjalankan pipeline sesuai dengan implementasi aktual.
- Catat batasan yang masih tersisa secara terbuka.

## 10. Kesimpulan Evaluasi

Berdasarkan bukti yang tersedia, proyek Olist Data Platform memiliki artefak untuk Bronze ingestion, Silver transformation, PostgreSQL load, Data Warehouse, Data Mart, Gold export, dan streaming.

Laporan yang tersedia mencatat 1.550.922 baris untuk proses Silver dan PostgreSQL load serta validasi jumlah baris pada enam mart Gold. Pada streaming, automated test suite terakhir yang tercatat menghasilkan 33 passed. Pengujian sintetis terbaru juga menunjukkan bahwa event baru dapat diproses dan replay dengan `event_id` yang sama diabaikan.

Namun, status final keseluruhan proyek masih bergantung pada verifikasi entry point, konsistensi baseline, kesesuaian dashboard dengan brief capstone, serta bukti end-to-end untuk skenario yang belum diuji sepenuhnya.

Dengan demikian, evaluasi yang paling akurat adalah: **bukti untuk sejumlah tahap inti tersedia dan beberapa pemeriksaan lulus, sementara beberapa aspek integrasi, reliability, dan reproduksibilitas masih memerlukan verifikasi akhir.**
## T6 - Failure Test Status

Status bukti pengujian per 2026-10-20:

| Pengujian | Status | Catatan |
|---|---|---|
| F1 - Producer dijalankan dua kali | Belum tervalidasi sesuai target | 74 pesan dibaca; 0 event baru; 74 duplikasi. Target 37 event baru + 37 duplikasi belum terbukti. |
| F2 - Consumer mati sebelum offset commit | Perlu verifikasi | Catatan sebelumnya menyebut fault injection dengan exit code 86; bukti replay perlu diverifikasi. |
| F3 - Kafka broker berhenti saat replay | Belum terverifikasi | Belum ada bukti eksekusi yang terkonfirmasi di catatan ini. |
| F4 - Pipeline dijalankan ulang | Belum terverifikasi | Belum ada perbandingan hasil sebelum dan sesudah rerun yang terkonfirmasi. |
| F5 - Kolom wajib sumber dihilangkan | Belum terverifikasi | Belum ada bukti eksekusi yang terkonfirmasi di catatan ini. |

### Hasil automated tests

Rangkaian pytest sebelumnya menghasilkan **32 passed, 0 failed**.
Hasil ini hanya menyatakan rangkaian tes tersebut lulus; hasil itu tidak otomatis
membuktikan seluruh skenario failure injection F1-F5 lulus.

Detail dan interpretasi hasil F1-F5 dicatat dalam `outputs/failure_tests.md`.
