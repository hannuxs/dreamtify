# 07 — Ekspor Format Promotor

Promotor meminta data dengan **format kolom Google Form jaswar/jastip lama**
(lihat `docs/referensi/form-jaswar-jastip.md`). Karena satu `OrderLine` setara
satu isian form lama, **satu baris Excel = satu OrderLine**.

Definisikan format di **satu tempat**: `apps/exports/promotor_format.py`
berupa daftar `(judul_kolom, fungsi_pengambil)`, agar mudah diubah bila
promotor meminta kolom lain.

## 1. File Excel (`openpyxl`)

Nama file: `Dreamtify_<slug-event>_<tahap>_<YYYYMMDD-HHmm>.xlsx`

### Sheet 1 — `Data` (format promotor, urutan & judul kolom PERSIS)

| # | Judul kolom (persis) | Isi | Format sel |
|---|---|---|---|
| 1 | `Stempel waktu` | `order.created_at` (WIB) | `dd/mm/yyyy hh:mm:ss` |
| 2 | `Nama Lengkap` | `holder_name` | teks |
| 3 | `No WA` | `holder_whatsapp` → fallback `buyer_whatsapp`, format `08…` | **teks** |
| 4 | `Email` | `holder_email` → fallback `buyer_email` | teks |
| 5 | `No. KTP` | NIK penuh bila diizinkan, selain itu `(disembunyikan)` | **teks** (`@`), jangan jadi angka ilmiah |
| 6 | `Jenis Kelamin` | `L` / `P` | teks |
| 7 | `Tanggal Lahir` | `holder_birth_date` | tanggal `dd/mm/yyyy` |
| 8 | `Username IG` | `holder_instagram` → fallback `buyer_instagram` | teks |
| 9 | `Jumlah Tiket yang di inginkan` | `quantity` | angka |
| 10 | `CAT UTAMA yang di inginkan` | nama kategori | teks |
| 11 | `CAT Cadangan 1 yang di inginkan (Wajib Beda dari CAT UTAMA)` | | teks |
| 12 | `CAT Cadangan 2 yang di inginkan (Wajib Beda dari CAT 1)` | | teks |
| 13 | `Punya membership?` | `Punya` bila ada nomor, selain itu `Tidak` | teks |
| 14 | `No Membership (wajib sudah registrasi presale)` | `holder_membership_no` | **teks** |
| 15 | `Jenis Jastip` | lihat label di bawah | teks |
| 16 | `Bukti Transfer FEE JASTIP/JASWAR` | URL bukti fee pertama yang `DITERIMA` (link bertanda tangan, lihat §3) | hyperlink |
| 17 | `Metode Pembayaran Tiket` | lihat label di bawah | teks |
| 18 | `No WA / IG yg merekomendasikan jastip di Dreamtify` | `order.referral` | teks |

Label persis:

| Enum | Teks di Excel |
|---|---|
| `JASWAR` | `JASWAR (Jasa War Only : Menggunakan Data Cust)` |
| `JASTIP` | `JASTIP (Terima Beres Tiket Fisik : Menggunakan Data Tim Dreamtify)` |
| `VA_BCA` | `VA BCA` |
| `VA_MANDIRI` | `VA Mandiri` |
| `TITIP_BAYAR` | `TITIP BAYAR ADMIN (Max H-1 sebelum War)` |

Untuk baris JASTIP, kolom identitas yang tidak diisi customer dibiarkan kosong
(tiket memakai data tim; lihat ASUMSI C2).

Gaya: baris judul tebal dengan latar `#BCE2F5`, freeze baris 1, autofilter,
lebar kolom otomatis (maks 50).

### Sheet 2 — `Hasil` (satu baris per tiket)

`Kode Pesanan`, `Stempel waktu`, `Nama Pemegang`, `Layanan`, `Tiket ke-`,
`Pilihan (Utama / Cad 1 / Cad 2)`, `Hasil`, `Kategori Didapat`, `Kode Tiket`,
`Status Penyerahan`.

### Sheet 3 — `Rekap`

- Per kategori: jumlah tiket diminta sebagai utama, jumlah secured.
- Per layanan (JASWAR/JASTIP): pesanan, tiket, secured.
- Per metode bayar.
- Waktu ekspor & filter yang dipakai.

## 2. Filter ekspor

- Wajib pilih event; tahap opsional (default semua tahap).
- Status default: pesanan yang **fee-nya sudah diterima** dan tidak batal
  (`MENUNGGU_PELUNASAN`, `VERIFIKASI_PELUNASAN`, `SIAP_WAR`, `PROSES_WAR`,
  `PENYELESAIAN`, `SELESAI`). Opsi "termasuk yang belum bayar".
- Urut `Stempel waktu` naik.
- Juga tersedia **CSV** (UTF-8 dengan BOM agar Excel membaca benar) untuk Sheet `Data`.

## 3. Link promotor `/p/<token>/`

- Aktif bila `event.promotor_link_enabled`. Token 32 karakter acak
  (`secrets.token_urlsafe`), bisa diganti admin (link lama mati).
- Halaman sederhana bermerek Dreamtify: nama event, pilihan tahap, jumlah
  pesanan & tiket per kategori (angka saja, tanpa data pribadi), "Data per
  <waktu>", tombol **Unduh Excel** dan **Unduh CSV**.
- NIK disertakan hanya bila `event.promotor_include_nik` (diatur Owner).
- Link bukti transfer di kolom 16: `/p/<token>/bukti/<payment_id>/?s=<tanda tangan>`
  (berlaku selama token promotor sama dan event belum diarsip).
- Setiap unduhan dicatat `AuditLog` (`export.promotor`, IP, tahap, termasuk NIK atau tidak).
- Rate limit 30 unduhan / jam per token. `noindex`, tidak ada di sitemap.

## 4. Tes wajib

- Judul kolom Sheet `Data` sama persis dengan tabel §1 (urutan & ejaan).
- NIK tersimpan sebagai teks 16 digit (tidak berubah jadi `3.17E+15`).
- NIK tidak muncul bila izin mati.
- Pesanan batal/belum bayar tidak ikut secara default.
