# Referensi — auloey.com (dilihat 25 Okt 2026)

Web referensi dari pemilik. **Jangan menyalin** logo, maskot, warna, atau teks
Auloey; ambil polanya saja.

## Yang diamati

- Satu brand dengan banyak layanan (rental HP, rental lightstick, titip jual
  tiket, jastip barang, dll.) dalam satu halaman depan berisi kartu layanan
  dengan badge "Tersedia" / "Segera hadir".
- Header: logo, sapaan ("Selamat datang, …!"), tombol "Masuk admin / investor".
- Customer bisa menjelajah tanpa login.
- Alur rental HP ditampilkan sebagai **3 langkah bernomor** di atas halaman:
  ① Pilih konser ② Pilih HP ③ Booking & bayar DP.
- Daftar konser sebagai **kartu poster** (nama, tanggal, venue, "Lihat koleksi →").
  Saat dilihat ada ±16 konser aktif sekaligus.
- Memilih konser menampilkan item dengan **harga, stok tersisa ("11 tersedia"),
  dan DP minimum**, tombol "Booking sekarang".
- "My Bookings": customer melengkapi data, menerima Order ID, upload bukti DP
  untuk diverifikasi admin.
- Gaya: ceria, kartu membulat, emoji, sapaan khusus komunitas, mobile-first.

## Yang dipakai untuk Dreamtify

| Pola Auloey | Di Dreamtify |
|---|---|
| Langkah bernomor | Stepper di detail event & form pesanan |
| Kartu poster konser | Kartu event di beranda |
| Stok tersisa | Indikator sisa slot / waiting list |
| My Bookings + Order ID + upload bukti | Halaman lacak (tanpa login: kode + WA) |
| Nada ramah & sapaan | Sapaan "kak", maskot awan |
| Banyak layanan | Struktur `ServiceType` yang bisa ditambah kelak (bukan MVP) |
