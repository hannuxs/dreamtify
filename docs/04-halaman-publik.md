# 04 — Halaman Publik (customer)

Prinsip: **mobile-first**, sekali lihat langsung paham "harus apa sekarang",
tidak perlu bertanya ke admin. Semua teks Bahasa Indonesia yang ramah dan santai
(sapaan "kak"), tidak alay. Lihat `docs/06` untuk gaya visual.

## Peta URL

| URL | Halaman |
|---|---|
| `/` | Beranda |
| `/event/<slug>/` | Detail event |
| `/event/<slug>/pesan/` | Form pesanan |
| `/pesanan/<kode>/berhasil/` | Halaman sukses (butuh izin session/token) |
| `/lacak/` | Form masuk lacak |
| `/lacak/<kode>/` | Halaman lacak pesanan |
| `/testimoni/` | Testimoni |
| `/faq/` | FAQ |
| `/syarat/` | Syarat & ketentuan umum |
| `/privasi/` | Kebijakan privasi |
| `/p/<token>/` | Halaman promotor (lihat `docs/07`) |
| `/berkas/<id>/` | Unduh file privat milik pesanan (cek izin) |

Header (semua halaman): logo, menu Event · Lacak Pesanan · Testimoni · FAQ,
tombol WA admin. Di HP: header ringkas + menu laci. Footer: kontak, IG,
syarat, privasi, "© Dreamtify".

## 1. Beranda `/`

