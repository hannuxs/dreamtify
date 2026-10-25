# Fase 07 — Mode War, VA & Hasil per Tiket

## Baca dulu
`CLAUDE.md`, `docs/02-aturan-bisnis.md` §4.3, §5, §8,
`docs/05-dashboard-admin.md` §6, `docs/04-halaman-publik.md` §5 (butir 2, 4, 7).

## Tujuan
Saat war, admin di HP bisa mengirim VA ke customer dan mengisi hasil setiap
tiket dengan satu ketukan; customer melihat VA dan hasilnya hampir seketika
di halaman lacak.

## Tugas
1. **Mode War** `/kelola/war/<phase_id>/` sesuai `docs/05` §6, dioptimalkan
   untuk HP (uji di lebar 360px):
   - Mulai war / Selesaikan war (`start_war`, `finish_war`, termasuk opsi
     "Tandai sisa sebagai Gagal" dengan konfirmasi).
   - Ringkasan angka, peringatan pesanan belum siap, filter cepat.
   - Kartu per pesanan → per tiket, tombol hasil
     [Utama] [Cad 1] [Cad 2] [Lainnya…] [Gagal] [Gagal-cust], simpan via HTMX,
     undo 10 detik, input kode tiket opsional.
   - Konflik antar-admin: simpan memakai kolom versi/`updated_at`; bila
     bentrok tampilkan nilai terbaru dan minta ulang.
   - Auto-refresh daftar tiap 15 detik tanpa mengganggu input aktif.
2. **VaNotice**:
   - Panel VA per pesanan (bank, nomor, nominal, batas, centang tiket) →
     tombol WA `VA_DIKIRIM` muncul.
   - Halaman lacak: banner VA dengan tombol salin & hitung mundur, tombol
     "Sudah saya bayar" (`DIKLAIM_CUSTOMER`), polling HTMX 10 detik selama
     tahap `WAR`.
   - Form "Kirim VA hasil war mandiri" di halaman lacak (bila
     `customer_va_enabled`, metode TITIP_BAYAR, tahap WAR) → antrian di Mode
     War → "Sudah dibayar tim" (`LUNAS`).
   - `run_periodic`: VA lewat batas → `KEDALUWARSA`.
3. Saat semua tiket pesanan terisi: `settlement` dihitung, status →
   `PENYELESAIAN`/`SELESAI`, notifikasi hasil dibuat (template final fase 09).
4. Halaman lacak: bagian "Tiket kamu" menampilkan hasil per tiket dengan
   badge `docs/06` §4, rincian biaya final & saldo.
5. Beranda tugas: kartu event yang sedang `WAR` disorot (badge pink live).
6. Tes: start_war hanya memindahkan `SIAP_WAR`; hasil SECURED kategori di
   luar pilihan (Lainnya) menghasilkan kekurangan bila lebih mahal; undo;
   finish_war menolak bila masih ada tiket MENUNGGU kecuali opsi tandai gagal;
   customer hanya melihat VA miliknya.

## Selesai bila
Simulasi war 10 pesanan (campuran VA & titip bayar) bisa diselesaikan di HP
tanpa membuka laptop, dan setiap customer melihat hasil serta saldo yang benar.

## Cara saya mengecek
1. Buka `/kelola/war/<id>/` di HP (atau mode HP browser) dan halaman lacak
   customer di jendela lain berdampingan.
2. Kirim VA → banner muncul di halaman customer dalam ±10 detik.
3. Isi hasil; cocokkan saldo dengan contoh `docs/02` §4.5.

## Penutup
Tes, `PROGRESS.md`, ringkasan. Jangan memulai fase 08.
