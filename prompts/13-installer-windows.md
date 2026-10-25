# Fase 13 — Installer Windows & Mode Produksi

## Baca dulu
`CLAUDE.md` §3, **`docs/10-instalasi-windows.md` (seluruhnya, teliti)**,
`docs/09-keamanan-privasi.md` §1, §9.

## Tujuan
Di server Windows, **satu perintah** `install.bat` menyiapkan semuanya sampai
web hidup otomatis di port 8383 (dan hidup lagi setelah restart), serta
`prod.bat` menjalankan mode produksi.

## Tugas
1. `install.bat` + `scripts/install.ps1` sesuai `docs/10` §4 (12 langkah),
   termasuk parameter `-InstallMariaDB`, `-MariaDBMsi`, `-NoService`,
   `-NonInteractive`. Idempoten: menjalankan ulang = update (pip, migrate,
   collectstatic, seed_initial, restart task) **tanpa menimpa kunci `.env`**.
2. `prod.bat` + `scripts/prod.ps1` sesuai `docs/10` §6 (cek port, migrate,
   collectstatic, check --deploy, waitress dengan log berotasi; argumen
   `--service` untuk dijalankan Scheduled Task tanpa `pause`).
3. Scheduled Tasks `Dreamtify Web`, `Dreamtify Berkala`, `Dreamtify Harian`
   via cmdlet `Register-ScheduledTask` (akun SYSTEM, restart bila gagal,
   tanpa batas waktu untuk Web).
4. `scripts/layanan.ps1 status|start|stop|restart|logs`.
5. Penanganan error ramah: setiap langkah `[OK]/[LEWATI]/[GAGAL] + solusi`,
   log ke `logs/install-*.log`, keluar dengan kode ≠ 0 bila gagal.
   Kasus wajib ditangani: bukan Administrator, Python tidak ada, MariaDB
   tidak ada / port bukan 3309 / password root salah, `mysqlclient` gagal
   (→ PyMySQL), port 8383 dipakai program lain, tidak ada internet saat pip.
6. Peringatan besar di akhir: **salin `.env` ke tempat aman** (kunci enkripsi).
7. `docs/INSTALASI-SERVER.md` untuk pemilik (bahasa awam, langkah bergambar
   teks): prasyarat, pasang MariaDB port 3309, jalankan `install.bat`,
   cek web, update, backup/restore, HTTPS opsional, pemecahan masalah umum.
8. Validasi statis skrip PowerShell: jalankan `PSScriptAnalyzer` bila tersedia;
   bila lingkungan bukan Windows, minimal pastikan sintaks valid dengan
   `pwsh -NoProfile -Command "[ScriptBlock]::Create((Get-Content ... -Raw))"`
   bila `pwsh` ada, dan catat di PROGRESS bahwa uji nyata perlu di Windows.

## Selesai bila
Di Windows bersih (VM) yang sudah ada Python & MariaDB 3309:
`install.bat` (Run as administrator) → web hidup di `http://<IP>:8383`,
restart Windows → web hidup lagi, task berkala & harian terdaftar, menjalankan
`install.bat` kedua kali tidak merusak apa pun.

## Cara saya mengecek
1. Salin folder proyek ke server/VM Windows.
2. Klik kanan `install.bat` → *Run as administrator* → ikuti pertanyaan.
3. Buka `http://<IP-server>:8383` dari HP di jaringan yang sama.
4. Restart server → buka lagi.
5. Buka *Task Scheduler* → lihat 3 task "Dreamtify".

## Penutup
Tes, `PROGRESS.md`, ringkasan. Jangan memulai fase 14.
