# Referensi — Google Form "Pelunasan Bigbang In Jakarta - Dreamtify"

Salinan isi form pelunasan lama (dibaca 25 Okt 2026). Di web, form ini
**digantikan oleh kartu tagihan di halaman lacak** yang menghitung nominal
otomatis.

## Deskripsi form

Sapaan pembuka ("Thank you for trusting Dreamtify, war semakin dekat…"),
lalu aturan:

- Full payment. Konfirmasi pembayaran setelah mendapatkan slot jastip,
  maksimal **H-2 ticketing (15 September) 19.00 WIB**.
- Bila tidak membayar sampai batas waktu, **slot dioper ke waiting list**.
- Bila customer war mandiri dan lebih dulu secured, kirimkan VA ke tim
  Dreamtify dan tim membantu proses pembayarannya.
- Nominal transfer = **harga kategori tertinggi** di antara pilihan.
  Contoh: Prio CAT 1, Cadangan 1 Gold, Cadangan 2 CAT 3 → transfer harga Gold.
- Harga dikalikan jumlah tiket. Contoh: 2 tiket Gold → Rp7.385.000 × 2 = Rp14.770.000.
- Bila sudah membayar **early booking slot**, nominal dikurangi early booking
  yang sudah ditransfer.
- Pembayaran hanya melalui BCA 7805519240 a.n. Norma Anissa Yuliana.
- Bagian "Pricelist" berisi gambar daftar harga.

## Pertanyaan

1. Email *
2. Nama Pengirim *
3. Nominal TF *
4. Bukti Transfer * — upload 1 file, maks 100 MB
5. Bank Pengirim *
6. Jumlah Tiket *

Catatan: form ini tidak meminta kode pesanan, sehingga admin harus mencocokkan
manual dengan form pertama. Web menyelesaikan ini karena pelunasan diupload dari
halaman pesanan itu sendiri.

## Pemetaan ke web

| Form lama | Web |
|---|---|
| Nominal (dihitung customer) | `Order.pelunasan_due` (dihitung sistem, `docs/02` §4.1) |
| Nama pengirim, bank, nominal, bukti | `Payment` kind `PELUNASAN` |
| Batas H-2 19.00 WIB | `SalePhase.pelunasan_deadline` |
| Dioper ke waiting list | aksi admin "Lepas slot" + kebijakan event |
| VA dari war mandiri | `VaNotice` dengan `source=CUSTOMER` |
| Early booking slot | `Event.early_booking_per_ticket` |
