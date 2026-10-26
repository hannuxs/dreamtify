# PROGRESS.md

Diperbarui oleh Claude Code di akhir setiap fase. Jangan dihapus.

## Status fase

| No | Fase | Status | Tanggal | Catatan |
|---|---|---|---|---|
| 00 | Pemanasan | ✅ selesai | 2026-10-25 | 5 keputusan dicatat di `ASUMSI-DAN-KEPUTUSAN.md` §D; MariaDB 11.4 dipasang |
| 01 | Fondasi proyek | ✅ selesai | 2026-10-26 | Django 5.2 + MariaDB 3309 + `dev.bat`, komponen dasar, 39 tes lulus |
| 02 | Model data | ✅ selesai | 2026-10-26 | Semua model + services (harga, status, kuota, penyelesaian), seed, admin; 131 tes lulus |
| 03 | Pengaturan & event | ⬜ belum | | |
| 04 | Form pesanan | ⬜ belum | | |
| 05 | Lacak & pembayaran | ⬜ belum | | |
| 06 | Verifikasi & waiting list | ⬜ belum | | |
| 07 | Mode war & hasil | ⬜ belum | | |
| 08 | Penyelesaian (refund, gelang, e-tiket) | ⬜ belum | | |
| 09 | Kabar WA | ⬜ belum | | |
| 10 | Rekap & ekspor promotor | ⬜ belum | | |
| 11 | Testimoni, beranda, FAQ | ⬜ belum | | |
| 12 | Keamanan & tugas harian | ⬜ belum | | |
| 13 | Installer Windows | ⬜ belum | | |
| 14 | Uji akhir & serah terima | ⬜ belum | | |

Legenda: ⬜ belum · 🟡 sedang · ✅ selesai · ⚠️ selesai dengan catatan

## Hasil tes terakhir

- **2026-10-26, fase 02** — `.venv\Scripts\python -m pytest` di **MariaDB 11.4.13**:
  **131 lulus, 0 gagal** (±15 detik). Termasuk 6 contoh wajib `docs/02` §4.5 (persis),
  setiap baris tabel pembatalan §4.4, verifikasi kurang/pas/lebih/sekaligus, undo Mode War,
  enkripsi + rotasi kunci, dan tes kuota bersamaan (2 thread, sisa kuota 1).
  Tes kuota dibuktikan bermakna: tanpa `select_for_update` tes itu **gagal** (keduanya dapat slot).
- `makemigrations --check`: bersih. `seed_initial` dua kali: tanpa duplikat.

- **2026-10-26, fase 01** — `.venv\Scripts\python -m pytest` di **MariaDB 11.4.13**
  (DB tes `test_dreamtify_dev`): **39 lulus, 0 gagal**.
- `manage.py check` (dev): bersih. `check --deploy` (prod): hanya 4 peringatan
  HTTPS (W004/W008/W012/W016) — wajar karena `HTTPS=0`; otomatis hilang saat `HTTPS=1`.
- `collectstatic` prod (whitenoise manifest): 156 file, sukses.
- Cek visual (Edge headless + emulasi perangkat) di 360px & 1366px: beranda,
  `/_komponen/`, kerangka dashboard, 404, 500 — tanpa scroll horizontal.
  Interaksi diuji: laci menu, modal, toast, tombol salin (klik asli).

## Lingkungan pengembangan

| Item | Nilai |
|---|---|
| OS | Windows 10 Pro 22H2 64-bit |
| Python | 3.12.10 (`py -3.12`) |
| MariaDB | 11.4.13, layanan `MariaDB`, port 3309, `C:\Program Files\MariaDB 11.4` (dipasang 2026-10-25) |
| Password root MariaDB | file `%USERPROFILE%\dreamtify-mariadb-root.txt` (di luar proyek) — **pindahkan ke pengelola kata sandi lalu hapus file** |
| XAMPP | MariaDB 10.4 (layanan `mysql`, port 3306) tetap ada, **tidak dipakai** (terlalu lama untuk Django 5.2) |
| Git | repo di-init di `main` |

## Pertanyaan terbuka

(hal ambigu yang diputuskan sementara dengan `# ASUMSI:` — pemilik perlu mengonfirmasi)

**Fase 02**

6. **Snapshot harga per pesanan** (`Order.pricing_snapshot`): seluruh matriks fee, harga &
   tier semua kategori, booking slot, dan early booking disimpan saat pesanan dibuat. Hasil war
   (termasuk kategori "Lainnya" di luar pilihan) dihitung dari snapshot ini — perubahan harga
   event tidak mengubah pesanan lama (`docs/02` §4.1). "Hitung ulang" (fase 06) memperbaruinya.
