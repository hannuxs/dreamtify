# CLAUDE.md — Proyek Web Dreamtify

File ini adalah memori proyek. Baca seluruhnya sebelum mengerjakan apa pun.

## 1. Tentang bisnis

**Dreamtify** ("Your Dream is Our Priority") adalah jasa pembelian tiket konser
untuk customer di Indonesia. Ada dua layanan:

- **JASWAR** (jasa war saja): tim Dreamtify ikut war tiket memakai **data
  customer**. Tiket fisik (gelang/wristband) **ditukar sendiri oleh customer**.
- **JASTIP** (terima beres): tim war memakai **data tim Dreamtify**, lalu
  menukarkan tiket sampai mendapat **tiket fisik (gelang)** dan
  menyerahkannya ke customer.

Masalah yang diselesaikan web ini:

1. Selama ini pakai 2 Google Form terpisah (pesanan & pelunasan) per event.
   Membuat form, cek transfer, rekap, dan mengabari customer semuanya manual.
2. Beberapa event bisa berjalan bersamaan (mis. 2 war dalam 1 minggu).
3. Satu orang sering memesan beberapa kategori sekaligus dan/atau
   membelikan orang lain — Google Form tidak mendukung ini.
4. Customer harus dikabari hasil war (dapat/tidak) dan refund; ini lambat.
5. Promotor sering menagih data karena rekap lambat.

## 2. Stack (wajib, jangan diganti)

| Bagian | Pilihan |
|---|---|
| Bahasa | Python 3.12 |
| Framework | Django 5.2 LTS (server-rendered templates) |
| Database | MariaDB (10.11 LTS atau 11.x), **port 3309**, charset `utf8mb4` |
| Driver DB | `mysqlclient` (ada wheel Windows); fallback `PyMySQL` bila gagal |
| Server produksi | `waitress` (Windows-friendly), **port 8383** |
| File statis | `whitenoise` |
| Interaktivitas | HTMX + Alpine.js, **di-vendor** ke `static/js/vendor/` (tanpa CDN) |
| CSS | CSS biasa dengan design token (`static/css/tokens.css`). **Tanpa Node/npm, tanpa build step** |
| Font | Fredoka (judul) + Nunito (isi), di-*self-host* di `static/fonts/` |
| Excel | `openpyxl` |
| Gambar | `Pillow` |
| Enkripsi field | `cryptography` (Fernet) |
| Config | `django-environ`, file `.env` |
| Cache / rate limit | Django `DatabaseCache` (tanpa Redis) |
| Tes | `pytest` + `pytest-django` + `freezegun` (dev saja) |
| OS target | **Windows**. Skrip: `.bat` yang memanggil PowerShell `.ps1` |

Semua versi paket di-*pin* di `requirements.txt`.

## 3. Perintah proyek (kontrak — nama file tidak boleh berubah)

| Perintah | Fungsi |
|---|---|
| `install.bat` | **Satu perintah** instalasi produksi (Run as administrator) |
| `dev.bat` | Menjalankan mode dev: `runserver 0.0.0.0:8383`, DEBUG aktif |
| `prod.bat` | Menjalankan mode produksi: migrate + collectstatic + waitress di 8383 |

Detail lengkap: `docs/10-instalasi-windows.md`.

## 4. Peta dokumen

Baca dokumen yang relevan sebelum mengerjakan sebuah fase:

| File | Isi |
|---|---|
| `ASUMSI-DAN-KEPUTUSAN.md` | Keputusan produk. **Prioritas tertinggi** bila bertentangan dengan dokumen lain |
| `docs/01-prd.md` | Tujuan, pengguna, ruang lingkup |
| `docs/02-aturan-bisnis.md` | Status, alur, **rumus harga/refund** (sumber kebenaran logika) |
| `docs/03-database.md` | Model & field |
| `docs/04-halaman-publik.md` | Halaman customer |
| `docs/05-dashboard-admin.md` | Halaman admin |
| `docs/06-desain-visual.md` | Warna, font, komponen |
| `docs/07-ekspor-promotor.md` | Format Excel promotor (kolom persis) |
| `docs/08-notifikasi-wa.md` | Template pesan WhatsApp |
| `docs/09-keamanan-privasi.md` | Enkripsi NIK, upload, rate limit, retensi |
| `docs/10-instalasi-windows.md` | install/dev/prod, layanan Windows, backup |
| `docs/11-pengujian.md` | Skenario uji & kriteria terima |
| `docs/referensi/` | Isi Google Form lama dan catatan web referensi |

## 5. Struktur kode yang dituju

