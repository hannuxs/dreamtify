# 06 — Desain Visual

Logo: `assets/logo-dreamtify.png` (salin ke `static/img/logo-dreamtify.png`).
Karakter brand: awan biru yang tersenyum, huruf tebal bulat berbingkai navy,
pipi merah muda. Rasa: **ceria, lembut, bisa dipercaya** — seperti teman
fangirl yang rapi mengurus uangmu. Referensi nuansa: auloey.com (kartu poster
konser, langkah bernomor, playful) tetapi dengan identitas Dreamtify sendiri:
**awan & langit**, bukan kuning-merah.

## 1. Warna (diambil dari logo)

Definisikan di `static/css/tokens.css` sebagai CSS custom properties.

| Token | Hex | Pemakaian |
|---|---|---|
| `--navy-900` | `#052A45` | Teks utama, tombol utama, garis "stiker" (dari outline logo) |
| `--navy-700` | `#17476B` | Hover tombol, judul sekunder |
| `--sky-600` | `#3E7FB0` | Link, ikon aktif |
| `--sky-400` | `#88B5D6` | Isian huruf logo; aksen dekoratif, garis progress |
| `--cloud-200` | `#BCE2F5` | Badan awan logo; latar kartu sorot, chip |
| `--cloud-100` | `#E4F3FC` | Latar bagian |
| `--cloud-50` | `#F5FBFF` | Latar halaman |
| `--white` | `#FFFFFF` | Kartu |
| `--pink-400` | `#F26877` | Pipi logo; aksen kecil, titik "live", bintang dekoratif (bukan untuk teks kecil) |
| `--pink-600` | `#C23A4B` | Teks aksen pink (kontras AA) |
| `--pink-100` | `#FDE4E7` | Latar badge pink |
| `--sun-400` | `#F5B83D` | Bintang rating |
| `--ink-600` | `#4A6175` | Teks sekunder |
| `--line` | `#D3E6F2` | Garis/border tipis |
| `--success` / `--success-bg` | `#1E8E5A` / `#E3F6EC` | |
| `--warning` / `--warning-bg` | `#A15F00` / `#FFF1D1` | |
| `--danger` / `--danger-bg` | `#C8333F` / `#FDE6E8` | |
| `--info` / `--info-bg` | `#2F6E9F` / `#E4F3FC` | |

Semua kombinasi teks wajib kontras WCAG AA (4.5:1 teks biasa). Tema terang saja.

## 2. Tipografi

- Judul: **Fredoka** (600/700) — bulat, cocok dengan huruf logo.
- Isi & UI: **Nunito** (400/600/700/800).
- Self-host `.woff2` di `static/fonts/` + file lisensi SIL OFL. Unduh sekali
  saat pengembangan (Google Fonts), lalu commit. Tidak memuat dari CDN saat jalan.
- Skala (mobile → desktop): h1 32→44px, h2 24→32, h3 20→24, isi 16, kecil 14.
  Angka uang & kode pesanan memakai `font-variant-numeric: tabular-nums`.
- Judul hero boleh memakai efek "logo": warna `--navy-900` dengan
  `text-shadow: 0 3px 0 var(--cloud-200)`.

## 3. Bentuk & gaya

- **Gaya stiker**: kartu penting & tombol utama memakai border 2px
  `--navy-900` + bayangan tegas `4px 4px 0 var(--navy-900)` (meniru outline
  logo). Saat ditekan: bayangan mengecil ke `1px 1px` (terasa "ditekan").
- Kartu biasa: putih, radius 20px, border 1px `--line`, bayangan lembut.
- Radius: kartu 20px, tombol 14px, input 12px, chip 999px.
- Motif awan: bentuk awan SVG lembut di hero dan di atas footer (gelombang
  awan). Buat SVG sendiri (bukan salinan logo).
- Maskot kosong/sukses/error: awan sederhana dengan wajah (`static/img/cloud-*.svg`):
  `cloud-happy` (sukses), `cloud-sleep` (kosong), `cloud-sad` (error/gagal).
  Gambar sendiri dengan SVG sederhana, gaya senada logo.
- Spasi berbasis 4px. Lebar konten maks 1120px. Gutter HP 16px.
- Breakpoint: `640px`, `1024px`. Desain dimulai dari 360px.

## 4. Komponen (buat sebagai partial template `templates/components/`)

| Komponen | Catatan |
|---|---|
| Tombol | `primary` (navy, teks putih, gaya stiker), `secondary` (putih, border navy), `ghost`, `danger`; tinggi min 44px; status loading |
| Kartu event | Poster rasio 4:5, badge tahap, tanggal & venue, hitung mundur war, indikator slot, tombol |
| Badge status | Lihat tabel di bawah |
| Stepper | Langkah bernomor ①②③④, yang aktif terisi navy |
| Bar bawah sticky (HP) | Ringkasan biaya + tombol utama |
| Tombol salin | Ikon + teks, toast "Tersalin ✓" |
| Hitung mundur | "War dalam 2h 03j 14m", berubah merah < 1 jam |
| Upload | Area seret/klik, pratinjau gambar, nama file PDF, validasi ukuran sebelum kirim |
| Accordion | Untuk syarat & FAQ |
| Modal | Alpine.js; dipakai untuk konfirmasi batal, lepas slot |
| Toast | Pojok bawah (HP: atas bar bawah) |
| Timeline | Titik + garis vertikal, item terbaru di atas |
| Tabel → kartu | Tabel admin berubah jadi kartu di < 640px |
| Empty state | Maskot awan + kalimat + aksi |
| Rating bintang | Input & tampilan |

### Warna badge status pesanan

| Status | Gaya |
|---|---|
| WAITING_LIST | abu (`--ink-600` di `--cloud-100`) |
| MENUNGGU_FEE, MENUNGGU_PELUNASAN | warning |
| VERIFIKASI_FEE, VERIFIKASI_PELUNASAN | info |
| SIAP_WAR | navy terisi, teks putih |
| PROSES_WAR | pink dengan titik berdenyut (hormati `prefers-reduced-motion`) |
| PENYELESAIAN | `--sky-600` outline |
| SELESAI | success |
| DIBATALKAN, HANGUS | danger |

Badge hasil tiket: SECURED → success "Dapat CAT X 🎉"; GAGAL → danger "Tidak dapat";
GAGAL_CUSTOMER → danger "Tidak dapat (VA tidak dibayar)"; MENUNGGU → abu.

## 5. Admin

Token yang sama, tetapi: latar `--cloud-50`, tanpa motif awan besar, gaya
stiker hanya untuk tombol aksi utama, tabel padat (baris 44px), angka rata
kanan. Sidebar navy dengan logo kecil. Mode War: tombol hasil ukuran besar
(min 48px), warna jelas (Utama navy, Cadangan sky, Gagal danger-outline).

## 6. Aksesibilitas & performa

- Fokus terlihat: `outline: 3px solid var(--pink-400); outline-offset: 2px`.
- Semua input punya label; pesan error terhubung `aria-describedby`.
- Gambar poster pakai `loading="lazy"` dan ukuran tetap (hindari layout shift).
- Gambar upload publik dikompres ke lebar maks 1600px (Pillow) saat disimpan.
- Total CSS < 60 KB, JS hanya HTMX + Alpine + skrip kecil sendiri.
- `prefers-reduced-motion`: matikan animasi denyut & transisi besar.
