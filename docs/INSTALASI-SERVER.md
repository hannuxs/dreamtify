# Instalasi di Server

Panduan untuk pemilik Dreamtify. Tidak perlu paham pemrograman, cukup bisa membuka folder dan mengedit file teks.

## Ringkasan

```
Salin folder proyek ke server  ->  (opsional) edit .env  ->  klik kanan install.bat  ->  Run as administrator
```

Setelah selesai, web hidup di `http://<IP-server>:8383` dan hidup lagi sendiri setelah server restart.

## Yang dibutuhkan

| Komponen | Keterangan |
|---|---|
| Windows | Server 2019 ke atas, atau Windows 10/11 64-bit |
| Python 3.12 64-bit | Dari python.org, centang "Add python.exe to PATH". Installer juga menawarkan pemasangan otomatis |
| MariaDB 10.11 atau 11.4 | Boleh di server ini atau di server lain |
| Internet | Saat instalasi saja |

## Memahami isi `.env`

`.env` adalah file pengaturan di folder proyek. Bagian database:

| Nama | Artinya | Contoh |
|---|---|---|
| `DB_HOST` | Alamat server MariaDB. `127.0.0.1` berarti server ini sendiri | `192.168.1.20` |
| `DB_PORT` | Port MariaDB | `3309` |
| `DB_USER` | User untuk masuk ke MariaDB | `dreamtify` |
| `DB_PASSWORD` | Sandi user itu | |
| `DB_NAME` | Database **sungguhan**, dipakai `install.bat` dan `prod.bat` | `dreamtify` |
| `DB_NAME_DEV` | Database **coba-coba**, dipakai `dev.bat`. Bisa berisi data demo | `dreamtify_dev` |
| `DB_DRIVER` | Pustaka Python penghubung ke MariaDB. **Biarkan `mysqlclient`.** Installer mengubahnya ke `pymysql` sendiri bila `mysqlclient` gagal dipasang | `mysqlclient` |
| `DB_SSL_CA` | Hanya bila diminta error 2026, lihat "Pemecahan masalah" | |

**Kenapa ada dua nama database?** Agar uji coba tidak pernah menyentuh data pelanggan. Keduanya database terpisah
di server MariaDB yang sama. Di server produksi, yang berperan hanya `DB_NAME`.

Sandi yang berisi spasi atau `#` diapit tanda kutip: `DB_PASSWORD='sandi #1'`. Sandi tidak boleh diawali tanda `$`.

## Database dibuat otomatis

Setiap kali web dinyalakan, sistem mengecek database sesuai `.env`, lalu:

1. membuat database bila belum ada (dengan charset `utf8mb4`),
2. membuat atau melengkapi **semua tabel**,
3. mengisi data awal: pengaturan, FAQ, syarat, template pesan, grup Owner dan Admin.

Jadi setelah mengubah `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, atau `DB_NAME`, cukup nyalakan ulang web:

```
scripts\layanan.ps1 restart
```

**Yang tidak ikut otomatis**: isi data lama (pesanan, event, akun admin). Database baru mulai kosong. Untuk memindahkan
data, lihat "Memindahkan data ke database baru". Akun Owner pertama dibuat dengan `scripts\tugas.bat buat_owner`.

## MariaDB di server lain

Jalankan perintah ini **di server MariaDB**, sekali saja. Ganti `IP-WEB` dengan IP server web dan `SANDI` dengan sandi Anda.

```sql
CREATE USER 'dreamtify'@'IP-WEB' IDENTIFIED BY 'SANDI';
CREATE DATABASE dreamtify CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON dreamtify.* TO 'dreamtify'@'IP-WEB';
FLUSH PRIVILEGES;
```

Pastikan juga di server MariaDB:

- `bind-address` di `my.ini` bukan `127.0.0.1` (pakai IP server, atau `0.0.0.0`),
- firewall membuka port MariaDB **hanya untuk IP server web**.

Lalu isi `.env` di server web:

```ini
DB_HOST=192.168.1.20
DB_PORT=3309
DB_NAME=dreamtify
DB_USER=dreamtify
DB_PASSWORD=SANDI
```

Akses root MariaDB tidak diperlukan dari sisi web. Tabel zona waktu MariaDB juga tidak diperlukan.

**Backup:** program `mariadb-dump` harus ada di server web. Unduh MariaDB versi ZIP dari mariadb.org, ekstrak ke
mana saja, lalu isi `MARIADB_BIN` di `.env` dengan folder `bin`-nya. Installer memperingatkan bila program ini belum ada.

## Langkah instalasi

1. Salin folder proyek ke server, misalnya `C:\dreamtify`.
2. Bila file `.env` sudah Anda siapkan, letakkan di folder itu. Bila belum, installer membuatnya dengan kunci acak.
3. Klik kanan `install.bat`, pilih **Run as administrator**.
4. Jawab pertanyaannya: lokasi MariaDB, IP/domain server, lalu username dan sandi Owner.
5. **Salin file `.env` ke tempat aman** (bukan di server yang sama).

> Tanpa `FIELD_ENCRYPTION_KEYS` di `.env`, NIK dan rekening tidak bisa dibaca lagi walaupun database masih utuh.

Cek dari HP di jaringan yang sama: buka `http://<IP-server>:8383`. Halaman admin ada di `/kelola/`.

