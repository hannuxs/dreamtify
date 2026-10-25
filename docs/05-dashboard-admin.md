# 05 — Dashboard Admin (`/kelola/`)

Prinsip: admin harus tahu **apa yang perlu dikerjakan sekarang** lintas semua
event, dan setiap tugas rutin bisa selesai dalam beberapa ketukan, termasuk
dari HP saat war.

Tata letak: sidebar di desktop; di HP bar navigasi bawah (Beranda · Pesanan ·
Verifikasi · War · Lainnya). Warna lebih tenang dari halaman publik, tabel padat
tapi terbaca (`docs/06`).

## Peta URL

| URL | Halaman | Peran |
|---|---|---|
| `/kelola/login/` | Login | — |
| `/kelola/` | Beranda tugas | Admin |
| `/kelola/event/` | Daftar event | Admin |
| `/kelola/event/baru/`, `/kelola/event/<id>/` | Form event (tab) | Admin |
| `/kelola/event/<id>/duplikat/` | Duplikat event | Admin |
| `/kelola/pesanan/` | Daftar pesanan | Admin |
| `/kelola/pesanan/<kode>/` | Detail pesanan | Admin |
| `/kelola/verifikasi/` | Antrian verifikasi pembayaran | Admin |
| `/kelola/waiting-list/` | Waiting list per tahap | Admin |
| `/kelola/war/<phase_id>/` | Mode War | Admin |
| `/kelola/penyelesaian/` | Refund & kekurangan | Admin |
| `/kelola/penyerahan/` | Penyerahan gelang & info e-tiket | Admin |
| `/kelola/kabar/` | Kotak Kabar (WA) | Admin |
| `/kelola/rekap/` | Rekap & ekspor | Admin |
| `/kelola/testimoni/` | Moderasi testimoni | Admin |
| `/kelola/pengaturan/` | Pengaturan (tab) | Owner |
| `/kelola/pengguna/` | Pengguna admin | Owner |
| `/kelola/log/` | Log aktivitas | Owner |
| `/kelola/sistem/` | Django admin bawaan (darurat) | Superuser |

## 1. Beranda tugas

- **Kartu angka tugas** (klik → halaman terfilter):
  Bukti menunggu verifikasi · Pesanan lewat batas pelunasan · Waiting list ·
  Refund siap diproses · Refund menunggu rekening customer · Kekurangan bayar ·
  Tiket menunggu penyerahan · Kabar belum dikirim · Testimoni menunggu.
- **Event aktif**: kartu per event/tahap → status tahap, hitung mundur war,
  kuota terpakai (progress bar), jumlah pesanan per status, tombol cepat
  (Pesanan, Mode War, Ekspor promotor).
- **Jadwal 7 hari**: daftar batas pelunasan & war mendatang.
- **Aktivitas terbaru** (10 baris AuditLog).

## 2. Event

**Daftar**: kartu/tabel event dengan status, tahap, tanggal; filter status;
tombol "Event baru", "Duplikat".

**Form event** (tab, simpan per tab):
1. *Info*: nama, slug (otomatis), artis, venue, kota, tanggal (teks + tanggal
   pertama), poster (upload + pratinjau), deskripsi, platform tiket, status.
2. *Tahap & jadwal*: daftar tahap (tambah/ubah/urut): nama, status, buka/tutup
   pesanan, waktu war, batas pelunasan, kuota, membership.
3. *Kategori*: tabel editable (nama, tier, harga, aktif, urutan) + tambah baris.
4. *Matriks fee*: grid per tahap → baris = layanan (JASWAR/JASTIP), kolom =
   tier (VIP/REGULER), sel = fee per tiket. Tombol "Salin dari tahap lain".
5. *Aturan*: layanan aktif, metode bayar aktif, maks baris, maks tiket per
   pemegang, jumlah cadangan wajib, dasar fee, booking slot, early booking,
   jendela bayar fee, kebijakan lewat batas pelunasan, kode unik, VA dari
   customer, fallback kategori, syarat event, info penukaran gelang.
