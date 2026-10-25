# Fase 10 — Rekap, Ekspor Promotor & Link Promotor

## Baca dulu
`CLAUDE.md`, `ASUMSI-DAN-KEPUTUSAN.md` (A7, C2, C11),
**`docs/07-ekspor-promotor.md` (seluruhnya)**,
`docs/referensi/form-jaswar-jastip.md`, `docs/05-dashboard-admin.md` §10.

## Tujuan
Rekap untuk promotor tinggal 1 klik — atau promotor mengunduh sendiri lewat
link rahasia — dengan kolom persis seperti Google Form lama. Owner punya
rekap keuangan per event.

## Tugas
1. `apps/exports/promotor_format.py`: definisi kolom tunggal (judul, pengambil,
   format) sesuai `docs/07` §1.
2. Pembuat Excel (`openpyxl`): sheet `Data`, `Hasil`, `Rekap`, gaya judul,
   freeze, autofilter, NIK/WA/membership sebagai teks, tanggal benar, link
   bukti transfer bertanda tangan. Juga CSV UTF-8 BOM untuk sheet `Data`.
   Gunakan mode write-only/streaming agar ringan untuk ribuan baris.
3. **Rekap & Ekspor** `/kelola/rekap/`: pilih event/tahap/filter status,
   unduh Excel promotor (centang NIK hanya Owner), rekap ringkas (tabel di
   layar), **rekap keuangan** (fee diterima, pelunasan diterima, refund
   keluar, saldo tertahan, kekurangan, pendapatan fee final), unduh rekap
   keuangan Excel.
4. **Link promotor** `/p/<token>/` sesuai `docs/07` §3 (halaman bermerek,
   angka ringkas tanpa data pribadi, unduh Excel/CSV, rate limit, audit,
   `noindex`). Bukti transfer: `/p/<token>/bukti/<payment_id>/?s=…`.
5. Tab Promotor di form event (fase 03) kini menampilkan statistik unduhan
   terakhir (dari AuditLog).
6. Tes `docs/07` §4 + link promotor nonaktif → 404, token diganti → link
   lama 404, rate limit, NIK tidak ikut tanpa izin.

## Selesai bila
File Excel promotor dibuka di Excel/Google Sheets: urutan & judul kolom
sama persis dengan form lama, NIK tampil 16 digit utuh (bila diizinkan),
link bukti transfer bisa dibuka.

## Cara saya mengecek
1. `/kelola/rekap/` → pilih event contoh → unduh Excel promotor → buka di Excel.
2. Aktifkan link promotor, buka di jendela penyamaran, unduh.
3. Bandingkan judul kolom dengan `docs/07` §1.

## Penutup
Tes, `PROGRESS.md`, ringkasan. Jangan memulai fase 11.
