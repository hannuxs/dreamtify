# Fase 03 — Login Admin, Pengaturan & Kelola Event

## Baca dulu
`CLAUDE.md`, `docs/05-dashboard-admin.md` (§ awal, 1, 2, 12, 13),
`docs/06-desain-visual.md` §5, `docs/09-keamanan-privasi.md` §5.

## Tujuan
Admin bisa login, mengatur brand/rekening/FAQ, dan membuat event lengkap
(tahap, kategori, matriks fee, aturan) — termasuk duplikat event.

## Tugas
1. Login/logout admin di `/kelola/login/` (form bermerek, rate limit login,
   timeout sesi). Mixin/decorator `admin_required`, `owner_required`.
2. Layout dashboard final: sidebar desktop (logo kecil, menu sesuai
   `docs/05` peta URL — item yang belum dibangun tampil nonaktif "segera"),
   bottom nav HP, header dengan nama pengguna & peran.
3. **Beranda tugas** versi awal: kartu event aktif + jadwal 7 hari (kartu
   angka tugas diisi bertahap di fase berikutnya; tampilkan 0).
4. **Kelola event** (`docs/05` §2): daftar, form bertab (Info, Tahap & jadwal,
   Kategori, Matriks fee, Aturan, Promotor), simpan per tab (HTMX),
   validasi publikasi, **duplikat event**, upload poster (kompres Pillow,
   simpan di `media/public/`). Tab Promotor: buat token, salin link
   (halamannya dibuat di fase 10).
5. Tabel kategori dan matriks fee yang nyaman diisi di HP (input angka
   dengan pemisah ribuan saat ditampilkan, disimpan integer).
6. **Pengaturan** (Owner): Brand & kontak, Rekening (CRUD + urutan), Syarat &
   privasi, FAQ (CRUD + urutan), Aturan default. Tab "Template pesan"
   dibuat di fase 09.
7. **Pengguna** (Owner): tambah admin, set peran Owner/Admin, nonaktifkan,
   reset kata sandi. **Log aktivitas** (Owner): daftar AuditLog berfilter.
8. Semua aksi admin tercatat di AuditLog.
9. Tes: akses tanpa login → redirect; Admin tidak bisa membuka Pengaturan;
   duplikat event menyalin kategori & matriks fee tanpa pesanan; validasi
   publikasi menolak event tanpa fee lengkap.

## Selesai bila
- Saya bisa membuat event "Contoh Fanmeet" dengan tahap Presale & Gensale,
  7 kategori (Duality Package 3.500.000 VIP, CAT 1 2.500.000, CAT 2 2.000.000,
  CAT 3 1.500.000, CAT 4–6 bebas, semuanya REGULER kecuali Duality),
  matriks fee sesuai `docs/referensi/form-jaswar-jastip.md`, lalu
  menduplikatnya dalam < 5 menit. (Data ini sama dengan contoh di
  `docs/02` §4.5 dan dipakai lagi di fase berikutnya.)
- Tampilan rapi di HP dan laptop.

## Cara saya mengecek
1. `dev.bat` → `http://localhost:8383/kelola/` → login.
2. Buat event contoh seperti di atas, publikasikan tahap Presale.
3. Duplikat event, ubah nama & harga.
4. Coba login sebagai Admin (bukan Owner) → menu Pengaturan tidak bisa dibuka.

## Penutup
Tes, `PROGRESS.md`, ringkasan. Jangan memulai fase 04.
