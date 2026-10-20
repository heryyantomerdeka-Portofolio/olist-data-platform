# Olist Data Platform — Runbook

## 1. Tujuan

Dokumen ini menjelaskan cara menyiapkan environment, menjalankan
pipeline Olist Data Platform, dan memverifikasi hasilnya.

## 2. Prasyarat

- Windows dengan Docker Desktop aktif.
- Python 3.10 atau lebih baru.
- Virtual environment `.venv` proyek.
- Dataset Olist tersedia di lokasi yang diharapkan oleh konfigurasi proyek.
- File `.env` tersedia secara lokal dan tidak dibagikan.
- Docker Compose services sesuai konfigurasi proyek.

## 3. Persiapan

Dari root proyek, aktifkan virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Periksa Python dan Docker:

```powershell
python --version
docker --version
docker compose ps
```

Pastikan konfigurasi `.env` tersedia:

```powershell
Test-Path .\.env
```

Jangan menampilkan atau menyalin nilai rahasia dari `.env` ke laporan.

## 4. Pengujian Otomatis

Jalankan:

```powershell
python -m pytest -q
```

Catat hasil aktual pengujian setiap kali kode berubah. Hasil sebelumnya
adalah 29 passed; angka ini bukan jaminan hasil pengujian berikutnya.

## 5. Menjalankan Pipeline

Periksa entry point dan opsi yang tersedia terlebih dahulu:

```powershell
Get-Content .\pipeline.py
```

Saat ini, T0, T1, dan T6 diketahui masih placeholder. Jangan menganggap
pemanggilan tahap tersebut sebagai eksekusi pipeline yang berhasil.

T2–T5 memiliki implementasi yang telah diuji. Sebelum menjalankan ulang,
periksa skrip tahap terkait dan efeknya terhadap database, object storage,
serta output yang sudah ada. Hindari menjalankan ulang tahap yang
menulis ulang data tanpa memahami perilaku idempotensinya.

## 6. Artefak Evaluasi

| Artefak | Kegunaan |
|---|---|
| `outputs/bronze_report.md` | Status dan metadata Bronze |
| `outputs/dq_report.md` | Hasil pemeriksaan kualitas data |
| `outputs/load_report.md` | Hasil pemrosesan Silver |
| `outputs/postgres_load_report.json` | Rekonsiliasi jumlah baris PostgreSQL |
| `outputs/dw_report.md` | Validasi Data Warehouse |
| `outputs/marts_report.md` | Ringkasan Data Mart |
| `outputs/gold/export_validation.csv` | Validasi ekspor enam mart Gold |
| `outputs/failure_tests.md` | Bukti pengujian skenario kegagalan |
| `EVALUATION_EVIDENCE.md` | Ringkasan bukti evaluasi dan keterbatasan |
| `outputs/olist-data-platform.pbix` | File dashboard Power BI |

## 7. Pemeriksaan Cepat

Pastikan artefak utama tersedia:

```powershell
$files = @(
    ".\outputs\bronze_report.md",
    ".\outputs\dq_report.md",
    ".\outputs\load_report.md",
    ".\outputs\postgres_load_report.json",
    ".\outputs\dw_report.md",
    ".\outputs\marts_report.md",
    ".\outputs\gold\export_validation.csv",
    ".\outputs\failure_tests.md",
    ".\outputs\olist-data-platform.pbix",
    ".\EVALUATION_EVIDENCE.md"
)

$files | ForEach-Object {
    [PSCustomObject]@{
        File = $_
        Exists = Test-Path $_
    }
} | Format-Table -AutoSize
```

## 8. Keamanan dan Batasan

- Jangan memasukkan dataset mentah, kredensial, atau `.env` ke repositori.
- Jangan menghapus Docker volumes untuk memperbaiki masalah sebelum
  memahami dampaknya terhadap data.
- Bedakan hasil unit test dari pengujian end-to-end.
- Klaim performa, freshness, retry, DLQ, dan skala harus didukung
  pengukuran yang sesuai.
- Perbarui laporan jika kode atau hasil pengujian berubah.

## T6 - Failure Testing and Evidence

### Tujuan
Memvalidasi ketahanan pipeline terhadap kegagalan dan memastikan pemrosesan
ulang tidak menghasilkan duplikasi data yang tidak diinginkan.

### Prasyarat
- Jalankan perintah dari direktori utama proyek.
- Aktifkan virtual environment `.venv`.
- Pastikan layanan yang diperlukan tersedia sebelum menjalankan pengujian.
- Gunakan topic dan data uji khusus untuk eksperimen streaming.
- Jangan menghapus volume Docker atau data produksi untuk membersihkan pengujian.

### Automated tests

Jalankan rangkaian tes:

```powershell
python -m pytest tests -q
```

Simpan output pengujian aktual sebagai bukti. Hasil sebelumnya adalah
32 passed dan 0 failed; hasil tersebut bukan bukti otomatis bahwa semua
failure scenario sudah tervalidasi.

### Failure scenarios

| ID | Skenario | Bukti yang harus disimpan |
|---|---|---|
| F1 | Producer mengirim event yang sama dua kali | Laporan kedua eksekusi producer dan statistik consumer |
| F2 | Consumer berhenti sebelum offset di-commit | Exit code, log, hasil replay, dan jumlah event unik |
| F3 | Kafka broker berhenti saat replay | Log kegagalan, pemulihan broker, dan hasil replay |
| F4 | Pipeline dijalankan ulang tanpa perubahan sumber | Jumlah baris, checksum, manifest, dan hasil sebelum/sesudah |
| F5 | Kolom wajib sumber dihilangkan | Input uji, pesan validasi, exit code, dan dampak pada output |

### Aturan evaluasi

1. Simpan output setiap skenario dengan nama file yang unik di `outputs/`.
2. Catat perintah yang dijalankan, waktu, exit code, dan hasil aktual.
3. Bandingkan jumlah event yang diterima dengan jumlah event unik di database.
4. Nyatakan skenario lulus hanya jika hasil aktual memenuhi kriteria penerimaan.
5. Jika bukti belum lengkap, gunakan status `BELUM TERVERIFIKASI`.
6. Catat ringkasan hasil di `outputs/failure_tests.md` dan `EVALUATION_EVIDENCE.md`.

### Status saat pembaruan dokumentasi

F1 belum memenuhi target 37 event baru dan 37 duplikasi. Hasil yang tercatat
adalah 74 pesan diterima, 0 event baru, dan 74 duplikasi.

Status F2-F5 harus ditentukan berdasarkan bukti eksekusi yang dapat diperiksa.
Jangan menganggap seluruh skenario lulus hanya karena automated tests berhasil.
