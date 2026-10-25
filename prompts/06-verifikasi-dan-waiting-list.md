# Fase 06 — Daftar Pesanan, Verifikasi Pembayaran & Waiting List

## Baca dulu
`CLAUDE.md`, `docs/02-aturan-bisnis.md` §4.2, §4.4, §5, §6, §7,
`docs/05-dashboard-admin.md` §1, §3, §4, §5.

## Tujuan
Admin bisa melihat & mengelola semua pesanan lintas event, memverifikasi
bukti transfer dengan sangat cepat, dan mengelola waiting list serta
pesanan yang lewat batas pelunasan.

## Tugas
1. **Daftar pesanan** `/kelola/pesanan/` dengan filter, pencarian (kode, nama,
   WA, email, nama pemegang, NIK lengkap via hash), paginasi, tampilan kartu
   di HP. Query efisien (tanpa N+1; cek dengan `assertNumQueries` di tes).
2. **Detail pesanan** `/kelola/pesanan/<kode>/` sesuai `docs/05` §3:
   aksi kontekstual, NIK tersamar + "Lihat NIK" (Owner, audit `nik.reveal`),
   keuangan lengkap, daftar Payment dengan pratinjau bukti, timeline,
   catatan internal, edit data (aturan §11), "Hitung ulang tagihan"
   (konfirmasi + audit), tambah pembayaran manual, salin link lacak.
3. **Antrian verifikasi** `/kelola/verifikasi/` sesuai `docs/05` §4
   (bukti besar dengan zoom/putar, nominal diharapkan vs klaim, terima
   dengan nominal diterima, tolak dengan alasan cepat, pintasan keyboard
   T/X/J/K, otomatis lanjut). Memakai `transitions.verify_payment()` /
   `reject_payment()`.
4. **Waiting list** `/kelola/waiting-list/` sesuai `docs/05` §5: per tahap,
   kuota/terpakai/sisa, "Naikkan" (`promote_from_waitlist`), "Batalkan";
   daftar lewat batas pelunasan dengan "Lepas slot" (modal menampilkan dampak
   keuangan dari `settlement`).
5. **Beranda tugas**: isi kartu angka "Bukti menunggu verifikasi",
   "Lewat batas pelunasan", "Waiting list".
6. Command `run_periodic` (versi awal, idempoten) untuk butir 1, 4, 6 di
   `docs/02` §7 (pengingat & VA menyusul di fase 07/09). Bisa dijalankan
   manual: `.venv\Scripts\python manage.py run_periodic`.
7. Tes: verifikasi kurang/pas/lebih/bayar sekaligus → status benar; tolak →
   kembali ke MENUNGGU_*; naikkan waiting list menolak bila kuota habis;
   lepas slot sesuai kebijakan event; `run_periodic` membatalkan pesanan
   lewat `fee_deadline` dan aman dijalankan dua kali; Admin non-Owner tidak
   bisa "Lihat NIK".

## Selesai bila
Saya bisa memverifikasi 10 bukti transfer berturut-turut dalam < 2 menit di
laptop, dan status pesanan di halaman lacak customer berubah sesuai.

## Cara saya mengecek
1. Buat beberapa pesanan & upload bukti (atau minta Claude Code membuat data
   uji sementara).
2. Buka `/kelola/verifikasi/`, pakai tombol T/X dan J/K.
3. Isi kuota tahap kecil (mis. 3), buat pesanan sampai masuk waiting list,
   batalkan satu, lalu naikkan dari waiting list.

## Penutup
Tes, `PROGRESS.md`, ringkasan. Jangan memulai fase 07.
