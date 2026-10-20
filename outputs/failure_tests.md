# T6 — Failure Test Evidence

Tanggal pembaruan: 2026-10-20

## 1. Ringkasan status

| Pengujian | Skenario | Status |
|---|---|---|
| F1 | Producer dijalankan dua kali; periksa idempotensi | Belum tervalidasi sesuai target |
| F2 | Consumer mati sebelum offset di-commit, lalu pesan diputar ulang | Perlu verifikasi bukti eksekusi |
| F3 | Kafka broker berhenti saat replay | Belum terverifikasi |
| F4 | Seluruh pipeline dijalankan ulang tanpa perubahan data sumber | Belum terverifikasi |
| F5 | Kolom wajib sumber dihilangkan | Belum terverifikasi |

Status di atas menunjukkan bukti yang tersedia saat dokumentasi ini diperbarui.
Skenario yang belum memiliki bukti eksekusi yang memadai tidak dinyatakan lulus.

## 2. F1 — Producer dijalankan dua kali

Topic:
`olist.t6-f1-test`

Consumer group:
`t6-f1-consumer`

Hasil consumer yang tercatat:

| Metrik | Hasil |
|---|---:|
| Messages received | 74 |
| New events | 0 |
| Duplicates ignored | 74 |
| Out-of-order events | 0 |
| DLQ count | 0 |

Producer melaporkan 37 event dasar pada masing-masing eksekusi.
Kedua eksekusi menggunakan data sumber yang menghasilkan ID event deterministik.

### Interpretasi

Consumer membaca 74 pesan dan mengabaikan semuanya sebagai duplikasi.
Hal ini konsisten dengan mekanisme idempotensi yang menggunakan `event_id`
dan `ON CONFLICT (event_id) DO NOTHING`.

Namun, hasil ini belum membuktikan skenario yang ditargetkan:
37 event baru pada pengiriman pertama dan 37 duplikasi pada pengiriman kedua.
Event yang sama kemungkinan sudah tersimpan di database sebelum pengujian ini.

### Keputusan

Status F1: **BELUM TERVALIDASI SESUAI TARGET**.

Jangan menyatakan F1 lulus hanya berdasarkan hasil 74 duplikasi.
Pengujian perlu diisolasi menggunakan event uji yang belum pernah diproses,
lalu memastikan pengiriman ulang tidak menambah baris unik.

## 3. F2 — Consumer berhenti sebelum offset di-commit

Skenario yang ditargetkan:
1. Consumer berhenti sebelum commit offset.
2. Consumer dijalankan kembali.
3. Pesan diproses ulang tanpa menggandakan event di database.

Catatan sebelumnya menyebutkan mekanisme fault injection dengan kode keluar 86.
Namun, bukti eksekusi lengkap dan hasil replay belum diverifikasi dalam catatan ini.

Status: **PERLU VERIFIKASI BUKTI EKSEKUSI**.

## 4. F3 — Kafka broker berhenti saat replay

Skenario yang ditargetkan:
1. Hentikan broker ketika replay berlangsung.
2. Pulihkan broker.
3. Lanjutkan pemrosesan dan periksa konsistensi data.

Status: **BELUM TERVERIFIKASI**.

## 5. F4 — Pipeline dijalankan ulang

Skenario yang ditargetkan:
1. Jalankan pipeline.
2. Jalankan pipeline sekali lagi tanpa mengubah sumber.
3. Bandingkan jumlah data, manifest, dan hasil akhir.

Status: **BELUM TERVERIFIKASI**.

## 6. F5 — Kolom wajib sumber dihilangkan

Skenario yang ditargetkan:
1. Gunakan salinan data uji dengan satu kolom wajib dihilangkan.
2. Jalankan validasi kontrak.
3. Pastikan proses gagal dengan pesan yang jelas dan tidak menerima data yang tidak valid.

Status: **BELUM TERVERIFIKASI**.

## 7. Unit test dan integration test

Hasil pengujian sebelumnya:
- 32 passed
- 0 failed

Hasil tersebut adalah bukti dari rangkaian pytest yang dijalankan saat itu.
Hasil ini tidak otomatis membuktikan bahwa seluruh skenario failure injection
F1–F5 sudah berhasil.

## 8. Aturan pelaporan

- Catat perintah, waktu eksekusi, exit code, dan output aktual untuk setiap skenario.
- Pisahkan hasil unit test dari hasil end-to-end.
- Jangan mengubah status menjadi lulus tanpa bukti yang sesuai.
- Simpan bukti pengujian baru dengan nama file yang konsisten di folder `outputs/`.

