# Fase 01 — Fondasi Proyek

## Baca dulu
`CLAUDE.md` (seluruhnya), `ASUMSI-DAN-KEPUTUSAN.md`, `docs/01-prd.md`,
`docs/06-desain-visual.md`, `docs/10-instalasi-windows.md` §1, §3, §5, §8.

## Tujuan
Kerangka Django berjalan di Windows dengan MariaDB port 3309, dibuka lewat
`dev.bat` di port 8383, dengan tampilan dasar bermerek Dreamtify.

## Tugas
1. **Rencana dulu.** Sebelum menulis kode, tampilkan rencana singkat
   (struktur folder, paket & versi yang akan di-pin) lalu lanjutkan.
2. Buat proyek Django 5.2 LTS sesuai struktur di `CLAUDE.md` §5:
   `config/settings/{base,dev,prod}.py`, `apps/` (buat semua app kosong:
   core, events, orders, notifications, testimonials, exports, public,
   dashboard), `templates/`, `static/`, `scripts/`, `tests/`.
3. Settings membaca `.env` (django-environ). `DJANGO_ENV` (dev/prod) memilih
   modul settings dan nama DB (`DB_NAME_DEV` / `DB_NAME`). `TIME_ZONE` dari
   `.env`, `LANGUAGE_CODE='id'`, `USE_TZ=True`. Logging ke `logs/` dengan
   filter penyamar 16 digit (`docs/09` §2). `DatabaseCache`.
4. Driver DB: `mysqlclient`; bila `DB_DRIVER=pymysql` di `.env`, pakai
   `pymysql.install_as_MySQLdb()`. Opsi `init_command` mode SQL ketat,
   charset `utf8mb4`.
5. `requirements.txt` & `requirements-dev.txt` dengan versi di-pin
   (`docs/10` §8). `.env.example` lengkap. `.gitignore`
   (`.env`, `.venv`, `media/`, `logs/`, `backups/`, `staticfiles/`).
6. `dev.bat` + `scripts/dev.ps1` + `scripts/common.ps1` sesuai `docs/10` §5
   (tanpa `seed` dulu — cukup terima argumennya dan beri pesan "tersedia di
   fase 11"). `install.bat` dan `prod.bat` **belum** dibuat (fase 13).
7. Frontend dasar:
   - `static/css/tokens.css` (semua token `docs/06` §1), `base.css`
     (reset, tipografi, utilitas tata letak), `components.css`.
   - Unduh & self-host font Fredoka + Nunito (`.woff2` + lisensi OFL) ke
     `static/fonts/`. Bila tidak ada akses internet, gunakan fallback
     `ui-rounded, system-ui` dan catat di PROGRESS.
   - Vendor HTMX dan **Alpine.js build CSP** (`@alpinejs/csp`) ke
     `static/js/vendor/`. Komponen Alpine didaftarkan dengan `Alpine.data()`
     di `static/js/app.js` (tidak ada ekspresi JS inline di atribut).
   - Salin `assets/logo-dreamtify.png` → `static/img/`. Buat favicon dari logo
     (Pillow, 32/180/512 px).
   - Buat SVG maskot awan `cloud-happy.svg`, `cloud-sleep.svg`,
     `cloud-sad.svg` (gaya senada logo, buatan sendiri).
   - Template `base_public.html` (header, laci menu HP, footer) dan
     `base_dashboard.html` (kerangka sidebar/bottom-nav, belum ada isi).
   - Halaman sementara `/` ("Segera hadir" dengan logo & maskot) dan
     halaman 404/500 bergaya brand.
8. Komponen template awal di `templates/components/`: tombol (4 varian),
   kartu, badge, toast, modal, accordion, tombol salin. Buat halaman dev-only
   `/_komponen/` (hanya saat DEBUG) yang menampilkan semuanya untuk dicek.
9. Endpoint `/sehat/` → JSON `{"status":"ok","db":true}` (cek koneksi DB).
10. pytest + pytest-django terpasang; satu tes untuk `/sehat/` dan satu tes
    bahwa halaman `/` merender logo.

## Jangan
- Jangan memakai Node/npm, Tailwind CDN, atau CDN apa pun saat runtime.
- Jangan membuat model bisnis dulu (fase 02).

## Selesai bila
- `dev.bat` di Windows membuka `http://localhost:8383` menampilkan halaman
  "Segera hadir" bermerek Dreamtify.
- `/_komponen/` menampilkan semua komponen dengan warna & font yang benar.
- `/sehat/` mengembalikan `db: true` dengan MariaDB port 3309.
- Tes lulus.

## Cara saya mengecek
1. Jalankan `dev.bat` → buka `http://localhost:8383`.
2. Buka `http://localhost:8383/_komponen/` di laptop dan mode HP (F12 →
   ikon HP).
3. Buka `http://localhost:8383/sehat/`.

## Penutup
Jalankan tes, perbarui `PROGRESS.md` (fase 01), ringkas hasil & hal yang
perlu saya cek. Jangan memulai fase 02.