6. *Promotor*: nama promotor, aktif/nonaktif link, tombol salin link,
   "Ganti link" (token baru), sertakan NIK (Owner saja).

Validasi publikasi: event tidak bisa `TAMPIL` + tahap `BUKA` bila belum ada
kategori aktif atau ada sel matriks fee yang kosong untuk layanan aktif.

**Duplikat event**: salin semua kecuali pesanan; nama "(salinan)", status
`DRAFT`, tanggal dikosongkan, token promotor baru.

**Batalkan event** (Owner): konfirmasi ketik nama event → semua pesanan
`DIBATALKAN` + `EVENT_BATAL` → masuk antrian refund penuh + kabar.

## 3. Pesanan

**Daftar**: tabel (HP: kartu) — kode, pemesan, event/tahap, jumlah tiket,
layanan, metode, status (badge warna), dibayar, saldo, dibuat.
Filter: event, tahap, status (multi), layanan, metode, "lewat batas",
"peringatan NIK ganda". Cari: kode, nama, WA, email, nama pemegang.
Aksi massal: tandai kabar, ekspor terpilih.

**Detail pesanan**:
- Kepala: kode, status, event/tahap, tombol aksi kontekstual (Verifikasi,
  Naikkan dari waiting list, Lepas slot, Batalkan, Buka di Mode War,
  Kirim kabar WA, Salin link lacak).
- Kontak pemesan (tombol WA).
- Baris tiket: pemegang (NIK tersamar; tombol "Lihat NIK" untuk Owner →
  tercatat `nik.reveal` di audit), pilihan kategori, slot + hasil + penyerahan.
- Keuangan: rincian §4 `docs/02` (tagihan awal, pelunasan, dibayar,
  final, saldo), daftar Payment (pratinjau bukti, status, siapa verifikasi).
- VaNotice, timeline publik + catatan internal, log audit pesanan.
- Form edit (sesuai aturan §11 `docs/02`), tombol "Hitung ulang tagihan".
- Tambah pembayaran manual (mis. customer kirim bukti lewat WA).

## 4. Antrian verifikasi

Satu halaman cepat:
- Daftar kiri (HP: atas) Payment `MENUNGGU`, urut terlama, filter event/jenis.
- Panel kanan: **bukti besar** (zoom, putar), data klaim customer, nominal yang
  diharapkan sistem, selisih (merah bila kurang), rekening tujuan.
- Input "Nominal diterima" (default = klaim), tombol **Terima** / **Tolak**
  (alasan wajib, pilihan cepat: "Bukti tidak terbaca", "Nominal tidak sesuai",
  "Dana belum masuk").
- Pintasan keyboard: `T` terima, `X` tolak, `J/K` berikutnya/sebelumnya.
- Setelah aksi langsung pindah ke berikutnya. Notifikasi otomatis dibuat.

## 5. Waiting list

Per tahap: kuota, terpakai, sisa. Daftar pesanan `WAITING_LIST` urut waktu
masuk, tombol "Naikkan" (nonaktif bila kuota tidak cukup), "Batalkan".
Juga daftar `MENUNGGU_PELUNASAN` yang lewat batas dengan tombol "Lepas slot"
(konfirmasi menampilkan dampak keuangan sesuai kebijakan event).

## 6. Mode War `/kelola/war/<phase_id>/` (dioptimalkan untuk HP)

- Kepala: nama event/tahap, jam war, tombol **Mulai war** / **Selesaikan war**,
  ringkasan: total tiket, secured, gagal, belum diisi.
- Peringatan pesanan yang belum `SIAP_WAR`.
- Filter cepat: semua / belum diisi / VA / titip bayar / JASWAR / JASTIP.
- Daftar kartu per pesanan (urut waktu pesan): kode, pemesan, metode, lalu
  per tiket: pemegang, layanan, pilihan (U / C1 / C2), dan tombol besar:
  **[Utama] [Cad 1] [Cad 2] [Lainnya…] [Gagal] [Gagal-cust]**.
  Satu ketukan = tersimpan (HTMX), kartu berubah warna, bisa dibatalkan
  (undo) selama 10 detik.
