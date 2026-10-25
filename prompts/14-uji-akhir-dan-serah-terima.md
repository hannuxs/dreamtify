# Fase 14 — Uji Akhir & Serah Terima

## Baca dulu
Semua dokumen di `docs/`, terutama **`docs/11-pengujian.md`**, dan
`PROGRESS.md` (bagian "Pertanyaan terbuka" & "Catatan").

## Tujuan
Membuktikan seluruh web memenuhi kriteria terima, merapikan sisa masalah,
dan menyerahkan panduan pemakaian kepada pemilik.

## Tugas
1. Jalankan seluruh tes di MariaDB; perbaiki yang gagal. Tambah tes untuk
   celah yang ditemukan.
2. Jalankan **12 skenario manual** `docs/11` §2 secara berurutan (pakai
   browser bila tersedia; bila tidak, uji lewat Django test client dan
   jelaskan). Catat hasil tiap skenario di `PROGRESS.md` (✅/❌ + catatan).
3. Periksa ulang konsistensi dengan `docs/02` (enum, rumus, transisi) dan
   `docs/07` (kolom ekspor) — buat daftar perbedaan dan perbaiki.
4. Pemeriksaan kualitas:
   - Tidak ada N+1 di daftar pesanan, Mode War, halaman lacak.
   - Lighthouse mode HP (bila tersedia) beranda & form pesanan:
     Performance ≥ 85, Accessibility ≥ 90; jika tidak bisa dijalankan,
     lakukan audit manual (ukuran aset, gambar lazy, kontras, label).
   - Semua halaman di lebar 360px tanpa scroll horizontal.
   - Tidak ada NIK di `logs/`.
5. Tulis **`docs/PANDUAN-ADMIN.md`** (bahasa awam, untuk pemilik & admin):
   - Membuat/duplikat event dan membuka tahap
   - Memverifikasi pembayaran
   - Waiting list & lepas slot
   - Hari war: langkah demi langkah di HP (mulai war, kirim VA, isi hasil,
     selesaikan war)
   - Mengabari customer (Kotak Kabar, mode beruntun)
   - Refund, kekurangan, penyerahan gelang, info JASWAR
   - Ekspor & link promotor
   - Testimoni
   - Pengaturan, pengguna, template pesan
   - Apa yang dilakukan sistem otomatis (berkala & harian)
   - Kalau ada masalah (web mati, lupa password admin, restore backup)
6. Perbarui `README.md` proyek (bukan README paket): ringkasan, cara jalan,
   tautan ke panduan.
7. Ringkasan akhir di `PROGRESS.md`: semua fase ✅, daftar keputusan yang
   masih perlu dikonfirmasi pemilik, ide pengembangan berikutnya (payment
   gateway, WA API, layanan lain).

## Selesai bila
Semua kriteria `docs/11` §3 terpenuhi, atau setiap pengecualian tercatat
jelas beserta alasannya.

## Cara saya mengecek
1. Baca ringkasan akhir di `PROGRESS.md`.
2. Baca `docs/PANDUAN-ADMIN.md` dan coba bagian "Hari war" dengan data demo.
3. Instal di server produksi dengan `install.bat`.
