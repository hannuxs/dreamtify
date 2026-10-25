# Fase 12 — Audit Keamanan, Retensi Data & Tugas Harian

## Baca dulu
`CLAUDE.md`, `ASUMSI-DAN-KEPUTUSAN.md` (C12), **`docs/09-keamanan-privasi.md`
(seluruhnya)**, `docs/02-aturan-bisnis.md` §7, `docs/10-instalasi-windows.md` §7.

## Tujuan
Memastikan semua kontrol keamanan di `docs/09` benar-benar ada dan teruji,
lalu membuat tugas harian (hapus data sensitif + backup).

## Tugas
1. **Audit menyeluruh** terhadap `docs/09` §1–§8. Buat tabel di
   `PROGRESS.md`: kontrol → lokasi kode → tes → status. Perbaiki semua yang
   kurang.
2. Middleware header keamanan + **CSP** (`default-src 'self'`; pastikan
   Alpine build CSP & HTMX berjalan tanpa `unsafe-inline`/`unsafe-eval`;
   pindahkan sisa inline script/style ke file statis).
3. Pengaturan cookie/HTTPS bergantung `HTTPS` & `TRUSTED_PROXY` di `.env`.
4. Filter log penyamar NIK & rekening diuji (buat log berisi NIK palsu →
   file log tidak memuatnya).
5. Command `purge_sensitive_data` (`docs/09` §3) dengan `--dry-run`.
6. Command `backup_db`: `mysqldump --single-transaction --routines` dari
   `MARIADB_BIN` ke `backups/dreamtify-YYYYMMDD-HHMM.sql.gz`, rotasi
   `BACKUP_KEEP`, salin `media/` dengan `robocopy /MIR` ke `backups/media/`
   (di non-Windows saat tes: lewati robocopy dengan pesan). Kata sandi DB
   dikirim lewat file opsi sementara (bukan argumen baris perintah).
7. Command `run_daily` = `purge_sensitive_data` + `backup_db`, dengan log ke
   `logs/daily.log`. Command `run_periodic` final (semua butir `docs/02` §7).
8. `scripts/restore.ps1 <file.sql.gz>` (ekstrak & impor, konfirmasi dulu).
9. Uji beban ringan: skrip `scripts/loadtest.py` (opsional, hanya dev) yang
   mensimulasikan 50 pesanan/menit ke form; pastikan tidak ada error & kuota
   tidak jebol.
10. Tes: semua di `docs/11` §1 terkait izin, enkripsi, upload, rate limit,
    retensi; CSP header ada; `check --deploy` di settings prod tanpa ERROR.

## Selesai bila
Tabel audit di `PROGRESS.md` semuanya ✅, `run_daily` menghasilkan file backup
yang bisa di-restore, dan tidak ada NIK di folder `logs/`.

## Cara saya mengecek
1. Jalankan `.venv\Scripts\python manage.py run_daily` → lihat folder `backups\`.
2. Jalankan `.venv\Scripts\python manage.py purge_sensitive_data --dry-run`.
3. Baca tabel audit di `PROGRESS.md`.

## Penutup
Tes, `PROGRESS.md`, ringkasan. Jangan memulai fase 13.
