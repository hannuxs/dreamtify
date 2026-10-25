# Referensi — Google Form "Jaswar/Jastip JNJM - Dreamtify"

Salinan isi form lama milik Dreamtify (dibaca 25 Okt 2026) sebagai referensi
aturan dan **format kolom promotor**. Form ini digantikan oleh web; jangan
menyalin tampilannya, tetapi pertahankan aturan & datanya.

## Deskripsi form

Pricelist Fanmeet JNJM-Dreamtify

**PRESALE**
- JASWAR (data cust): Duality Package 250K/tix, Non VIP 200K/tix
- JASTIP: diurus hingga tiket fisik/WB (data tim Dreamtify): VIP 300K/tix, Non VIP 250K/tix

**GENSALE**
- JASWAR (data cust): Duality Package 300K/tix, Non VIP 250K/tix
- JASTIP: diurus hingga tiket fisik/WB (data tim Dreamtify): VIP 350K/tix, Non VIP 300K/tix

Aturan:
- Harga tiket menggunakan sistem self-payment by customer.
- Jika tidak bisa standby saat war, sebaiknya titip bayar ke admin dengan
  full payment fee jastip + harga tiket di awal.
- Menggunakan data pribadi; namun jika kondisi saat war tidak memungkinkan
  memakai data pribadi, tim Dreamtify memakai data owner untuk mengamankan
  tiket customer.
- Fee jaswar & jastip full payment di awal.
- Cancel = hangus.
- Jika tidak berhasil secure, dikembalikan 100% setelah dikurangi biaya
  booking slot 50K.
- Jika gagal secure karena customer gagal bayar, tidak ada refund.
- Wajib mencantumkan kategori utama dan cadangan. Jika kategori utama tidak
  didapat, tim otomatis beralih ke pilihan kedua tanpa konfirmasi.
- Jika kategori utama maupun cadangan sold out, tim mengamankan kategori mana
  pun yang tersedia tanpa konfirmasi.
- Pembayaran: Bank BCA 7805519240 a.n. Norma Anissa Yuliana.

## Pertanyaan (urutan asli; * = wajib)

1. Nama Lengkap *
2. No WA *
3. Email *
4. No. KTP *
5. Jenis Kelamin * — L / P
6. Tanggal Lahir * (tanggal)
7. Username IG *
8. Jumlah Tiket yang di inginkan * — 1 / 2 / 3 / 4
9. CAT UTAMA yang di inginkan * — Duality Package, CAT 1, CAT 2, CAT 3, CAT 4, CAT 5, CAT 6
10. CAT Cadangan 1 yang di inginkan (Wajib Beda dari CAT UTAMA) * — opsi sama
11. CAT Cadangan 2 yang di inginkan (Wajib Beda dari CAT 1) * — opsi sama
12. Punya membership? * — Punya / Tidak
13. No Membership (wajib sudah registrasi presale)
14. Jenis Jastip * —
    - JASWAR (Jasa War Only : Menggunakan Data Cust)
    - JASTIP (Terima Beres Tiket Fisik : Menggunakan Data Tim Dreamtify)
15. Bukti Transfer FEE JASTIP/JASWAR * — upload 1 file, maks 10 MB
16. Metode Pembayaran Tiket * — "Pastikan anda standby saat kami pesankan
    tiket, tiket hangus karena kelalaian customer maka tidak ada refund.
    Apabila tidak memungkinkan standby pembayaran, silakan pilih opsi Titip
    Bayar Admin."
    - VA BCA
    - VA Mandiri
    - TITIP BAYAR ADMIN (Max H-1 sebelum War)
17. No WA / IG yg merekomendasikan jastip di Dreamtify *

Form mengumpulkan email akun Google pengisi (karena ada upload file).

## Pemetaan ke web

| Form lama | Web |
|---|---|
| 1 isian | 1 `OrderLine` |
| Pertanyaan 1–7, 13 | data pemegang di `OrderLine` |
| 8 | `OrderLine.quantity` |
| 9–11 | `cat_primary`, `cat_backup1`, `cat_backup2` |
| 14 | `OrderLine.service_type` |
| 15 | `Payment` (kind `FEE`) |
| 16 | `Order.ticket_payment_method` |
| 17 | `Order.referral` |
| Pricelist | `FeeRule` per tahap × layanan × tier; "Duality Package"/"VIP" = tier `VIP`, "Non VIP" = `REGULER` |
| Rekening | `BankAccount` (seed) |