1. **Hero**: logo awan, tagline, kalimat singkat ("Jasa war & jastip tiket
   konser. Kamu tinggal duduk manis, kami yang berjuang."), tombol
   "Lihat event" dan "Lacak pesanan".
2. **Event yang sedang buka**: kartu poster (lihat komponen di `docs/06`):
   nama, tanggal, venue, badge tahap ("Presale buka", "Gensale segera"),
   hitung mundur war, indikator slot ("Sisa ±12 slot" / "Waiting list").
   Kosong → ilustrasi awan + "Belum ada event, pantau IG kami ya".
3. **Cara kerja** 3 langkah: Pilih event → Isi pesanan & bayar fee → Pantau
   hasil di halaman lacak.
4. **JASWAR vs JASTIP**: dua kartu berdampingan (di HP bertumpuk):
   - JASWAR — "Jasa war saja. Pakai data kamu. Gelang kamu tukar sendiri."
   - JASTIP — "Terima beres. Pakai data tim. Gelang kami tukarkan & serahkan."
5. **Testimoni pilihan** (3–6 yang `is_featured`), tombol "Lihat semua".
6. **FAQ ringkas** (5 teratas) + tombol "Tanya admin via WA".

## 2. Detail event `/event/<slug>/`

- Poster besar, nama, artis, tanggal, venue, platform tiket.
- **Pilih tahap** (tab Presale/Gensale) bila lebih dari satu; tampilkan jadwal
  war, batas pesan, batas pelunasan, status tahap.
- **Pricelist** (tabel/kartu):
  - Harga tiket per kategori (badge tier VIP/Reguler).
  - Fee jasa: matriks Layanan × Tier untuk tahap terpilih.
  - Booking slot (tidak dikembalikan bila gagal), early booking bila ada.
- **Syarat event** (accordion; buka otomatis di HP pertama kali) — gabungan
  `event.terms` + ringkasan aturan inti dari `docs/02` dalam bahasa awam:
  fee dibayar di awal; batal = fee hangus; gagal = refund dipotong booking slot;
  wajib pilih cadangan; tim otomatis pindah cadangan; kelalaian bayar VA = tidak
  refund.
- **Tombol "Pesan sekarang"** menempel di bawah layar HP (sticky).
  Tahap tutup → tombol nonaktif + info. Kuota penuh → "Masuk waiting list".

## 3. Form pesanan `/event/<slug>/pesan/`

Satu halaman dengan **4 langkah** (stepper di atas; Alpine.js untuk interaksi,
validasi tetap di server). Ringkasan biaya **live** di bawah (sticky di HP,
kolom kanan di desktop), dihitung ulang via endpoint HTMX
`/event/<slug>/pesan/hitung/` yang memanggil `services/pricing.py`
(tidak ada rumus di JavaScript).

**Langkah 1 — Data pemesan**
Nama lengkap, No. WA (validasi & normalisasi 62…), email, username IG,
perekomendasi (opsional), tahap (bila >1 tahap buka).

**Langkah 2 — Tiket**
- Kartu "Tiket #1" berisi:
  - Layanan: pilihan besar JASWAR / JASTIP dengan penjelasan 1 baris.
  - Jumlah tiket: stepper 1–4.
  - Kategori utama, cadangan 1, cadangan 2 (select; opsi yang sudah dipilih di
    kartu ini dinonaktifkan; harga tampil di opsi).
  - Data pemegang: field sesuai layanan (JASWAR lengkap, JASTIP nama + WA).
    Checkbox "Pemegang = saya (pemesan)".
  - No. membership bila tahap mewajibkan.
- Tombol "+ Tambah tiket untuk kategori/orang lain" (maks `max_lines_per_order`).
- Tombol hapus kartu, dan "Salin dari tiket sebelumnya" untuk kategori.

**Langkah 3 — Pembayaran tiket**
- Pilihan metode yang aktif di event, dengan penjelasan:
  - VA BCA / VA Mandiri — "Kamu bayar sendiri saat war. Wajib standby. Telat
    bayar = tiket hangus & fee tidak kembali."
  - Titip Bayar Admin — "Kamu titip uang harga tiket ke kami, paling lambat
    <pelunasan_deadline>. Nominal = kategori termahal pilihanmu × jumlah;
    selisih dikembalikan setelah war."
- Ringkasan: Fee jasa (per baris), early booking, potongan kode unik,
  **Tagihan sekarang**, dan (titip bayar) **Pelunasan nanti**.

**Langkah 4 — Cek & setuju**
- Ringkasan semua data (NIK tampil tersamar `•••• •••• •••• 1234`).
- Checkbox wajib: setuju syarat event & umum; setuju kebijakan privasi
  (data KTP dipakai untuk pembelian tiket & dihapus setelah event).
- Tombol "Kirim pesanan".

Perilaku:
- Draf disimpan di `localStorage` **kecuali** NIK, tanggal lahir, dan
  nomor membership. Tombol "Kosongkan form".
- Bila validasi server gagal, kembali ke langkah yang salah dengan pesan
  jelas di bawah field.
- Proteksi kirim ganda (token sekali pakai + tombol nonaktif saat kirim).
- Honeypot field anti-bot + rate limit 5 pesanan / 10 menit per IP.

## 4. Halaman sukses `/pesanan/<kode>/berhasil/`

- "Pesanan kamu tercatat! 🎉" + **kode pesanan besar** (tombol salin).
- Status: `MENUNGGU_FEE` → nominal transfer besar (tombol salin angka),
  rekening tujuan (bisa lebih dari satu, tombol salin nomor), batas waktu
  (hitung mundur), tombol **"Upload bukti sekarang"** (form inline) dan
  "Nanti saja".
- TITIP_BAYAR: dua pilihan "Bayar fee saja (Rp X)" / "Bayar sekaligus fee +
  pelunasan (Rp Y)".
- `WAITING_LIST` → penjelasan: belum perlu bayar; akan dikabari bila slot tersedia.
- Tombol "Simpan link lacak" (link bertoken) + tombol WA "Kirim link ini ke
  WhatsApp saya" (wa.me ke nomor customer sendiri, berisi link lacak).

## 5. Lacak `/lacak/` dan `/lacak/<kode>/`

Form masuk: kode pesanan + No. WA. Gagal → pesan umum.

Halaman lacak (urut dari atas):
1. **Kartu status**: label status besar + kalimat "Yang perlu kamu lakukan
   sekarang" (selalu satu aksi jelas, atau "Tidak ada, tunggu kabar dari kami").
2. **Banner VA** (hanya saat ada `VaNotice` AKTIF): bank, nomor VA (salin),
   nominal, hitung mundur, tombol "Sudah saya bayar". Auto-refresh 10 detik
   (HTMX polling) selama tahap `WAR`.
3. **Kartu tagihan** (bila ada yang harus dibayar): nominal, rekening, batas
   waktu, form upload bukti (nama pengirim, bank, tanggal, nominal, foto/PDF
   maks 10 MB). Setelah upload → status "sedang dicek".
4. **Tiket kamu**: per baris → per tiket: pemegang (nama), layanan, pilihan
   kategori, **hasil** (badge: Menunggu war / Dapat CAT X 🎉 / Tidak dapat),
   **penyerahan** (JASTIP: Menunggu penukaran → Gelang sudah ditukar → Siap
   diserahkan [metode, jadwal, lokasi/resi] → Sudah diserahkan; JASWAR: info
   penukaran + unduh e-tiket bila ada).
5. **Rincian biaya**: tagihan awal, pelunasan, pembayaran diterima, hasil
   final, refund/kekurangan, refund yang sudah ditransfer (lihat bukti).
6. **Rekening refund** (bila SALDO > 0): form bank, nomor, atas nama.
   Setelah diisi tampil tersamar + tombol ubah (sebelum diproses).
7. **Kirim VA hasil war mandiri** (bila `customer_va_enabled`, metode
   TITIP_BAYAR, tahap `WAR`): bank, nomor VA, nominal, batas bayar, screenshot.
8. **Timeline**: riwayat status publik.
9. **Ubah data pemegang** (sebelum `PROSES_WAR`).
10. **Batalkan pesanan** (sebelum `PROSES_WAR`): dialog konfirmasi yang
    menjelaskan konsekuensi persis (berapa yang hangus, berapa yang kembali),
    dihitung oleh `services/settlement.py`.
11. **Tulis testimoni** (status `SELESAI`, belum pernah kirim): rating bintang,
    teks, foto opsional, nama tampilan, izin publikasi.
12. Tombol WA admin dengan pesan otomatis "Halo kak, saya mau tanya pesanan
    DRM-XXXXXX".

## 6. Testimoni `/testimoni/`

- Grid kartu (masonry sederhana via CSS columns): nama tampilan, bintang,
  event, teks, foto (klik → lightbox), badge "Pembeli terverifikasi".
- Filter per event (select), urut terbaru, paginasi 12.
- Ringkasan di atas: jumlah testimoni, rata-rata rating.
- CTA: "Sudah pakai Dreamtify? Tulis testimoni dari halaman lacak pesananmu."

## 7. FAQ, Syarat, Privasi

Konten dari Pengaturan (`FaqItem`, `general_terms`, `privacy_policy`).
FAQ berbentuk accordion. Seed FAQ awal (bisa diubah admin):
- Apa beda JASWAR dan JASTIP?
- Kapan saya tahu tiket dapat atau tidak?
- Bagaimana kalau tidak dapat tiket? (refund dipotong booking slot)
- Kenapa harus pilih kategori cadangan?
- Apa itu titip bayar & kenapa nominalnya kategori termahal?
- Bisa pesan untuk teman / beberapa kategori? (bisa, tambah tiket di form)
- Bagaimana kalau saya batal?
- Apakah data KTP saya aman?
- Berapa lama refund diproses?

## 8. Halaman error

404 dan 500 bergaya brand (awan sedih), tombol kembali ke beranda dan WA admin.
