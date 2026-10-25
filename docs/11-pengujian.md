# 11 — Pengujian & Kriteria Terima

## 1. Tes otomatis (pytest)

Jalankan: `.venv\Scripts\python -m pytest` (DB tes MariaDB `test_dreamtify_dev`).
Bila MariaDB tidak tersedia di lingkungan pengembangan, `DJANGO_TEST_SQLITE=1`
boleh dipakai untuk tes unit **logika murni**, tetapi sebelum fase dianggap
selesai tes harus lulus di MariaDB.

Wajib ada (minimal):

| Area | Tes |
|---|---|
| Harga | 6 contoh di `docs/02` §4.5 menghasilkan angka persis |
| Harga | `FeeBasis.KATEGORI_UTAMA`, early booking, kode unik |
| Status | setiap transisi sah berhasil; transisi tidak sah → `InvalidTransition` |
| Status | verifikasi pembayaran memindahkan status sesuai §4.2 (kurang, pas, lebih, bayar sekaligus) |
| Kuota | 2 pesanan bersamaan untuk sisa kuota 1 → satu `MENUNGGU_FEE`, satu `WAITING_LIST` |
| Batas waktu | `run_periodic` membatalkan pesanan lewat `fee_deadline`; idempoten |
| Pembatalan | semua baris tabel §4.4 |
| Penyelesaian | pesanan otomatis `SELESAI` hanya bila semua syarat terpenuhi |
| Lacak | kode+WA benar → masuk; salah → pesan umum; rate limit aktif; token kedaluwarsa ditolak |
| Izin | customer A tidak bisa membuka pesanan/berkas customer B; Admin tidak bisa "Lihat NIK"; Owner bisa & tercatat |
| Enkripsi | NIK di DB tidak berupa teks asli; dekripsi benar; hash konsisten |
| Upload | file palsu (ekstensi .jpg isi teks) ditolak; > 10 MB ditolak; EXIF terbuang |
| Ekspor | judul kolom persis; NIK teks; NIK tersembunyi tanpa izin |
| Template WA | semua template default ter-render tanpa placeholder tersisa |
| Retensi | `purge_sensitive_data` hanya menyentuh event yang memenuhi syarat |

## 2. Skenario uji manual end-to-end (fase 14)

Jalankan dengan `dev.bat seed` lalu ikuti sebagai customer (di HP / mode HP
browser) dan admin:

1. **Event baru < 5 menit**: duplikat event contoh, ubah nama/tanggal/harga,
   buka tahap Presale.
2. **Pesanan multi-baris**: 2 VIP JASWAR untuk diri sendiri + 1 CAT 3 JASTIP
   untuk teman, metode Titip Bayar, pilih "bayar fee saja".
3. Upload bukti fee dari halaman sukses → admin verifikasi → status
   `MENUNGGU_PELUNASAN` → Kotak Kabar berisi `FEE_DITERIMA` + `TAGIHAN_PELUNASAN`.
4. Upload pelunasan dari halaman lacak (link bertoken) → verifikasi → `SIAP_WAR`.
5. Pesanan kedua metode VA BCA. Kuota diatur agar pesanan ketiga masuk
   waiting list; naikkan setelah pesanan lain dibatalkan.
6. **Mode War** di HP: mulai war, kirim VA ke pesanan VA, customer klik
   "Sudah saya bayar", isi hasil: sebagian secured, sebagian gagal.
7. Halaman lacak menampilkan hasil & refund yang benar; customer isi rekening;
   admin catat refund dengan bukti; customer lihat bukti.
8. Penyerahan: tiket JASTIP → ditukar → siap diserahkan (titik temu) →
   diserahkan. Tiket JASWAR → info dikirim.
9. Pesanan menjadi `SELESAI`; customer kirim testimoni; admin setujui; tampil
   di `/testimoni/`.
10. Ekspor Excel promotor & buka via link promotor; cocokkan kolom dengan
    `docs/07`.
11. Batal: pesanan baru dibatalkan customer setelah fee diterima → `HANGUS`,
    dialog menampilkan nominal yang benar.
12. **Produksi**: di Windows bersih (VM), `install.bat` → web hidup di 8383,
    restart Windows → web hidup lagi otomatis; task berkala & harian berjalan;
    backup tercipta.

## 3. Kriteria terima akhir

- Semua tes otomatis lulus di MariaDB.
- Semua 12 skenario manual berhasil tanpa error 500.
- Lighthouse (mode HP) halaman beranda & form pesanan: Performance ≥ 85,
  Accessibility ≥ 90.
- `check --deploy` bersih (kecuali peringatan HTTPS bila memang HTTP).
- Tidak ada NIK di `logs\`.
- `docs/PANDUAN-ADMIN.md` tersedia (dibuat di fase 14).