- Panel VA per pesanan (metode VA): form kecil bank, nomor VA, nominal, batas,
  centang tiket yang dicakup → simpan → tombol WA `VA_DIKIRIM` muncul.
  Badge "Customer bilang sudah bayar" saat `DIKLAIM_CUSTOMER`.
- Antrian VA dari customer (war mandiri): bank, nomor, nominal, screenshot,
  tombol "Sudah dibayar tim" → `LUNAS`.
- Auto-refresh daftar tiap 15 detik (tanpa mengganggu input yang sedang diketik).
- Mendukung beberapa admin sekaligus (simpan per tiket, cek konflik versi).

## 7. Penyelesaian

Tab **Refund**: pesanan SALDO > 0 → nominal, rekening customer (Owner/Admin
melihat penuh; tercatat audit), status rekening ("menunggu customer mengisi").
Aksi: "Catat refund" (nominal default = saldo, upload bukti, tanggal).
Tombol "Ingatkan isi rekening" (kabar WA).

Tab **Kekurangan**: pesanan SALDO < 0, nominal, tombol kabar `KEKURANGAN_BAYAR`.

Ekspor daftar refund (Excel) untuk transfer massal.

## 8. Penyerahan

Filter event/tahap/layanan/status penyerahan.
- JASTIP: daftar tiket SECURED → aksi massal "Tandai sudah ditukar",
  "Set siap diserahkan" (metode, detail jadwal/lokasi/resi, sekali untuk
  banyak tiket), "Tandai diserahkan" (nama penerima, foto opsional).
- JASWAR: aksi "Kirim info" (upload e-tiket opsional, catatan) → `INFO_DIKIRIM`.
- Setiap perubahan → timeline + kabar (`GELANG_SIAP`, `ETIKET_INFO`).

## 9. Kotak Kabar

Daftar Notification `PERLU_DIKIRIM` (filter event/jenis).
- Tiap baris: penerima, nomor, ringkasan pesan, tombol **"Kirim WA"** → membuka
  `https://wa.me/<nomor>?text=<pesan>` di tab baru dan menandai `TERKIRIM`.
  Tombol "Lewati" dan "Ubah pesan" (sebelum kirim).
- **Mode beruntun**: tombol "Mulai kirim beruntun" → menampilkan satu pesan
  per layar dengan tombol besar "Kirim & lanjut" (untuk blast setelah war).
- Email (bila diaktifkan) terkirim otomatis; Kotak Kabar hanya menampilkan
  status email.

## 10. Rekap & Ekspor

Pilih event + tahap:
- **Excel format promotor** (`docs/07`) — tombol unduh; centang "sertakan
  NIK" hanya untuk Owner.
- **Rekap ringkas**: permintaan per kategori utama, secured per kategori,
  per layanan, per metode.
- **Rekap keuangan**: fee diterima, pelunasan diterima, refund keluar, saldo
  tertahan, kekurangan, pendapatan fee final (Σ fee_final).
- Ekspor daftar refund, daftar penyerahan gelang (untuk dibawa ke lokasi).

## 11. Testimoni

Tab Menunggu / Tampil / Disembunyikan. Aksi: setujui, sembunyikan, jadikan
unggulan, edit teks (typo), hapus. Form "Tambah testimoni" (upload screenshot
chat, nama tampilan, event, rating).

## 12. Pengaturan (Owner)

Tab: Brand & kontak · Rekening · Syarat & privasi · FAQ (urut drag/tombol) ·
Template pesan (`docs/08`, dengan pratinjau placeholder) · Aturan default
(jendela bayar, booking slot, retensi) · Email SMTP (status saja; kredensial
di `.env`).

## 13. Pengguna & Log (Owner)

Pengguna: tambah/nonaktifkan admin, set peran, reset kata sandi.
Log: AuditLog dengan filter aksi, pengguna, tanggal, objek.
