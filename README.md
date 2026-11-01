# Dreamtify

Web jasa war dan jastip tiket konser: halaman customer, dashboard admin, dan link promotor dalam satu aplikasi.

| | |
|---|---|
| Stack | Python 3.12, Django 5.2, MariaDB, waitress, HTMX + Alpine.js |
| Port web | 8383 |
| OS | Windows |

## Menjalankan

| Perintah | Fungsi |
|---|---|
| `install.bat` | Instalasi produksi (klik kanan, Run as administrator). Aman diulang untuk update |
| `prod.bat` | Mode produksi |
| `dev.bat` | Mode pengembangan di `http://localhost:8383` |
| `dev.bat seed` | Mode pengembangan dengan data demo |

Database dan semua tabel dibuat otomatis sesuai `.env` setiap web dinyalakan. MariaDB boleh di server lain.

Tes: `.venv\Scripts\python -m pytest`

## Dokumen

| File | Isi |
|---|---|
| [docs/INSTALASI-SERVER.md](docs/INSTALASI-SERVER.md) | Instalasi, arti isi `.env`, MariaDB di server lain, backup, pemecahan masalah |
| [docs/PANDUAN-ADMIN.md](docs/PANDUAN-ADMIN.md) | Pemakaian sehari-hari untuk pemilik dan admin |
| [CLAUDE.md](CLAUDE.md) | Aturan proyek dan peta dokumen spesifikasi |
| [PROGRESS.md](PROGRESS.md) | Status, hasil uji, keputusan yang perlu dikonfirmasi |
