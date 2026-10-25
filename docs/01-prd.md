# 01 — PRD (Product Requirements Document)

## 1. Latar belakang

Dreamtify melayani jasa war (JASWAR) dan jasa titip tiket (JASTIP) konser.
Saat ini setiap event memakai dua Google Form (pesanan & pelunasan). Masalahnya:

| Masalah | Dampak |
|---|---|
| Membuat form baru tiap event, form & link terpisah | Lambat saat 2+ event berdekatan |
| Cek transfer & konfirmasi manual satu per satu | Admin kewalahan, customer menunggu |
| Customer menghitung sendiri nominal pelunasan | Salah transfer, harus dicek ulang |
| 1 form = 1 set kategori untuk 1 orang | Tidak bisa pesan beberapa kategori / beliin orang lain dalam 1 kali isi |
| Hasil war & refund dikabari manual | Customer terus bertanya |
| Rekap untuk promotor disusun manual | Promotor menagih karena lambat |

## 2. Tujuan

1. **Satu web** untuk semua event: membuat event baru (atau menduplikat event
   lama) cukup beberapa menit.
2. **Customer melayani dirinya sendiri**: memesan, membayar, melihat status,
   tagihan, hasil war, refund, dan penyerahan tiket di satu halaman lacak.
3. **Admin bekerja dari satu dashboard**: antrian tugas jelas (verifikasi,
   pelunasan, refund, kabar), semua angka dihitung otomatis.
4. **Rekap promotor sekali klik** dalam format yang sudah mereka kenal, plus
   link agar promotor bisa mengunduh sendiri.
5. Halaman **testimoni** untuk membangun kepercayaan.

## 3. Pengguna

| Peran | Kebutuhan utama | Perangkat |
|---|---|---|
| Customer | Pesan cepat, tahu harus bayar berapa, tahu status tanpa bertanya | HP |
| Admin | Verifikasi cepat, input hasil war cepat (saat war, di HP), kabari massal | HP + laptop |
| Owner | Semua akses admin + pengaturan, data sensitif, laporan keuangan | Laptop |
| Promotor | Unduh data pembeli dalam format kolom yang diminta | Laptop |

## 4. Ruang lingkup (MVP — semuanya dibangun)

**Publik**
- Beranda, daftar event buka, detail event + pricelist + syarat
- Form pesanan multi-baris tiket (beberapa pemegang, kategori, layanan)
- Halaman sukses dengan nominal & rekening
- Lacak pesanan (kode + WA): timeline, tagihan, upload bukti, info VA saat war,
  hasil per tiket, form rekening refund, status gelang / e-tiket, batalkan,
  kirim testimoni
- Testimoni, FAQ, Syarat & Ketentuan, Kebijakan Privasi
- Link promotor per event

**Admin (`/kelola/`)**
- Beranda tugas lintas event
- Kelola event (tahap, kategori, matriks fee, aturan, kuota, duplikat)
- Daftar & detail pesanan, edit data dengan jejak audit
- Antrian verifikasi pembayaran
- Waiting list
- Mode War (input VA, hasil per tiket, cepat di HP)
- Penyelesaian: antrian refund, kekurangan bayar
- Penyerahan tiket: gelang (JASTIP) dan e-tiket/kabar (JASWAR)
- Kotak Kabar (WA click-to-chat dengan template)
- Rekap & ekspor (format promotor, keuangan)
- Moderasi testimoni
- Pengaturan: brand, rekening, kontak, template pesan, FAQ, syarat, pengguna
- Log aktivitas

**Sistem**
- Tugas harian terjadwal: batalkan pesanan lewat batas, pengingat, hapus data
  sensitif, backup database
- Installer Windows 1 perintah, `dev.bat`, `prod.bat`

## 5. Di luar cakupan (bukan MVP)

- Payment gateway otomatis (disiapkan strukturnya saja: metode pembayaran
  terpisah dari logika)
- Pengiriman WA otomatis via API berbayar (disiapkan antarmuka backend saja)
- Akun/login customer
- Aplikasi mobile native
- Multi-bahasa (UI hanya Bahasa Indonesia)
- Layanan lain seperti rental HP/lightstick (struktur jangan menghalangi
  penambahan layanan di masa depan, tapi tidak dibangun)

## 6. Ukuran keberhasilan

| Ukuran | Target |
|---|---|
| Waktu membuat event baru (duplikat) | < 5 menit |
| Waktu verifikasi 1 bukti transfer | < 15 detik |
| Waktu input hasil war 1 tiket di HP | < 5 detik |
| Waktu mengabari semua customer 1 event setelah war | < 15 menit untuk 50 pesanan |
| Rekap promotor | 1 klik / promotor unduh sendiri |
| Salah hitung pelunasan/refund | 0 (dihitung sistem) |

## 7. Kebutuhan non-fungsional

- Bahasa Indonesia, mobile-first, ringan (tanpa framework JS berat).
- Berjalan di Windows Server, MariaDB port 3309, web port 8383.
- Kuat untuk lonjakan saat event dibuka: target 50 pesanan/menit di server kecil
  (waitress 8 thread). Hindari query N+1.
- Aman: data KTP terenkripsi, akses berbasis peran, audit, rate limit.
- Dapat dipulihkan: backup harian otomatis dan panduan restore.
