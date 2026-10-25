# 09 — Keamanan & Privasi

Web ini menyimpan NIK (No. KTP), tanggal lahir, nomor WA, dan bukti transfer.
Perlakukan sesuai prinsip UU Pelindungan Data Pribadi (UU 27/2022): kumpulkan
seperlunya, lindungi, hapus bila tidak diperlukan.

## 1. Enkripsi field

- `apps/core/crypto.py`: `EncryptedTextField` (custom model field) memakai
  `cryptography.fernet.MultiFernet` dengan kunci dari `.env`:
  `FIELD_ENCRYPTION_KEYS` (dipisah koma; kunci pertama untuk enkripsi,
  semua untuk dekripsi → mendukung rotasi kunci).
- Field terenkripsi: `OrderLine.holder_nik`, `Order.refund_account_number`.
- `holder_nik_hash` = HMAC-SHA256(NIK, `NIK_HASH_PEPPER` dari `.env`) untuk
  pencarian duplikat & pencarian admin berdasarkan NIK lengkap.
- `holder_nik_last4` untuk tampilan tersamar.
- **Peringatan di installer & README**: kehilangan `FIELD_ENCRYPTION_KEYS`
  = NIK tidak bisa dibaca lagi. Installer meminta admin menyimpan salinan kunci.

## 2. Akses data sensitif

- Tampilan default selalu tersamar (`•••• •••• •••• 1234`).
- "Lihat NIK" hanya untuk Owner, dicatat `AuditLog` (`nik.reveal`).
- Ekspor dengan NIK hanya Owner atau link promotor dengan izin Owner; dicatat.
- NIK & rekening tidak pernah ditulis ke log aplikasi, pesan error, URL,
  query string, `localStorage`, atau isi notifikasi.
- Logging: filter khusus yang menyamarkan pola 16 digit di semua log.

## 3. Retensi

Tugas harian `purge_sensitive_data`: untuk event berstatus `SELESAI`,
`DIBATALKAN`, atau `ARSIP` yang `first_show_date` + `sensitive_data_retention_days`
(default 30) sudah lewat:
- Kosongkan `holder_nik` (sisakan `holder_nik_last4`), `holder_birth_date`,
  `refund_account_number` (bila refund sudah selesai).
- Hapus file privat yang sudah tidak diperlukan (screenshot VA, foto gelang).
  Bukti transfer & bukti refund **disimpan** (catatan keuangan) — kecuali
  Owner mengatur lain.
- Catat jumlah yang dihapus di `AuditLog`.

## 4. File upload

- Tipe diizinkan: JPG, PNG, WEBP, HEIC (dikonversi ke JPG bila Pillow
  mendukung; bila tidak, tolak dengan pesan jelas), PDF. Maks **10 MB**.
- Validasi berdasarkan isi (Pillow `verify()` untuk gambar; header `%PDF-`
  untuk PDF), bukan ekstensi saja.
- Gambar disimpan ulang lewat Pillow (buang EXIF/lokasi), lebar maks 2000px.
- Nama file UUID, folder `media/private/<tahun>/<bulan>/`.
- Disajikan lewat view `/berkas/<id>/` yang mengecek: admin login, ATAU
  session lacak pesanan pemilik, ATAU tanda tangan link promotor yang valid.
  Header `Content-Disposition` aman, `X-Content-Type-Options: nosniff`.
- File publik (poster, testimoni yang disetujui) di `media/public/`,
  disajikan lewat view sederhana dengan cache header.

## 5. Autentikasi & otorisasi

- Admin: login Django, validator kata sandi bawaan (min 10 karakter),
  rate limit login 5 gagal / 15 menit per IP+username, sesi 8 jam,
  logout otomatis bila tidak aktif 2 jam.
- Decorator/mixin `owner_required`, `admin_required` di semua view `/kelola/`.
- Customer: akses lacak via session (setelah kode + WA cocok) atau token
  bertanda tangan. Setiap view pesanan memastikan izin untuk **kode itu**.
- Halaman `/kelola/sistem/` (Django admin) hanya superuser.

## 6. Rate limit (DatabaseCache)

| Aksi | Batas |
|---|---|
| Masuk lacak | 10 / 15 menit / IP |
| Kirim pesanan | 5 / 10 menit / IP |
| Upload bukti | 10 / jam / pesanan |
| Login admin | 5 gagal / 15 menit |
| Unduh promotor | 30 / jam / token |

Implementasi helper sendiri di `apps/core/ratelimit.py` (tanpa dependensi baru).
Ambil IP dari `REMOTE_ADDR`, atau `X-Forwarded-For` hanya bila
`TRUSTED_PROXY=1` di `.env`.

## 7. Pengaturan Django produksi

- `DEBUG=False`, `ALLOWED_HOSTS` dan `CSRF_TRUSTED_ORIGINS` dari `.env`.
- `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS='DENY'`,
  `SECURE_REFERRER_POLICY='same-origin'`.
- Bila `HTTPS=1` di `.env`: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
  `SECURE_PROXY_SSL_HEADER`, HSTS.
- Content-Security-Policy sederhana via middleware sendiri: `default-src 'self'`;
  izinkan `img-src 'self' data:`; tanpa skrip eksternal. (Alpine butuh
  `'unsafe-eval'` kecuali memakai build CSP Alpine — pakai **build CSP Alpine**.)
- `python manage.py check --deploy` tanpa peringatan penting (kecuali yang
  terkait HTTPS bila memang HTTP).

## 8. Anti-spam form

Honeypot field, token sekali pakai, rate limit, validasi WA Indonesia
(`^(\+?62|0)8[0-9]{7,12}$`), validasi NIK 16 digit.

## 9. Backup

Tugas harian `backup_db`: `mysqldump` (dari instalasi MariaDB) ke
`backups/dreamtify-YYYYMMDD-HHMM.sql.gz`, simpan 14 terakhir, plus salin
`media/` secara inkremental (robocopy) ke `backups/media/`.
Dokumen `docs/10` berisi cara restore.
