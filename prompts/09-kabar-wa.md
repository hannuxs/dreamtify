# Fase 09 — Kotak Kabar & Template Pesan WhatsApp

## Baca dulu
`CLAUDE.md`, `ASUMSI-DAN-KEPUTUSAN.md` (C9), `docs/08-notifikasi-wa.md`
(seluruhnya), `docs/05-dashboard-admin.md` §9, §12.

## Tujuan
Setiap kejadian penting otomatis menyiapkan pesan WA yang tinggal dikirim
admin dengan satu ketukan (atau beruntun), dan email otomatis bila diaktifkan.

## Tugas
1. `notifications/services.py`: `enqueue(order, key, extra_context)` dengan
   `dedupe_key`, render template (placeholder `docs/08` §2), pemilihan
   channel, dan pembuatan link lacak bertoken. Pastikan semua titik di
   `transitions.py` dan aksi Mode War/penyerahan memanggil key yang benar
   (`docs/08` §3).
2. `notifications/backends.py`: `ManualWhatsAppBackend`, `EmailBackend`
   (Django email, template `templates/emails/` sederhana bermerek),
   `HttpWhatsAppGatewayBackend` (stub dengan docstring cara mengaktifkan).
3. Seed **semua** template default di `seed_initial` (update hanya bila
   belum diubah pengguna).
4. **Kotak Kabar** `/kelola/kabar/` sesuai `docs/05` §9: filter, tombol
   "Kirim WA" (buka `wa.me` di tab baru + tandai TERKIRIM), Lewati, Ubah pesan,
   **Mode beruntun** (satu pesan per layar, "Kirim & lanjut").
5. Tombol "Kirim kabar WA" di detail pesanan & Mode War memakai template yang
   sesuai konteks.
6. Pengaturan → tab **Template pesan** (Owner): daftar, edit, pratinjau dengan
   data contoh, peringatan placeholder tak dikenal, tombol "Kembalikan default".
7. `run_periodic`: pengingat `PENGINGAT_FEE` (3 jam) dan
   `PENGINGAT_PELUNASAN` (24 jam), tanpa duplikat.
8. Beranda tugas: kartu "Kabar belum dikirim".
9. Tes: semua template default ter-render tanpa placeholder tersisa;
   dedupe mencegah kabar ganda; URL `wa.me` benar (nomor 62…, teks
   ter-encode); email terkirim ke `locmem` saat diaktifkan; pengingat tidak
   ganda saat `run_periodic` dijalankan dua kali.

## Selesai bila
Setelah simulasi war, saya bisa mengabari semua customer satu event lewat
mode beruntun, dan setiap pesan berisi kode & link lacak yang benar.

## Cara saya mengecek
1. Jalankan alur fase 06–08 dengan nomor WA saya sendiri sebagai customer.
2. Buka `/kelola/kabar/` → "Mulai kirim beruntun" → WhatsApp terbuka
   dengan pesan siap kirim.
3. Ubah satu template di Pengaturan, lihat pratinjaunya.

## Penutup
Tes, `PROGRESS.md`, ringkasan. Jangan memulai fase 10.
