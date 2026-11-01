# Panduan Admin Dreamtify

Untuk pemilik (Owner) dan admin. Halaman admin ada di `/kelola/`, nyaman dipakai dari HP.

**Owner** bisa semuanya. **Admin** mengurus pekerjaan harian, tetapi tidak bisa melihat NIK lengkap, mengubah
pengaturan, melihat rekap keuangan, atau mengelola pengguna.

Halaman **Beranda tugas** menampilkan yang perlu dikerjakan hari ini. Mulai dari sana setiap hari.

## 1. Membuat event

**Cara tercepat, duplikat event lama:** buka Event, pilih event, tekan Duplikat. Salinannya berstatus Draf dengan
tanggal kosong dan link promotor baru.

Lalu isi tab demi tab:

| Tab | Isi |
|---|---|
| Info | Nama, tanggal, venue, poster |
| Tahap | Presale/Gensale: waktu buka, tutup, war, batas pelunasan, kuota slot |
| Kategori | Nama, harga, tier fee (VIP atau Reguler) |
| Fee | Fee per tiket untuk tiap layanan dan tier |
| Aturan | Layanan aktif, metode bayar, booking slot, jumlah cadangan |
| Promotor | Link rahasia dan izin NIK |

Daftar periksa di samping menunjukkan yang kurang. Ubah status event ke **Tampil** dan tahap ke **Buka** agar muncul
di web.

## 2. Memverifikasi pembayaran

Buka **Verifikasi**. Di layar terlihat bukti, nominal yang diharapkan, dan klaim customer.

- Sesuai: **Terima**. Isi nominal yang benar-benar masuk.
- Tidak sesuai: **Tolak** dan tulis alasan. Customer bisa mengirim ulang.

Di laptop ada pintasan keyboard: `T` terima, `X` tolak, `J` berikutnya, `K` sebelumnya.

Status pesanan berubah sendiri, dan kabar untuk customer disiapkan di Kotak Kabar.

Bila customer mengirim bukti lewat WA, catat dari detail pesanan.

## 3. Waiting list dan lepas slot

Buka **Waiting list**.

- **Naikkan** memindahkan pesanan ke status menunggu fee. Tombolnya hanya aktif bila kuota cukup.
- **Lepas slot** dipakai untuk pesanan yang lewat batas pelunasan. Sistem hanya menandainya, keputusan tetap di admin.

## 4. Hari war (dari HP)

**Sebelum war:** buka **Mode War**, pilih tahap, cek daftar "belum siap".

1. Tekan **Mulai war**. Pesanan siap war masuk daftar, dan halaman lacak customer ikut berubah.
2. Untuk metode VA, buka "Kirim VA ke customer" di kartu pesanan: isi bank, nomor VA, nominal, batas waktu, lalu Simpan.
3. Tekan **Kirim WA** di kartu itu agar customer langsung tahu.
4. Bila customer menekan "Sudah saya bayar", tandanya muncul di kartu. Setelah dicek, tekan **Tandai lunas**.
5. Isi hasil tiap tiket dengan satu ketukan:
   - **Utama / Cad 1 / Cad 2**: dapat kategori itu.
   - **Lainnya**: dapat kategori lain, atau isi kode tiket.
   - **Gagal**: tiket tidak didapat.
   - **Gagal customer**: VA tidak dibayar, fee tidak kembali.
6. Salah tekan? **Undo** tersedia 10 detik. Setelah itu pakai **Ubah hasil** selama war belum selesai.
7. Selesai, tekan **Selesaikan war**. Sisa tiket kosong bisa ditandai Gagal sekaligus.

Halaman memuat ulang sendiri tiap 15 detik, jadi beberapa admin bisa bekerja bersama. Bila dua admin mengisi tiket
yang sama, isian kedua ditolak agar tidak saling menimpa.

## 5. Mengabari customer

WhatsApp dikirim manual lewat satu tombol. Buka **Kotak Kabar**:

- **Kirim WA** membuka WhatsApp dengan pesan yang sudah terisi. Tinggal tekan kirim.
- Pesan bisa diubah dulu, atau dilewati.
- **Mulai kirim beruntun** menampilkan pesan satu per satu, cara tercepat bila banyak.