Opsi: `-NoService` (tanpa firewall dan tugas terjadwal), `-NonInteractive` (tanpa pertanyaan, untuk update),
`-InstallMariaDB -MariaDBMsi C:\path\mariadb.msi` (pasang MariaDB di server ini).

## Yang berjalan otomatis

| Tugas Windows | Kapan | Fungsi |
|---|---|---|
| Dreamtify Web | Saat server menyala | Menjalankan web, restart sendiri bila mati |
| Dreamtify Berkala | Tiap 15 menit | Batalkan pesanan lewat batas, buat pengingat, tutup tahap |
| Dreamtify Harian | Tiap hari 02.30 | Hapus data sensitif yang lewat retensi, lalu backup |

Melihat status (PowerShell Administrator):

```
scripts\layanan.ps1 status
scripts\layanan.ps1 logs
```

Pilihan lain: `start`, `stop`, `restart`.

## Update aplikasi

Salin kode baru, lalu jalankan `install.bat` lagi. Kunci di `.env` tidak ditimpa, dan tabel baru dibuat otomatis.

## Perintah manual di server

Selalu pakai `scripts\tugas.bat`. Perintah `manage.py` langsung memakai mode dev, jadi menyentuh `DB_NAME_DEV`.

```
scripts\tugas.bat backup_db
scripts\tugas.bat purge_sensitive_data --dry-run
scripts\tugas.bat changepassword nama-admin
```

## Backup dan pemulihan

Backup harian tersimpan di `backups\`: 14 file database terakhir (`dreamtify-YYYYMMDD-HHMM.sql.gz`) dan salinan
`backups\media\`. Salin folder ini berkala ke komputer lain.

Memulihkan database (hentikan web dulu, database tujuan harus sudah ada):

```
scripts\layanan.ps1 stop
powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 backups\dreamtify-20261101-0230.sql.gz
scripts\layanan.ps1 start
```

Salin balik `backups\media\` ke `media\`, dan pakai `.env` yang sama.

### Memindahkan data ke database baru

1. Di web lama: `scripts\tugas.bat backup_db`.
2. Ubah `.env` ke database baru, lalu jalankan `scripts\layanan.ps1 restart` sekali agar database terbentuk.
3. `scripts\layanan.ps1 stop`, jalankan `restore.ps1` seperti di atas, lalu `scripts\layanan.ps1 start`.

## HTTPS (opsional)

Pasang Cloudflare Tunnel yang mengarah ke `http://localhost:8383`, atau IIS sebagai reverse proxy. Setelah itu ubah
`.env`: `HTTPS=1`, `TRUSTED_PROXY=1`, serta `SITE_URL`, `ALLOWED_HOSTS`, dan `CSRF_TRUSTED_ORIGINS` ke domain baru.

## Pemecahan masalah

| Gejala | Penyebab dan solusi |
|---|---|
| "User/sandi ditolak" (1045) | `DB_USER`/`DB_PASSWORD` salah, atau user dibuat untuk IP lain. Cek `CREATE USER` di atas |
| "menolak alamat komputer ini" (1130) | Buat user untuk IP server web |
| "tidak bisa dihubungi" (2002, 2003) | Cek `DB_HOST`, `DB_PORT`, firewall, `bind-address`, dan layanan MariaDB |
| "Database belum ada dan user tidak boleh membuatnya" | Jalankan `CREATE DATABASE` dan `GRANT` di server MariaDB |
| Sertifikat tidak terverifikasi (2026) | Lihat bagian di bawah |
| Port 8383 dipakai | Web sudah berjalan, atau ubah `WEB_PORT` di `.env` |
| Halaman "Bad Request (400)" | Alamat belum ada di `ALLOWED_HOSTS` di `.env` |
| Gagal saat kirim form (CSRF) | Tambahkan alamat ke `CSRF_TRUSTED_ORIGINS` |
| Backup gagal: tidak menemukan `mariadb-dump` | Isi `MARIADB_BIN` di `.env` |
| Tampilan berantakan | Jalankan ulang `install.bat` |

### Error 2026 pada backup

Klien MariaDB 11.4 memverifikasi sertifikat server saat terhubung lewat jaringan. Bila server memakai sertifikat
buatan sendiri, `mariadb-dump` berhenti dengan error 2026. Pilih salah satu:

1. **Disarankan:** siapkan sertifikat di server MariaDB (`ssl_ca`, `ssl_cert`, `ssl_key`), salin file CA ke server web,
   lalu isi `DB_SSL_CA=C:\dreamtify\ca.pem` di `.env`.
2. Jalankan backup di server MariaDB itu sendiri dengan penjadwal di sana.

Dreamtify sengaja tidak mematikan verifikasi sertifikat, karena koneksi ini membawa data pribadi pelanggan.