7. **Pembatalan tidak pernah membuat customer berutang**: semua rumus §4.4 dibatasi
   `min(dibayar, …)`. Contoh: fee baru dibayar sebagian lalu batal → yang hangus = yang sudah dibayar.
8. **Batal oleh customer saat bukti masih dicek** → `HANGUS` (bukan `DIBATALKAN`). Bila bukti itu
   kemudian ditolak, yang hangus tetap `min(dibayar=0, …) = 0`; bila diterima, fee hangus sesuai aturan.
9. **Kuota semua-atau-tidak**: pesanan 3 tiket saat sisa 2 masuk waiting list utuh (tidak dipecah).
10. **Saldo saat war berlangsung**: tiket yang belum ada hasilnya dihitung seperti sebelum war
    (fee awal + harga dasar), jadi saldo baru "final" setelah semua tiket terisi.
11. **Admin boleh mencatat pembayaran tanpa bukti** (mis. customer kirim lewat WA); customer wajib upload bukti.
12. **Penyerahan hanya maju** (Menunggu → Ditukar → Siap → Diserahkan); status yang sama boleh
    diulang untuk memperbarui detail (mis. no. resi). Dari "Menunggu" boleh langsung lompat ke "Siap diserahkan".
13. **Batas fee setelah bukti ditolak** diperpanjang ke `sekarang + 6 jam` (maks. `war − 2 jam`) — D3(b).

1. Keputusan D1–D5 di `ASUMSI-DAN-KEPUTUSAN.md` §D sudah disetujui secara umum
   ("pakai usulan yang masuk akal"); D2 (early booking hangus) paling layak dicek ulang.
2. Penyamar log (`apps/core/log_filters.py`) menyamarkan **NIK 16 digit** (boleh
   dengan spasi/titik/strip) **dan semua deret ≥10 digit** (nomor WA, rekening).
   Hanya 4 digit terakhir yang tersisa. Lebih ketat dari `docs/09`, sengaja.
3. Menu header publik memakai path tetap (`/lacak/`, `/testimoni/`, `/faq/`, …)
   yang baru dibangun di fase 04–11; sementara ini menuju 404. Diganti `{% url %}` saat halamannya ada.
4. Menu sidebar dashboard ditulis statis dengan label "segera"; dijadikan data-driven + cek peran di fase 03.
5. Favicon: bagian awan dari logo (dipotong dari atas tulisan, sudut bawah dibulatkan)
   di atas ubin navy — awan pucat tidak terbaca di tab browser bila latarnya transparan.

## Dependensi tambahan

Tidak ada. Semua paket sesuai `CLAUDE.md` §2 (versi di-pin di `requirements*.txt`):
Django 5.2.18, mysqlclient 2.3.0, PyMySQL 1.2.3, waitress 3.0.2, whitenoise 6.12.0,
django-environ 0.14.0, openpyxl 3.1.5, Pillow 13.0.0, cryptography 50.0.2;
dev: pytest 9.1.1, pytest-django 4.14.0, freezegun 1.5.5.
Vendor JS: htmx 2.0.11, `@alpinejs/csp` 3.17.4. Font: Fredoka & Nunito (variable, latin + latin-ext, OFL).

## Catatan untuk fase berikutnya

**Dari fase 02 (penting untuk fase 03+):**

- **API services** (`apps/orders/services/transitions.py`) — semua menerima `actor=Actor`
  (`apps.core.actors`: `Actor.staff(user, ip)`, `Actor.customer(code, ip)`, `Actor.system()`):
  `create_order(phase, buyer=BuyerData, lines=[LineData], payment_method)`, `submit_payment`,
  `verify_payment`, `reject_payment(reason)`, `promote_from_waitlist`, `release_slot`,
  `cancel_by_customer`, `cancel_by_admin(reason)`, `cancel_expired_fee` (untuk `run_periodic`),
  `start_war`, `set_slot_result(result, category, expected_version)` (result=`MENUNGGU` = undo),
  `finish_war(mark_rest_failed)`, `set_fulfillment`, `record_refund`, `refresh_completion`.
  Error: `InvalidTransition` (+ `QuotaFull`), `SlotConflict`, `django ValidationError` dengan kunci
  field seperti `lines.0.holder_nik` (cocok untuk dipetakan ke form fase 04).
- **Angka** untuk tampilan: `settlement.summarize(order)` → `initial_due`, `pelunasan_due`,
  `paid_in`, `refunded`, `pending_in`, `final_due`, `balance`, `refund_due`, `shortfall`,
  `remaining_before_war`. Dialog batal: `settlement.cancellation_preview(order)`.
  Pratinjau form: `pricing.quote_order(PricingContext.for_phase(phase), [LineInput…], method)`.
