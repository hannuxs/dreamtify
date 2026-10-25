# Fase 11 — Testimoni, Beranda, FAQ & Data Demo

## Baca dulu
`CLAUDE.md`, `ASUMSI-DAN-KEPUTUSAN.md` (A8, C15), `docs/04-halaman-publik.md`
§1, §6, §7, §8, `docs/05-dashboard-admin.md` §11, `docs/06-desain-visual.md`.
Gunakan skill/kemampuan desain frontend terbaik yang tersedia untuk polish visual.

## Tujuan
Halaman publik lengkap dan meyakinkan: beranda final, halaman testimoni,
FAQ, syarat, privasi; plus data demo agar web mudah dicoba.

## Tugas
1. **Beranda final** `/` sesuai `docs/04` §1 (ganti halaman "Segera hadir"):
   hero dengan motif awan, kartu event buka (hitung mundur, slot), cara kerja
   3 langkah, kartu JASWAR vs JASTIP, testimoni unggulan, FAQ ringkas, CTA
   lacak & WA. Empty state dengan maskot.
2. **Testimoni**:
   - `/testimoni/` sesuai `docs/04` §6 (grid, filter event, lightbox,
     ringkasan rating, paginasi).
   - Form testimoni di halaman lacak untuk pesanan `SELESAI` (satu kali per
     pesanan; gambar opsional lewat upload aman; masuk `MENUNGGU`).
   - Moderasi `/kelola/testimoni/` sesuai `docs/05` §11, termasuk tambah
     testimoni manual (screenshot chat). Gambar yang disetujui dipindah/
     disalin ke `media/public/`.
   - Beranda tugas: kartu "Testimoni menunggu".
3. **FAQ** `/faq/`, **Syarat** `/syarat/`, **Privasi** `/privasi/` dari
   Pengaturan. Tulis isi default syarat umum & kebijakan privasi yang sesuai
   aturan `docs/02` dan `docs/09` (bahasa awam; Owner bisa mengubah).
4. Meta & SEO dasar: title/description per halaman, Open Graph (poster event
   untuk halaman event), `robots.txt` (blokir `/kelola/`, `/lacak/`, `/p/`),
   sitemap sederhana untuk halaman publik.
5. **`seed_demo`** (hanya `DJANGO_ENV=dev`): 2 event (satu sesuai contoh
   `docs/02` §4.5), tahap, kategori, matriks fee, ±25 pesanan di semua status
   (termasuk hasil war, refund, penyerahan), testimoni dengan gambar contoh
   sederhana. Aktifkan `dev.bat seed`.
6. Polish lintas halaman publik: konsistensi spasi, status kosong, loading
   state HTMX, fokus keyboard, kontras.
7. Tes: testimoni customer hanya bisa sekali & hanya saat SELESAI; testimoni
   `MENUNGGU` tidak tampil publik; robots.txt; seed_demo menolak jalan di prod.

## Selesai bila
Beranda, event, testimoni, FAQ tampil rapi di HP & laptop dengan data demo,
dan alur testimoni customer → moderasi → tampil berjalan.

## Cara saya mengecek
1. `dev.bat seed` → buka beranda di HP & laptop.
2. Buka salah satu pesanan demo yang SELESAI lewat halaman lacak, kirim
   testimoni → setujui di admin → tampil di `/testimoni/`.

## Penutup
Tes, `PROGRESS.md`, ringkasan. Jangan memulai fase 12.
