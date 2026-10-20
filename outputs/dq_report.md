# Olist Data Quality Report

> Evaluasi data sumber. Data sumber tidak diubah.

## Ringkasan per tabel

| Tabel | Baris sumber | Karantina unik | Baris diterima | % karantina | Ambang | Verdict |
|---|---:|---:|---:|---:|---:|---|
| customers | 99441 | 0 | 99441 | 0.0000% | 2.00% | PASS |
| geolocation | 1000163 | 0 | 1000163 | 0.0000% | 5.00% | PASS |
| orders | 99441 | 0 | 99441 | 0.0000% | 2.00% | PASS |
| order_items | 112650 | 0 | 112650 | 0.0000% | 2.00% | PASS |
| order_payments | 103886 | 0 | 103886 | 0.0000% | 2.00% | PASS |
| order_reviews | 99224 | 0 | 99224 | 0.0000% | 2.00% | PASS |
| products | 32951 | 0 | 32951 | 0.0000% | 2.00% | PASS |
| sellers | 3095 | 0 | 3095 | 0.0000% | 2.00% | PASS |
| category_translation | 71 | 0 | 71 | 0.0000% | 2.00% | PASS |

## Pelanggaran per aturan

| Rule | Tabel | Jenis | Aksi | Jumlah pelanggaran | Deskripsi |
|---|---|---|---|---:|---|
| H001_CUSTOMER_ID_REQUIRED | customers | hard | quarantine | 0 | customer_id wajib terisi. |
| H002_CUSTOMER_ID_UNIQUE | customers | hard | quarantine | 0 | customer_id harus unik. |
| H003_CUSTOMER_ZIP_FORMAT | customers | hard | quarantine | 0 | Kode pos pelanggan harus berupa 5 digit teks. |
| H004_GEO_ZIP_FORMAT | geolocation | hard | quarantine | 0 | Kode pos geolokasi harus berupa 5 digit teks. |
| H005_GEO_LAT_RANGE | geolocation | hard | quarantine | 0 | Latitude harus berada di antara -90 dan 90. |
| H006_GEO_LNG_RANGE | geolocation | hard | quarantine | 0 | Longitude harus berada di antara -180 dan 180. |
| H007_ORDER_ID_REQUIRED | orders | hard | quarantine | 0 | order_id wajib terisi. |
| H008_ORDER_ID_UNIQUE | orders | hard | quarantine | 0 | order_id harus unik. |
| H009_ORDER_CUSTOMER_FK | orders | hard | quarantine | 0 | customer_id harus ditemukan pada customers. |
| H010_ITEM_ORDER_FK | order_items | hard | quarantine | 0 | order_id harus ditemukan pada orders. |
| H011_ITEM_PRODUCT_FK | order_items | hard | quarantine | 0 | product_id harus ditemukan pada products. |
| H012_ITEM_SELLER_FK | order_items | hard | quarantine | 0 | seller_id harus ditemukan pada sellers. |
| H013_ITEM_PRICE_NONNEGATIVE | order_items | hard | quarantine | 0 | price tidak boleh negatif. |
| H014_ITEM_FREIGHT_NONNEGATIVE | order_items | hard | quarantine | 0 | freight_value tidak boleh negatif. |
| H015_PAYMENT_ORDER_FK | order_payments | hard | quarantine | 0 | order_id pembayaran harus ditemukan pada orders. |
| H016_PAYMENT_VALUE_NONNEGATIVE | order_payments | hard | quarantine | 0 | payment_value tidak boleh negatif. |
| H017_REVIEW_ORDER_FK | order_reviews | hard | quarantine | 0 | order_id review harus ditemukan pada orders. |
| H018_REVIEW_SCORE_RANGE | order_reviews | hard | quarantine | 0 | review_score harus berada di antara 1 dan 5. |
| H019_PRODUCT_ID_REQUIRED | products | hard | quarantine | 0 | product_id wajib terisi. |
| H020_PRODUCT_ID_UNIQUE | products | hard | quarantine | 0 | product_id harus unik. |
| H021_SELLER_ID_REQUIRED | sellers | hard | quarantine | 0 | seller_id wajib terisi. |
| H022_SELLER_ID_UNIQUE | sellers | hard | quarantine | 0 | seller_id harus unik. |
| H023_SELLER_ZIP_FORMAT | sellers | hard | quarantine | 0 | Kode pos penjual harus berupa 5 digit teks. |
| H024_TRANSLATION_CATEGORY_REQUIRED | category_translation | hard | quarantine | 0 | Nama kategori sumber pada tabel terjemahan wajib terisi. |
| S001_CUSTOMER_STATE_PRESENT | customers | soft | warn | 0 | Catat pelanggan yang tidak memiliki kode state. |
| S002_GEO_COORDINATE_DUPLICATE | geolocation | soft | warn | 261831 | Hitung koordinat atau baris geolokasi duplikat. |
| S003_ORDER_APPROVAL_MISSING | orders | soft | warn | 160 | Catat order yang belum memiliki waktu persetujuan. |
| S004_ORDER_DELIVERY_CHRONOLOGY | orders | soft | warn | 189 | Periksa urutan waktu purchase, carrier, dan delivery. |
| S005_ITEM_SHIPPING_LIMIT | order_items | soft | warn | 0 | Periksa shipping limit yang lebih awal dari purchase. |
| S006_PAYMENT_INSTALLMENTS | order_payments | soft | warn | 2 | Catat nilai cicilan yang tidak positif. |
| S007_REVIEW_COMMENT_EMPTY | order_reviews | soft | warn | 56537 | Hitung review tanpa komentar; tidak mengarantina baris. |
| S008_PRODUCT_DIMENSIONS | products | soft | warn | 4 | Catat dimensi atau berat produk yang tidak positif. |
| H_REQUIRED_CUSTOMER_ID | customers | hard | quarantine | 0 | customer_id wajib terisi. |
| H_REQUIRED_CUSTOMER_UNIQUE_ID | customers | hard | quarantine | 0 | customer_unique_id wajib terisi. |
| H_REQUIRED_GEOLOCATION_ZIP_CODE_PREFIX | geolocation | hard | quarantine | 0 | geolocation_zip_code_prefix wajib terisi. |
| H_REQUIRED_GEOLOCATION_LAT | geolocation | hard | quarantine | 0 | geolocation_lat wajib terisi. |
| H_REQUIRED_GEOLOCATION_LNG | geolocation | hard | quarantine | 0 | geolocation_lng wajib terisi. |
| H_REQUIRED_ORDER_ID | orders | hard | quarantine | 0 | order_id wajib terisi. |
| H_REQUIRED_CUSTOMER_ID | orders | hard | quarantine | 0 | customer_id wajib terisi. |
| H_REQUIRED_ORDER_STATUS | orders | hard | quarantine | 0 | order_status wajib terisi. |
| H_REQUIRED_ORDER_PURCHASE_TIMESTAMP | orders | hard | quarantine | 0 | order_purchase_timestamp wajib terisi. |
| H_REQUIRED_ORDER_ID | order_items | hard | quarantine | 0 | order_id wajib terisi. |
| H_REQUIRED_ORDER_ITEM_ID | order_items | hard | quarantine | 0 | order_item_id wajib terisi. |
| H_REQUIRED_PRODUCT_ID | order_items | hard | quarantine | 0 | product_id wajib terisi. |
| H_REQUIRED_SELLER_ID | order_items | hard | quarantine | 0 | seller_id wajib terisi. |
| H_REQUIRED_SHIPPING_LIMIT_DATE | order_items | hard | quarantine | 0 | shipping_limit_date wajib terisi. |
| H_REQUIRED_PRICE | order_items | hard | quarantine | 0 | price wajib terisi. |
| H_REQUIRED_FREIGHT_VALUE | order_items | hard | quarantine | 0 | freight_value wajib terisi. |
| H_REQUIRED_ORDER_ID | order_payments | hard | quarantine | 0 | order_id wajib terisi. |
| H_REQUIRED_PAYMENT_SEQUENTIAL | order_payments | hard | quarantine | 0 | payment_sequential wajib terisi. |
| H_REQUIRED_PAYMENT_TYPE | order_payments | hard | quarantine | 0 | payment_type wajib terisi. |
| H_REQUIRED_PAYMENT_INSTALLMENTS | order_payments | hard | quarantine | 0 | payment_installments wajib terisi. |
| H_REQUIRED_PAYMENT_VALUE | order_payments | hard | quarantine | 0 | payment_value wajib terisi. |
| H_REQUIRED_REVIEW_ID | order_reviews | hard | quarantine | 0 | review_id wajib terisi. |
| H_REQUIRED_ORDER_ID | order_reviews | hard | quarantine | 0 | order_id wajib terisi. |
| H_REQUIRED_REVIEW_SCORE | order_reviews | hard | quarantine | 0 | review_score wajib terisi. |
| H_REQUIRED_PRODUCT_ID | products | hard | quarantine | 0 | product_id wajib terisi. |
| H_REQUIRED_SELLER_ID | sellers | hard | quarantine | 0 | seller_id wajib terisi. |
| H_REQUIRED_PRODUCT_CATEGORY_NAME | category_translation | hard | quarantine | 0 | product_category_name wajib terisi. |
| H_REQUIRED_PRODUCT_CATEGORY_NAME_ENGLISH | category_translation | hard | quarantine | 0 | product_category_name_english wajib terisi. |
| H_PRIMARY_KEY_UNIQUE_CUSTOMERS | customers | hard | quarantine | 0 | Primary key ['customer_id'] harus unik. |
| H_PRIMARY_KEY_UNIQUE_ORDERS | orders | hard | quarantine | 0 | Primary key ['order_id'] harus unik. |
| H_PRIMARY_KEY_UNIQUE_ORDER_ITEMS | order_items | hard | quarantine | 0 | Primary key ['order_id', 'order_item_id'] harus unik. |
| H_PRIMARY_KEY_UNIQUE_ORDER_PAYMENTS | order_payments | hard | quarantine | 0 | Primary key ['order_id', 'payment_sequential'] harus unik. |
| H_PRIMARY_KEY_UNIQUE_PRODUCTS | products | hard | quarantine | 0 | Primary key ['product_id'] harus unik. |
| H_PRIMARY_KEY_UNIQUE_SELLERS | sellers | hard | quarantine | 0 | Primary key ['seller_id'] harus unik. |
| H_PRIMARY_KEY_UNIQUE_CATEGORY_TRANSLATION | category_translation | hard | quarantine | 0 | Primary key ['product_category_name'] harus unik. |
| H_TYPE_GEOLOCATION_LAT | geolocation | hard | quarantine | 0 | Nilai nonkosong pada geolocation_lat tidak sesuai tipe decimal. |
| H_TYPE_GEOLOCATION_LNG | geolocation | hard | quarantine | 0 | Nilai nonkosong pada geolocation_lng tidak sesuai tipe decimal. |
| H_TYPE_ORDER_PURCHASE_TIMESTAMP | orders | hard | quarantine | 0 | Nilai nonkosong pada order_purchase_timestamp tidak sesuai tipe timestamp. |
| H_TYPE_ORDER_APPROVED_AT | orders | hard | quarantine | 0 | Nilai nonkosong pada order_approved_at tidak sesuai tipe timestamp. |
| H_TYPE_ORDER_DELIVERED_CARRIER_DATE | orders | hard | quarantine | 0 | Nilai nonkosong pada order_delivered_carrier_date tidak sesuai tipe timestamp. |
| H_TYPE_ORDER_DELIVERED_CUSTOMER_DATE | orders | hard | quarantine | 0 | Nilai nonkosong pada order_delivered_customer_date tidak sesuai tipe timestamp. |
| H_TYPE_ORDER_ESTIMATED_DELIVERY_DATE | orders | hard | quarantine | 0 | Nilai nonkosong pada order_estimated_delivery_date tidak sesuai tipe timestamp. |
| H_TYPE_ORDER_ITEM_ID | order_items | hard | quarantine | 0 | Nilai nonkosong pada order_item_id tidak sesuai tipe integer. |
| H_TYPE_SHIPPING_LIMIT_DATE | order_items | hard | quarantine | 0 | Nilai nonkosong pada shipping_limit_date tidak sesuai tipe timestamp. |
| H_TYPE_PRICE | order_items | hard | quarantine | 0 | Nilai nonkosong pada price tidak sesuai tipe decimal. |
| H_TYPE_FREIGHT_VALUE | order_items | hard | quarantine | 0 | Nilai nonkosong pada freight_value tidak sesuai tipe decimal. |
| H_TYPE_PAYMENT_SEQUENTIAL | order_payments | hard | quarantine | 0 | Nilai nonkosong pada payment_sequential tidak sesuai tipe integer. |
| H_TYPE_PAYMENT_INSTALLMENTS | order_payments | hard | quarantine | 0 | Nilai nonkosong pada payment_installments tidak sesuai tipe integer. |
| H_TYPE_PAYMENT_VALUE | order_payments | hard | quarantine | 0 | Nilai nonkosong pada payment_value tidak sesuai tipe decimal. |
| H_TYPE_REVIEW_SCORE | order_reviews | hard | quarantine | 0 | Nilai nonkosong pada review_score tidak sesuai tipe integer. |
| H_TYPE_REVIEW_CREATION_DATE | order_reviews | hard | quarantine | 0 | Nilai nonkosong pada review_creation_date tidak sesuai tipe timestamp. |
| H_TYPE_REVIEW_ANSWER_TIMESTAMP | order_reviews | hard | quarantine | 0 | Nilai nonkosong pada review_answer_timestamp tidak sesuai tipe timestamp. |
| H_TYPE_PRODUCT_NAME_LENGHT | products | hard | quarantine | 0 | Nilai nonkosong pada product_name_lenght tidak sesuai tipe integer. |
| H_TYPE_PRODUCT_DESCRIPTION_LENGHT | products | hard | quarantine | 0 | Nilai nonkosong pada product_description_lenght tidak sesuai tipe integer. |
| H_TYPE_PRODUCT_PHOTOS_QTY | products | hard | quarantine | 0 | Nilai nonkosong pada product_photos_qty tidak sesuai tipe integer. |
| H_TYPE_PRODUCT_WEIGHT_G | products | hard | quarantine | 0 | Nilai nonkosong pada product_weight_g tidak sesuai tipe decimal. |
| H_TYPE_PRODUCT_LENGTH_CM | products | hard | quarantine | 0 | Nilai nonkosong pada product_length_cm tidak sesuai tipe decimal. |
| H_TYPE_PRODUCT_HEIGHT_CM | products | hard | quarantine | 0 | Nilai nonkosong pada product_height_cm tidak sesuai tipe decimal. |
| H_TYPE_PRODUCT_WIDTH_CM | products | hard | quarantine | 0 | Nilai nonkosong pada product_width_cm tidak sesuai tipe decimal. |

## Interpretasi

- Hard rule: pelanggaran mengarantina baris.
- Soft rule: pelanggaran hanya dicatat; baris tetap diterima.
- Karantina unik dihitung per baris, meskipun melanggar beberapa aturan.
- Baris anak yang merujuk ke induk yang dikarantina ikut diperiksa ulang.
- FAIL berarti persentase karantina melampaui ambang.
- PASS+KARANTINA berarti ada baris dikarantina tetapi masih di bawah ambang.
- PASS berarti tidak ada baris yang dikarantina.
- Baris sumber = baris diterima + baris karantina.

Catatan: aturan kontrak dan pemeriksaan tambahan dicatat terpisah. Jumlah pelanggaran per aturan tidak boleh dijumlahkan untuk memperoleh jumlah baris karantina karena satu baris dapat melanggar beberapa aturan.