- **Query**: `apps/orders/selectors.py` (`get_order(code)`, `orders_for_phase`, `pending_payments`) — pakai ini di view (prefetch).
- **Template**: `{% load ui %}` → `|rupiah`, `|status_tone`, `|result_tone`. Brand dari `SiteSetting.load()`.
- **Link lacak**: `links.tracking_url(order)` / `check_tracking_token(code, token)` (30 hari) — dipakai fase 05.
- **Notifikasi**: `notifications.services.enqueue(order, KEY, extra=…, dedupe=…)`; template default
  di `apps/notifications/defaults.py` (20 key, semua sudah berisi `{kode}` & `{link_lacak}`).
  Email baru dibuat barisnya (status PERLU_DIKIRIM) bila diaktifkan — pengiriman di fase 09.
- **Zona waktu MariaDB**: Django butuh tabel zona waktu MariaDB untuk filter tanggal (mis.
  `date_hierarchy`, `__date`). Di Windows diisi dari paket `tzdata` lewat
  `Install-TimeZoneTables` (`scripts/common.ps1`); `dev.bat` menawarkannya otomatis bila
  `manage.py cek_db` menjawab `OK:TZ`. **Fase 13: `install.ps1` wajib memanggilnya juga.**
- `dev.bat` kini juga menjalankan `seed_initial` (idempoten) setelah migrasi.
- Izin: grup **Owner** (semua + `orders.view_full_nik`) dan **Admin** (operasional, tanpa NIK
  penuh & tanpa ubah pengaturan). Cek "Lihat NIK" pakai `user.has_perm("orders.view_full_nik")`.

**Dari fase 01:**

- **Settings**: `config/settings/{base,dev,prod,test}.py`. `test.py` (tambahan) dipakai
  pytest: hasher MD5, email `locmem`, log ke NullHandler; `DJANGO_TEST_SQLITE=1` → SQLite.
- **`dev.bat`** = `scripts/dev.ps1` + `scripts/common.ps1`: venv & pip (dipasang ulang
  otomatis bila `requirements*.txt` berubah), `.env` acak, cek port & login DB
  (`manage.py cek_db`), buat DB+user bila perlu (`$env:MARIADB_ROOT_PASSWORD` untuk
  non-interaktif), migrate, createcachetable, runserver `0.0.0.0:8383`.
  Fungsi `Initialize-AppDatabase`, `New-DotEnvFile`, `Find-MariaDbBin`,
  `Test-TcpPort` siap dipakai ulang oleh `install.ps1` (fase 13).
  File `.ps1` sengaja **ASCII murni** (PowerShell 5.1 membaca file tanpa BOM sebagai ANSI).
- **Komponen**: `templates/components/` (button, card, badge, copy_button, modal,
  accordion_item, countdown, stepper, empty_state, toast_host, `_head`). Ikon lewat
  `{% load ui %}{% icon "nama" %}` (sprite `static/img/icons.svg`).
  ⚠️ Parameter lebar penuh tombol bernama `full`, **bukan** `block` (bentrok dengan
  variabel bawaan Django di dalam `{% block %}`).
- **Alpine CSP**: komponen didaftarkan di `static/js/app.js` (`toastHost`, `toastTrigger`,
  `drawer`, `modal`, `copyButton`, `countdown`); atribut template hanya nama properti/metode.
  `app.js` dimuat sebelum Alpine (keduanya `defer`). Script per-halaman yang mendaftar
  komponen Alpine **harus dimuat sebelum** `alpine-csp.min.js`, jadi taruh di `app.js`
  atau tambahkan blok sebelum Alpine di `_head.html`.
- **Toast dari server**: Django messages otomatis jadi toast; respons HTMX bisa memicu
  toast lewat header `HX-Trigger: {"dt:toast": {"message": "...", "tone": "success"}}`.
- **HTMX**: CSRF lewat `hx-headers` di `<body>`; `htmx-config` mematikan eval &
  style indikator inline (persiapan CSP fase 12).
- **Tombol salin** punya fallback `execCommand` karena produksi berjalan di HTTP polos
  (Clipboard API butuh HTTPS).
- **Brand** sementara dari settings (`BRAND_NAME`, `BRAND_TAGLINE`) via
  `apps.core.context_processors.site`; fase 02 pindah ke `SiteSetting`
  (termasuk `admin_whatsapp` — tombol WA di header/404 baru muncul bila terisi).
- Django admin bawaan sudah terpasang di `/kelola/sistem/`; pendaftaran model di fase 02.
- Aset brand dibuat ulang dengan `scripts/tools/make_brand_images.py` (Pillow).
- `/_komponen/`, `/_komponen/dashboard/`, `/_komponen/404/`, `/_komponen/500/`
  hanya aktif saat `DEBUG` (404 di produksi, ada tesnya).