```
manage.py
config/            settings/{base,dev,prod}.py, urls.py, wsgi.py
apps/
  core/            SiteSetting, BankAccount, FaqItem, AuditLog, util (uang, WA, upload, crypto)
  events/          Event, SalePhase, TicketCategory, FeeRule
  orders/          Order, OrderLine, TicketSlot, Payment, VaNotice, OrderTimeline
    services/      pricing.py, transitions.py, settlement.py, quota.py, codes.py
  notifications/   MessageTemplate, Notification, backends (manual WA, email)
  testimonials/    Testimonial
  exports/         ekspor Excel promotor & rekap
  public/          view halaman customer
  dashboard/       view admin (/kelola/)
templates/         public/, dashboard/, components/, emails/
static/            css/, js/vendor/, fonts/, img/
media/             (gitignore) private/ dan public/
scripts/           common.ps1, install.ps1, dev.ps1, prod.ps1, layanan.ps1, restore.ps1
install.bat dev.bat prod.bat
tests/
logs/ backups/     (gitignore)
```

## 6. Aturan kerja (wajib)

1. **Kerjakan satu prompt/fase per waktu.** Jangan memulai fase berikutnya
   tanpa diminta. Di akhir fase: jalankan tes, perbarui `PROGRESS.md`,
   lalu ringkas apa yang dibuat dan apa yang perlu dicek pengguna.
2. **Logika bisnis hanya di `services/`.** View, form, dan template tidak
   boleh menghitung harga atau mengubah status langsung.
3. **Setiap perubahan status** lewat `orders/services/transitions.py`, yang
   sekaligus: memvalidasi transisi, menulis `OrderTimeline`, menulis
   `AuditLog`, dan membuat `Notification` bila perlu.
4. **Uang selalu integer rupiah** (`PositiveBigIntegerField` / `BigIntegerField`).
   Tidak pernah float. Format tampilan: `Rp 1.250.000`.
5. **Nilai enum (status, jenis layanan, dll.) mengikuti `docs/02` persis.**
   Kode/identifier Python berbahasa Inggris; nilai enum dan semua teks UI
   berbahasa Indonesia.
6. **Data sensitif** (NIK, nomor rekening refund) dienkripsi di database dan
   **tidak pernah** ditulis ke log, pesan error, URL, atau localStorage.
7. **File upload** tidak pernah disajikan langsung dari folder publik bila
   bersifat pribadi (bukti transfer, e-tiket, foto KTP). Lewat view yang
   memeriksa izin.
8. **Mobile-first.** Customer dan admin (saat war) memakai HP.
9. **Windows dulu.** Gunakan `pathlib`, jangan asumsikan perintah Unix.
   Skrip shell selalu `.bat`/`.ps1`.
10. **Zona waktu:** simpan UTC (`USE_TZ=True`), tampilkan `Asia/Jakarta` (WIB)
    sesuai `TIME_ZONE` di `.env`.
11. **Tes untuk logika uang & status wajib ada** sebelum fase dianggap selesai.
12. **Jangan menambah dependensi** di luar daftar di atas tanpa alasan kuat;
    bila perlu, catat alasannya di `PROGRESS.md`.
13. Jika spesifikasi ambigu: pilih opsi paling sederhana yang aman, tandai
    `# ASUMSI:` di kode, dan catat di `PROGRESS.md` bagian "Pertanyaan terbuka".

## 7. Glosarium

| Istilah | Arti |
|---|---|
| War | Momen penjualan tiket resmi dibuka; tim berebut tiket |
| Tahap (phase) | Presale / Gensale, masing-masing punya jadwal war & fee sendiri |
| Kategori (CAT) | Kelas tiket: Duality Package, VIP, CAT 1, dst. |
| Tier fee | VIP atau REGULER (Non-VIP); menentukan besar fee jasa |
| Fee jasa | Biaya jasa Dreamtify per tiket, dibayar penuh di awal |
| Booking slot | Potongan yang tidak dikembalikan bila tiket gagal didapat (default Rp50.000/tiket) |
| Titip bayar admin | Customer menitip uang harga tiket ke Dreamtify; tim yang bayar saat war |
| VA | Virtual Account dari platform tiket; dibayar customer sendiri saat war |
| Pelunasan | Pembayaran harga tiket (untuk titip bayar) |
| Secured | Tiket berhasil didapat |
| Waiting list | Antrian bila kuota slot penuh |
| Pemegang tiket | Orang yang datanya dipakai/menerima tiket (bisa beda dari pemesan) |
| Gelang | Tiket fisik (wristband) hasil penukaran |
| Promotor | Penyelenggara konser; meminta rekap data pembeli |
