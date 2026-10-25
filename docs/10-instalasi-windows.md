# 10 — Instalasi & Menjalankan di Windows

## 1. Kontrak perintah

| Perintah | Dijalankan | Fungsi |
|---|---|---|
| `install.bat` | sekali di server produksi (klik kanan → *Run as administrator*); aman diulang untuk update | Menyiapkan semuanya sampai web berjalan otomatis |
| `dev.bat` | di mesin pengembangan | Mode dev di `http://localhost:8383` |
| `prod.bat` | manual atau oleh layanan | Mode produksi (waitress) di port 8383 |

Ketiganya `.bat` tipis yang memanggil PowerShell:
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\<nama>.ps1 %*`
lalu `pause` bila dijalankan dengan klik ganda dan terjadi error.
Fungsi bersama (cari Python, baca `.env`, tes koneksi DB, tulis log berwarna)
di `scripts\common.ps1`.

## 2. Prasyarat

| Komponen | Versi | Catatan |
|---|---|---|
| Windows | Server 2019/2022/2025 atau Windows 10/11 64-bit | |
| Python | 3.12.x 64-bit | Installer bisa memasang via `winget` bila belum ada (tanya dulu) |
| MariaDB Server | 10.11 LTS atau 11.4 LTS | Port **3309**, charset UTF8 (`utf8mb4`) |
| Akses internet | saat instalasi | untuk `pip install` |

### MariaDB belum terpasang?

Opsi A (disarankan, manual): unduh MSI dari https://mariadb.org/download/
(pilih versi LTS, Windows x86_64, MSI). Saat instalasi: isi password root,
centang "Use UTF8 as default server's character set", **ubah port ke 3309**,
centang "Install as service".

Opsi B (otomatis): `install.bat -InstallMariaDB -MariaDBMsi C:\path\mariadb.msi`
→ skrip menjalankan
`msiexec /i <msi> PORT=3309 PASSWORD=<diminta> SERVICENAME=MariaDB UTF8=1 /qn`
lalu menunggu layanan berjalan.

Bila MariaDB sudah ada di port lain: ubah `port=3309` di `my.ini`
(folder data MariaDB) lalu restart layanan `MariaDB`.

## 3. File `.env` (dibuat installer dari `.env.example`)

```ini
# Umum
SECRET_KEY=<acak, dibuat installer>
ALLOWED_HOSTS=localhost,127.0.0.1,<ip/domain server>
CSRF_TRUSTED_ORIGINS=http://<ip/domain>:8383
SITE_URL=http://<ip/domain>:8383
TIME_ZONE=Asia/Jakarta
HTTPS=0
TRUSTED_PROXY=0

# Web
WEB_HOST=0.0.0.0
WEB_PORT=8383
WAITRESS_THREADS=8

# Database
DB_HOST=127.0.0.1
DB_PORT=3309
DB_NAME=dreamtify
DB_NAME_DEV=dreamtify_dev
DB_USER=dreamtify
DB_PASSWORD=<acak, dibuat installer>
MARIADB_BIN=<terdeteksi otomatis, mis. C:\Program Files\MariaDB 11.4\bin>

# Keamanan data (SIMPAN SALINANNYA DI TEMPAT AMAN!)
FIELD_ENCRYPTION_KEYS=<Fernet key, dibuat installer>
NIK_HASH_PEPPER=<acak, dibuat installer>

# Email (opsional)
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=1
DEFAULT_FROM_EMAIL=Dreamtify <noreply@domain>

