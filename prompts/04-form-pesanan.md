# Fase 04 — Detail Event & Form Pesanan

## Baca dulu
`CLAUDE.md`, `ASUMSI-DAN-KEPUTUSAN.md` (C1, C2, C7, C8),
`docs/02-aturan-bisnis.md` §3, §4.1, §6, §7, `docs/04-halaman-publik.md`
§2, §3, §4, `docs/06-desain-visual.md`, `docs/09` §8.

## Tujuan
Customer bisa membuka event, membaca pricelist & syarat, lalu membuat pesanan
multi-baris tiket dan sampai di halaman sukses dengan nominal transfer yang benar.

## Tugas
1. **Detail event** `/event/<slug>/` sesuai `docs/04` §2 (tab tahap,
   pricelist kategori + matriks fee, syarat accordion, tombol sticky,
   status kuota). Event `DRAFT` → 404 (kecuali admin login: tampil dengan
   banner "Pratinjau").
2. **Form pesanan** `/event/<slug>/pesan/` sesuai `docs/04` §3:
   - Stepper 4 langkah (Alpine.js CSP, komponen di `app.js`).
   - Kartu baris tiket dinamis (tambah/hapus/salin), field pemegang berubah
     sesuai layanan, "Pemegang = saya".
   - Opsi kategori yang sudah dipilih di kartu yang sama dinonaktifkan.
   - Ringkasan biaya live via endpoint HTMX `/event/<slug>/pesan/hitung/`
     yang memanggil `services/pricing.py`.
   - Draf di localStorage tanpa NIK/tanggal lahir/membership (try/catch).
   - Validasi server lengkap (Django Form + formset untuk baris), pesan error
     di bawah field, kembali ke langkah yang salah.
   - Honeypot, token sekali pakai, rate limit 5 / 10 menit / IP.
   - Submit memanggil `transitions.create_order()` (kuota → `MENUNGGU_FEE`
     atau `WAITING_LIST`; fee_deadline; snapshot harga; slot tiket;
     peringatan NIK ganda).
3. **Halaman sukses** `/pesanan/<kode>/berhasil/` sesuai `docs/04` §4,
   termasuk pilihan "bayar fee saja / bayar sekaligus" untuk titip bayar,
   rekening (tombol salin), hitung mundur, link lacak bertoken, tombol
   "kirim link ke WA saya". Form upload bukti di halaman ini boleh berupa
   tombol menuju halaman lacak dulu (upload dibangun di fase 05).
4. Akses halaman sukses: hanya browser yang baru membuat pesanan (session)
   atau token lacak.
5. Tes: pesanan 2 baris tersimpan dengan slot benar; kategori sama ditolak;
   field JASWAR wajib, JASTIP minimal; kuota penuh → waiting list;
   rate limit; tahap tutup → form tidak bisa dibuka; nominal halaman sukses
   = `pricing`.

## Jangan
- Tidak ada rumus harga di JavaScript.
- NIK tidak boleh muncul utuh di halaman mana pun setelah dikirim.

## Selesai bila
Pesanan contoh 4 (`docs/02` §4.5) bisa dibuat lewat form di HP dan halaman
sukses menampilkan Tagihan sekarang Rp750.000 dan Pelunasan nanti Rp9.500.000
(dengan data contoh yang sama).

## Cara saya mengecek
1. Buka `http://localhost:8383/event/<slug-contoh>/` di mode HP.
2. Pesan: 2 Duality JASWAR (saya) + 1 CAT 3 JASTIP (teman), titip bayar.
3. Cocokkan angka di halaman sukses. Cek pesanan muncul di `/kelola/sistem/`.

## Penutup
Tes, `PROGRESS.md`, ringkasan. Jangan memulai fase 05.