Kabar sebelum war yang belum terkirim otomatis dibuang saat war dimulai karena sudah tidak relevan.

## 6. Refund dan kekurangan

Buka **Penyelesaian**.

**Refund:** nominal sudah dihitung sistem. Bila rekening belum diisi customer, tekan "Ingatkan isi rekening". Setelah
mentransfer, buka "Catat refund", isi nominal, tanggal, dan bukti. Boleh bertahap. Customer melihat buktinya di
halaman lacak.

**Kekurangan:** tab ini berisi pesanan yang kategori didapatnya lebih mahal. Tekan "Kirim kabar kekurangan".

## 7. Penyerahan gelang

Buka **Penyerahan**, centang tiket, pilih aksi:

- **JASTIP:** Tandai ditukar, lalu Siap diserahkan (wajib metode), lalu Diserahkan (wajib nama penerima, foto opsional).
- **JASWAR:** Kirim info penukaran. E-tiket bisa dilampirkan bila hanya 1 tiket dipilih.

"Daftar penyerahan gelang" di Rekap bisa dicetak untuk dibawa ke lokasi.

Pesanan otomatis **Selesai** bila hasil, uang, dan penyerahan semuanya beres.

## 8. Ekspor dan promotor

Buka **Rekap & Ekspor**, pilih event dan tahap.

- **Unduh Excel**: format sama persis dengan Google Form lama. Centang "Sertakan No. KTP" hanya tersedia untuk Owner.
- **Link promotor**: di Event, tab Promotor, aktifkan lalu salin link. Promotor bisa mengunduh sendiri kapan saja.
- **Ganti link** mematikan link lama. Menonaktifkan link hanya menutup halamannya; link bukti transfer di Excel lama
  tetap terbuka sampai link diganti.
- NIK ikut di link promotor hanya bila Owner mengizinkan.

Owner juga melihat **Rekap keuangan**. "Saldo tertahan" berarti hak refund yang belum ditransfer ditambah uang pesanan
yang hasil war-nya belum final.

## 9. Testimoni

Customer mengirim testimoni dari halaman lacak setelah pesanan selesai. Buka **Testimoni**:

- **Setujui** agar tampil di web. **Jadikan unggulan** agar tampil di beranda.
- **Sembunyikan**: testimoni dan fotonya hilang dari web.
- **Tambah testimoni**: unggah screenshot chat, langsung tampil.

## 10. Pengaturan (Owner)

**Pengaturan** berisi brand dan kontak, rekening, syarat dan privasi, FAQ, template pesan, dan aturan default.
**Pengguna** untuk menambah admin. **Log aktivitas** mencatat siapa melakukan apa.

Saat mengedit template, peringatan muncul bila ada `{placeholder}` yang salah ketik. Tombol default mengembalikan isi awal.

## 11. Yang dikerjakan sistem sendiri

| Kapan | Apa |
|---|---|
| Tiap 15 menit | Membatalkan pesanan yang lewat batas bayar fee |
| | Menyiapkan pengingat fee (3 jam sebelum batas) dan pelunasan (24 jam sebelum batas) |
| | Menandai lewat batas pelunasan, VA kedaluwarsa, menutup tahap yang waktunya habis |
| Tiap hari 02.30 | Menghapus NIK, tanggal lahir, dan file sensitif 30 hari setelah event selesai |
| | Backup database dan file |

## 12. Kalau ada masalah

| Masalah | Yang dilakukan |
|---|---|
| Web tidak bisa dibuka | Di server, PowerShell Administrator: `scripts\layanan.ps1 status`, lalu `restart`. Lihat `logs` |
| Lupa sandi admin | Owner mereset di menu Pengguna |
| Lupa sandi Owner | Di server: `scripts\tugas.bat changepassword nama-owner` |
| Terkunci setelah salah sandi | Tunggu 15 menit |
| Data hilang atau rusak | Pulihkan dari backup, lihat `docs/INSTALASI-SERVER.md` |
| Ganti server database | Ubah `.env`, lalu `scripts\layanan.ps1 restart`, lihat `docs/INSTALASI-SERVER.md` |

Simpan salinan file `.env` di tempat aman. Tanpa itu, NIK dan rekening tidak bisa dibaca lagi.