# Backup
BACKUP_DIR=backups
BACKUP_KEEP=14
```

`DJANGO_ENV` **tidak** disimpan di `.env`; di-set oleh `dev.bat` (`dev`)
dan `prod.bat` (`prod`). Mode dev memakai `DB_NAME_DEV`, prod memakai `DB_NAME`.

## 4. `install.bat` — langkah (idempoten)

Parameter opsional: `-InstallMariaDB`, `-MariaDBMsi <path>`, `-NoService`,
`-NonInteractive` (pakai nilai `.env` yang sudah ada, untuk update).

1. Cek berjalan sebagai Administrator; bila tidak, minta ulang dengan elevasi.
2. Cek Python 3.12+ (`py -3.12`, lalu `python`). Tidak ada → tawarkan
   `winget install -e --id Python.Python.3.12` (tanya Y/N), lalu cek ulang.
3. Cari folder `bin` MariaDB (registry/`Program Files`); bila
   `-InstallMariaDB`, pasang (§2). Tes port 3309 terbuka.
4. Buat `.venv` bila belum ada; `pip install --upgrade pip`;
   `pip install -r requirements.txt`. Gagal `mysqlclient` → coba
   `PyMySQL` (sudah ada di requirements sebagai cadangan) dan set
   `DB_DRIVER=pymysql` di `.env`.
5. Buat `.env` bila belum ada: generate `SECRET_KEY`, `DB_PASSWORD`,
   `FIELD_ENCRYPTION_KEYS`, `NIK_HASH_PEPPER`; tanya IP/domain server
   (default: IP lokal pertama). Bila `.env` sudah ada: **jangan menimpa kunci**.
6. Database: minta password root MariaDB (sekali, tidak disimpan) →
   `CREATE DATABASE IF NOT EXISTS dreamtify CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`
   (+ `dreamtify_dev`), buat user `dreamtify`@`localhost` & `127.0.0.1`,
   `GRANT ALL` pada kedua DB dan `test_dreamtify%` (untuk tes). Lewati bila
   koneksi dengan user aplikasi sudah berhasil.
7. `manage.py migrate`, `createcachetable`, `collectstatic --noinput`,
   `seed_initial` (SiteSetting, rekening contoh, FAQ, template pesan, grup
   Owner/Admin — idempoten).
8. Bila belum ada user Owner: tanya username & password → buat superuser +
   grup Owner.
9. Firewall: `New-NetFirewallRule` inbound TCP 8383 (nama "Dreamtify Web 8383"),
   lewati bila sudah ada.
10. Kecuali `-NoService`, daftarkan **Scheduled Tasks** (lewati/ perbarui bila ada):
    - `Dreamtify Web` — pemicu: saat sistem menyala; akun SYSTEM; jalankan
      `prod.bat --service`; restart bila gagal (tiap 1 menit, 999 kali);
      tanpa batas waktu eksekusi. Langsung dijalankan setelah dibuat.
    - `Dreamtify Berkala` — tiap 15 menit: `manage.py run_periodic`.
    - `Dreamtify Harian` — tiap hari 02:30: `manage.py run_daily`
      (hapus data sensitif + backup).
11. Tes `http://127.0.0.1:8383/sehat/` (endpoint health check yang mengecek DB)
    sampai 60 detik.
12. Ringkasan akhir: URL web & admin, lokasi `.env`, **peringatan simpan
    salinan `.env`** (kunci enkripsi), lokasi log, cara stop/start.

Semua langkah mencetak `[OK]`, `[LEWATI]`, atau `[GAGAL] <apa yang harus
dilakukan>`. Log lengkap ke `logs\install-YYYYMMDD-HHmm.log`.

## 5. `dev.bat`

1. Set `DJANGO_ENV=dev`.
2. Bila `.venv` belum ada: buat + `pip install -r requirements-dev.txt`.
   Bila `.env` belum ada: salin dari `.env.example` dengan nilai dev acak.
3. Tes koneksi MariaDB 3309; gagal → pesan jelas.
4. `manage.py migrate` (otomatis), lalu
   `manage.py runserver 0.0.0.0:8383`.
5. Opsi: `dev.bat seed` menjalankan `seed_demo` (event contoh, pesanan contoh
   di berbagai status, testimoni) sebelum menjalankan server.

## 6. `prod.bat`

1. Set `DJANGO_ENV=prod`. Pastikan `.venv` & `.env` ada (bila tidak →
   suruh jalankan `install.bat`).
2. Cek port 8383 belum dipakai; bila dipakai oleh task `Dreamtify Web`,
   beri tahu (dan keluar) kecuali argumen `--service`.
3. `manage.py migrate --noinput`, `collectstatic --noinput`,
   `check --deploy --fail-level ERROR`.
4. `waitress-serve --host=%WEB_HOST% --port=8383 --threads=%WAITRESS_THREADS%
   --url-scheme=http config.wsgi:application`
   dengan log ke `logs\web.log` (rotasi harian, simpan 14 hari).

## 7. Operasional

Skrip bantu opsional `scripts\layanan.ps1 status|start|stop|restart|logs`
(membungkus Scheduled Task `Dreamtify Web`).

**Update aplikasi**: salin kode baru (atau `git pull`), lalu jalankan lagi
`install.bat` (otomatis: pip, migrate, collectstatic, restart task).

**Restore backup**:
```
"<MARIADB_BIN>\mysql.exe" -h 127.0.0.1 -P 3309 -u root -p dreamtify < backups\dreamtify-YYYYMMDD-HHMM.sql
```
(ekstrak `.gz` dulu; skrip `scripts\restore.ps1 <file>` menangani ini.)
Salin balik `backups\media\` ke `media\`. `.env` harus sama (kunci enkripsi).

**HTTPS (opsional, di luar aplikasi)**: Cloudflare Tunnel (`cloudflared`)
mengarah ke `http://localhost:8383`, atau IIS + URL Rewrite/ARR sebagai reverse
proxy. Setelah HTTPS aktif: set `HTTPS=1`, `TRUSTED_PROXY=1`, perbarui
`SITE_URL` dan `CSRF_TRUSTED_ORIGINS`.

## 8. `requirements.txt` (di-pin saat fase 01)

Django 5.2.x, mysqlclient, PyMySQL, waitress, whitenoise, django-environ,
openpyxl, Pillow, cryptography.
`requirements-dev.txt` = `-r requirements.txt` + pytest, pytest-django,
factory-boy (opsional), freezegun.
