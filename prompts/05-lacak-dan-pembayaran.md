# Fase 05 — Lacak Pesanan & Upload Pembayaran

## Baca dulu
`CLAUDE.md`, `docs/02-aturan-bisnis.md` §4.2, §4.4, §9 (refund), §10, §11,
`docs/04-halaman-publik.md` §5, `docs/09-keamanan-privasi.md` §4–§6.

## Tujuan
Customer bisa masuk ke halaman lacak (kode + WA atau link token), melihat
semua informasi pesanannya, mengupload bukti pembayaran, mengisi rekening
refund, mengubah data pemegang, dan membatalkan pesanan.

## Tugas
1. `/lacak/` (form kode + WA) dan `/lacak/<kode>/` (session 12 jam atau
   `?t=` token 30 hari). Rate limit & pesan gagal umum.
2. Halaman lacak lengkap sesuai `docs/04` §5, **kecuali** bagian yang
   bergantung pada fase berikutnya — tetap buat tempatnya dengan data nyata:
   - Kartu status + "Yang perlu kamu lakukan sekarang" (satu fungsi
     `next_action(order)` di services yang mengembalikan teks & aksi).
   - Kartu tagihan + **upload bukti** (FEE / PELUNASAN / KEKURANGAN dipilih
     otomatis dari status & saldo) → `transitions.submit_payment()`.
   - Tiket kamu (hasil & penyerahan tampil sesuai data; akan terisi di fase 07–08).
   - Rincian biaya (dari `settlement`).
   - Form rekening refund (tampil bila saldo > 0).
   - Timeline publik.
   - Ubah data pemegang (sebelum `PROSES_WAR`; audit).
   - Batalkan pesanan: modal dengan `cancellation_preview()` (berapa hangus,
     berapa kembali) → `transitions.cancel_by_customer()`.
   - Tombol WA admin dengan pesan berisi kode.
   - Banner VA & form VA mandiri: buat komponennya, aktif di fase 07.
3. **Upload aman** (`apps/core/uploads.py`): validasi isi, maks 10 MB,
   buang EXIF, re-encode, nama UUID, `media/private/`. View `/berkas/<id>/`
   dengan cek izin (admin / session lacak pemilik / tanda tangan promotor).
4. Halaman sukses (fase 04) kini punya form upload bukti inline.
5. Tes: akses lacak (benar/salah/token kedaluwarsa/rate limit); customer A
   tidak bisa melihat pesanan & berkas B; upload file palsu & terlalu besar
   ditolak; upload fee → `VERIFIKASI_FEE`; batal sebelum bayar →
   `DIBATALKAN`, sesudah fee diterima → `HANGUS` dengan nominal benar;
   ubah data pemegang setelah `PROSES_WAR` ditolak.

## Selesai bila
Customer dari fase 04 bisa membuka halaman lacak di HP, upload bukti fee,
dan status berubah menjadi "Bukti fee sedang dicek".

## Cara saya mengecek
1. Buka link lacak dari halaman sukses di jendela penyamaran (incognito).
2. Coba masuk lewat `/lacak/` dengan nomor WA salah → pesan umum.
3. Upload foto bukti → status berubah. Coba upload file `.txt` yang diganti
   nama jadi `.jpg` → ditolak.

## Penutup
Tes, `PROGRESS.md`, ringkasan. Jangan memulai fase 06.
