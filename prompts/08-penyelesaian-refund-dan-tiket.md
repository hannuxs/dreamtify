# Fase 08 — Penyelesaian: Refund, Kekurangan & Penyerahan Tiket

## Baca dulu
`CLAUDE.md`, `ASUMSI-DAN-KEPUTUSAN.md` (A6), `docs/02-aturan-bisnis.md` §4.3,
§4.4, §9, `docs/05-dashboard-admin.md` §7, §8, `docs/04-halaman-publik.md` §5
(butir 3–6).

## Tujuan
Setelah war, admin bisa memproses semua refund & kekurangan bayar dan
mencatat penyerahan gelang (JASTIP) atau info tiket (JASWAR), sampai pesanan
otomatis berstatus `SELESAI`.

## Tugas
1. **Penyelesaian** `/kelola/penyelesaian/`:
   - Tab Refund: pesanan SALDO > 0 (semua status termasuk HANGUS/DIBATALKAN),
     rekening customer (tampil penuh untuk admin, audit), status "menunggu
     rekening", aksi "Catat refund" (nominal default = saldo, bukti,
     tanggal) → `record_refund`. Boleh bertahap.
   - Tab Kekurangan: SALDO < 0, tombol kabar.
   - Ekspor daftar refund (Excel: kode, nama, bank, no. rekening, atas nama,
     nominal) untuk transfer massal; setiap unduhan tercatat di AuditLog.
2. **Penyerahan** `/kelola/penyerahan/` sesuai `docs/05` §8:
   - JASTIP: aksi massal Ditukar → Siap diserahkan (metode, detail, sekali
     untuk banyak tiket) → Diserahkan (nama penerima, foto opsional).
   - JASWAR: "Kirim info" (upload e-tiket opsional, catatan; info penukaran
     dari `event.redemption_info`) → `INFO_DIKIRIM`.
   - Peringatan bila pesanan masih kekurangan bayar.
   - Ekspor "Daftar penyerahan gelang" (Excel untuk dibawa ke lokasi:
     kode, pemegang, WA, kategori, metode, detail, kolom tanda tangan kosong).
3. Halaman lacak: progres penyerahan per tiket, unduh e-tiket (berkas
   privat), bukti refund, tagihan kekurangan + upload.
4. `refresh_completion()` dipanggil setelah refund, pembayaran kekurangan
   diverifikasi, dan setiap perubahan penyerahan → `SELESAI` bila syarat terpenuhi.
5. Beranda tugas: kartu "Refund siap diproses", "Refund menunggu rekening",
   "Kekurangan bayar", "Tiket menunggu penyerahan".
6. Tes: refund bertahap sampai saldo 0 → SELESAI (bila penyerahan tuntas);
   pesanan HANGUS dengan sisa uang tiket muncul di antrian refund;
   kekurangan dibayar → saldo 0; JASWAR selesai dengan `INFO_DIKIRIM`;
   JASTIP baru selesai saat `DISERAHKAN`.

## Selesai bila
Semua pesanan simulasi war fase 07 bisa dibawa sampai `SELESAI`, dan halaman
lacak tiap customer menampilkan bukti refund / status gelang yang benar.

## Cara saya mengecek
1. Pakai pesanan dari fase 07. Sebagai customer, isi rekening refund.
2. Sebagai admin, catat refund dengan bukti → customer melihat bukti.
3. Tandai gelang JASTIP sampai Diserahkan → status pesanan Selesai.

## Penutup
Tes, `PROGRESS.md`, ringkasan. Jangan memulai fase 09.
