# Fase 02 — Model Data & Logika Inti

## Baca dulu
`CLAUDE.md`, `ASUMSI-DAN-KEPUTUSAN.md`, **`docs/02-aturan-bisnis.md`
(seluruhnya, teliti)**, `docs/03-database.md`, `docs/09-keamanan-privasi.md` §1.

## Tujuan
Semua model database + lapisan `services/` (harga, status, penyelesaian,
kuota, kode) lengkap dengan tes. Belum ada halaman.

## Tugas
1. Enum di `apps/core/enums.py` (atau per app) sebagai `TextChoices` dengan
   nilai persis `docs/02` §2 dan label Indonesia.
2. `apps/core/crypto.py`: `EncryptedTextField` (MultiFernet dari
   `FIELD_ENCRYPTION_KEYS`) dan `nik_hash()` (HMAC + `NIK_HASH_PEPPER`).
3. Model semua app sesuai `docs/03` (core, events, orders, notifications,
   testimonials), termasuk index, constraint unik, `TimeStampedModel`.
   Constraint tambahan: kategori utama/cadangan berbeda (validasi di
   `clean()` + service), `quantity` 1–4, uang ≥ 0 kecuali yang memang bisa
   negatif.
4. Migrasi awal. Pastikan berjalan di MariaDB (utf8mb4, panjang index aman).
5. `apps/orders/services/`:
   - `codes.py` — generator `DRM-XXXXXX` unik (retry bila bentrok).
   - `pricing.py` — §4.1 (snapshot per baris & total), dipakai juga untuk
     pratinjau form (fungsi murni menerima data mentah, tidak wajib model tersimpan).
   - `quota.py` — §6 dengan `select_for_update`.
   - `settlement.py` — §4.3 & §4.4: `final_due(order)`, `balance(order)`,
     `cancellation_preview(order, reason)` (untuk dialog batal).
   - `transitions.py` — mesin status §5: satu fungsi per aksi
     (`create_order`, `submit_payment`, `verify_payment`, `reject_payment`,
     `promote_from_waitlist`, `release_slot`, `cancel_by_customer`,
     `cancel_by_admin`, `start_war`, `set_slot_result`, `finish_war`,
     `set_fulfillment`, `record_refund`, `refresh_completion`), masing-masing
     di dalam `transaction.atomic`, menulis `OrderTimeline` + `AuditLog`
     dan memanggil `notifications.services.enqueue()` (buat versi sederhana
     dulu; template lengkap di fase 09). Transisi tidak sah →
     `InvalidTransition`.
   - `orders/selectors.py` — query baca yang efisien (prefetch) untuk dipakai view.
6. `apps/core/money.py` — format `Rp 1.250.000`; template filter `rupiah`.
   `apps/core/phone.py` — normalisasi & validasi WA Indonesia.
7. Management command `seed_initial` (idempoten): SiteSetting, rekening dari
   `docs/referensi/form-jaswar-jastip.md`, grup Owner/Admin beserta
   permission, FAQ awal (`docs/04` §7), template pesan placeholder.
8. **Tes** (`tests/`): semua butir tabel `docs/11` §1 yang terkait harga,
   status, kuota, pembatalan, penyelesaian, enkripsi. **Enam contoh
   `docs/02` §4.5 wajib persis.** Gunakan factory sederhana.

## Jangan
- Jangan menaruh rumus di model/view/template; semuanya di `services/`.
- Jangan memakai float untuk uang.

## Selesai bila
- `migrate` bersih di MariaDB; `seed_initial` bisa dijalankan dua kali tanpa duplikat.
- Semua tes lulus, termasuk 6 contoh harga dan tes kuota bersamaan.
- Django admin bawaan di `/kelola/sistem/` (superuser) menampilkan semua model
  (pendaftaran admin sederhana, NIK tersamar).

## Cara saya mengecek
1. `dev.bat`, lalu di terminal lain:
   `.venv\Scripts\python manage.py createsuperuser`.
2. Buka `http://localhost:8383/kelola/sistem/` dan lihat tabel-tabelnya.
3. Minta Claude Code menunjukkan hasil `pytest` dan tabel ringkas 6 contoh harga.

## Penutup
Jalankan tes, perbarui `PROGRESS.md`, catat asumsi baru di "Pertanyaan
terbuka". Jangan memulai fase 03.
