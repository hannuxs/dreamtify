# Paket Prompt Claude Code — Web Dreamtify

Paket ini berisi semua bahan yang dibutuhkan Claude Code untuk membangun web
**Dreamtify** (jasa war & jastip tiket konser): spesifikasi, aturan bisnis,
desain, dan prompt bertahap. Isinya bukan kode — kodenya akan ditulis Claude Code.

## Ringkasan proyek

| | |
|---|---|
| Bahasa | Python 3.12 (Django 5.2 LTS) |
| Database | MariaDB, port **3309** |
| Port web | **8383** |
| Server | Windows (Windows Server / Windows 10–11) |
| Instalasi produksi | 1 perintah: `install.bat` |
| Menjalankan | `dev.bat` (mode dev) dan `prod.bat` (mode produksi) |

Satu aplikasi web utuh: halaman customer + dashboard admin + link promotor,
satu codebase, satu database.

## Isi paket

```
README.md                  ← file ini
CLAUDE.md                  ← memori proyek; otomatis dibaca Claude Code
ASUMSI-DAN-KEPUTUSAN.md    ← keputusan yang saya ambil; ubah jika tidak sesuai
PROGRESS.md                ← checklist yang diperbarui Claude Code tiap fase
docs/                      ← spesifikasi lengkap (PRD, aturan, DB, UI, dll.)
docs/referensi/            ← salinan isi Google Form lama + catatan Auloey
prompts/                   ← prompt 00 (pemanasan) + 14 prompt bertahap, berurutan
assets/logo-dreamtify.png  ← logo
```

## Cara pakai

1. **Ekstrak zip**, misalnya ke `C:\`. Hasilnya folder `C:\dreamtify` —
   itulah folder proyek (file `CLAUDE.md` ada langsung di dalamnya).
2. **Baca dan sesuaikan `ASUMSI-DAN-KEPUTUSAN.md`** (±5 menit). Bagian yang
   ditandai ⚠️ paling perlu dicek. Kalau ada yang diubah, cukup edit file
   itu — Claude Code wajib mengikutinya.
3. **Pastikan tersedia** di mesin pengembangan:
   - Python 3.12 (64-bit) — centang "Add python.exe to PATH" saat instal
   - MariaDB yang berjalan di port 3309 (lihat `docs/10-instalasi-windows.md`)
   - Git (disarankan, agar setiap fase bisa di-commit)
4. **Buka terminal di folder proyek, jalankan `claude`.**
5. **Mulai dengan pemanasan** (disarankan): ketik di Claude Code

   ```
   Kerjakan prompts/00-mulai.md
   ```

   Claude Code akan menjelaskan ulang proyek ini, menyebut hal yang masih
   ambigu, dan mengecek apakah Python & MariaDB sudah siap. Jawab
   pertanyaannya bila ada.
6. **Jalankan prompt satu per satu**, mulai dari `prompts/01-...`:

   ```
   Kerjakan prompts/01-fondasi-proyek.md
   ```

   Tunggu sampai selesai, cek hasilnya (setiap prompt punya bagian
   "Cara saya mengecek"), lalu lanjut ke prompt berikutnya.
7. **Jangan lompat urutan.** Setiap fase membangun di atas fase sebelumnya.
   Jika satu fase bermasalah, minta Claude Code memperbaikinya dulu sebelum lanjut.

## Urutan prompt

| No | Prompt | Hasil |
|---|---|---|
| 00 | Pemanasan (opsional) | Claude Code memahami proyek, cek lingkungan, tanpa kode |
| 01 | Fondasi proyek | Django + MariaDB jalan di port 8383, `dev.bat`, tampilan dasar |
| 02 | Model data | Semua tabel + aturan harga & status (dengan tes) |
| 03 | Pengaturan & event | Login admin, kelola event, kategori, matriks fee |
| 04 | Form pesanan | Customer bisa memesan multi-tiket |
| 05 | Lacak & pembayaran | Halaman lacak, upload bukti, rekening refund |
| 06 | Verifikasi & waiting list | Antrian verifikasi bukti, kuota, waiting list |
| 07 | Mode war & hasil | Input VA, hasil war per tiket |
| 08 | Penyelesaian | Refund, kekurangan bayar, penyerahan gelang / e-tiket |
| 09 | Kabar WA | Kotak kabar + template pesan WhatsApp |
| 10 | Rekap & ekspor | Excel format promotor, link promotor, rekap keuangan |
| 11 | Testimoni, beranda, FAQ | Halaman publik lengkap |
| 12 | Keamanan & tugas harian | Enkripsi, rate limit, backup, hapus data otomatis |
| 13 | Installer Windows | `install.bat`, `prod.bat`, layanan otomatis |
| 14 | Uji akhir | Uji menyeluruh + panduan admin |

## Setelah selesai

- Server produksi: salin folder proyek → klik kanan `install.bat` →
  *Run as administrator*. Ikuti pertanyaannya.
- Mode dev: `dev.bat`. Mode produksi manual: `prod.bat`.
- Web terbuka di `http://<IP-server>:8383`, dashboard admin di `/kelola/`.
