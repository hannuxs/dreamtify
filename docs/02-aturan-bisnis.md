# 02 — Aturan Bisnis (sumber kebenaran logika)

Semua logika di dokumen ini diimplementasikan di `apps/orders/services/`
dan **wajib punya tes**. Nilai enum ditulis persis seperti di sini.

---

## 1. Konsep inti

```
Event (mis. "BIGBANG in Jakarta")
 ├─ SalePhase  (Presale, Gensale) — jadwal war, kuota, batas pelunasan
 ├─ TicketCategory (Duality Package, CAT 1 … CAT 6) — harga tiket, tier fee
 └─ FeeRule  (tahap × layanan × tier → fee per tiket)

Order (1 pemesan, 1 kode, 1 metode bayar tiket, 1 tahap)
 ├─ OrderLine  (= 1 isian Google Form lama: 1 pemegang tiket)
 │    ├─ layanan JASWAR/JASTIP, jumlah 1–4, kategori utama + cadangan 1 + cadangan 2
 │    └─ TicketSlot × jumlah  (hasil war & penyerahan per tiket)
 ├─ Payment  (FEE, PELUNASAN, KEKURANGAN masuk; REFUND keluar)
 ├─ VaNotice (VA yang dibayar saat war)
 └─ OrderTimeline (riwayat yang dilihat customer)
```

## 2. Enum

| Enum | Nilai |
|---|---|
| `ServiceType` | `JASWAR`, `JASTIP` |
| `FeeTier` | `VIP`, `REGULER` (urutan: VIP > REGULER) |
| `TicketPaymentMethod` | `VA_BCA`, `VA_MANDIRI`, `TITIP_BAYAR` |
| `EventStatus` | `DRAFT`, `TAMPIL`, `SELESAI`, `DIBATALKAN`, `ARSIP` |
| `PhaseStatus` | `DRAFT`, `BUKA`, `TUTUP`, `WAR`, `SELESAI` |
| `OrderStatus` | `WAITING_LIST`, `MENUNGGU_FEE`, `VERIFIKASI_FEE`, `MENUNGGU_PELUNASAN`, `VERIFIKASI_PELUNASAN`, `SIAP_WAR`, `PROSES_WAR`, `PENYELESAIAN`, `SELESAI`, `DIBATALKAN`, `HANGUS` |
| `CancelReason` | `LEWAT_BATAS_FEE`, `LEWAT_BATAS_PELUNASAN`, `BATAL_CUSTOMER`, `BATAL_ADMIN`, `EVENT_BATAL` |
| `SlotResult` | `MENUNGGU`, `SECURED`, `GAGAL`, `GAGAL_CUSTOMER` |
| `FulfillmentStatus` | `TIDAK_PERLU`, `MENUNGGU`, `DITUKAR`, `SIAP_DISERAHKAN`, `DISERAHKAN`, `INFO_DIKIRIM` |
| `HandoverMethod` | `AMBIL_DI_VENUE`, `TITIK_TEMU`, `KIRIM_EKSPEDISI` |
| `PaymentKind` | `FEE`, `PELUNASAN`, `KEKURANGAN`, `REFUND` |
| `PaymentStatus` | `MENUNGGU`, `DITERIMA`, `DITOLAK` |
| `VaStatus` | `AKTIF`, `DIKLAIM_CUSTOMER`, `LUNAS`, `KEDALUWARSA` |
| `VaSource` | `ADMIN` (dikirim tim saat war), `CUSTOMER` (customer war sendiri, minta dibayarkan) |
| `LatePelunasanPolicy` | `HANGUS`, `REFUND_KURANGI_BOOKING` |
| `FeeBasis` | `TIER_TERTINGGI` (default), `KATEGORI_UTAMA` |

Label tampilan untuk customer (pakai di template, bukan nilai enum):

| OrderStatus | Label customer |
|---|---|
| WAITING_LIST | Masuk waiting list |
| MENUNGGU_FEE | Menunggu pembayaran fee |
| VERIFIKASI_FEE | Bukti fee sedang dicek |
| MENUNGGU_PELUNASAN | Menunggu pelunasan tiket |
| VERIFIKASI_PELUNASAN | Bukti pelunasan sedang dicek |
| SIAP_WAR | Siap war 🎫 |
| PROSES_WAR | War sedang berlangsung |
| PENYELESAIAN | Hasil keluar — proses penyelesaian |
| SELESAI | Selesai ✨ |
| DIBATALKAN | Dibatalkan |
| HANGUS | Dibatalkan (fee hangus) |

## 3. Aturan baris tiket (OrderLine)

1. Satu pesanan berisi 1–`event.max_lines_per_order` baris (default 6).
2. Jumlah tiket per baris: 1–`event.max_tickets_per_holder` (default 4).
3. Kategori: `cat_primary` wajib; `cat_backup1` dan `cat_backup2` wajib sebanyak
   `event.required_backups` (default 2). Ketiganya harus **berbeda**. Hanya
   kategori aktif di event itu.
4. Data pemegang:
   - **JASWAR**: wajib nama lengkap (sesuai KTP), No. KTP (16 digit), jenis
     kelamin (L/P), tanggal lahir, email, No. WA, username IG.
     No. membership wajib bila `phase.membership_required`.
   - **JASTIP**: wajib nama + No. WA penerima gelang. Field lain opsional.
   - Tombol "Sama dengan data pemesan" mengisi otomatis dari kontak pemesan.
5. Jika NIK yang sama muncul lebih dari sekali di satu tahap (pesanan mana
   pun), tandai **peringatan** untuk admin (platform biasanya membatasi
   tiket per KTP). Tidak memblokir customer.

## 4. Rumus harga (`services/pricing.py`)

Semua angka integer rupiah. Notasi untuk satu baris `L`:
`q` = jumlah tiket, `s` = layanan, `C` = himpunan kategori pilihan (utama + cadangan),
`fee(tahap, s, tier)` = nilai dari `FeeRule`, `harga(c)` = harga tiket kategori `c`.

### 4.1 Saat pesanan dibuat (snapshot)

```
tier_dasar(L)        = tier tertinggi di C            (FeeBasis.TIER_TERTINGGI)
                       atau tier(kategori utama)      (FeeBasis.KATEGORI_UTAMA)
fee_awal(L)          = q × fee(tahap, s, tier_dasar)
harga_dasar(L)       = q × max(harga(c) untuk c di C)
early_booking(L)     = q × event.early_booking_per_ticket   (hanya bila metode TITIP_BAYAR; default 0)

TAGIHAN_AWAL         = Σ fee_awal + Σ early_booking − potongan_kode_unik
TAGIHAN_PELUNASAN    = Σ harga_dasar − Σ early_booking      (hanya TITIP_BAYAR; selain itu 0)
TOTAL_SEBELUM_WAR    = TAGIHAN_AWAL + TAGIHAN_PELUNASAN
```

- Nilai per tiket (`fee_per_ticket_snapshot`, `price_basis_per_ticket_snapshot`,
  `tier_snapshot`) disimpan di `OrderLine`. Perubahan harga event **tidak**
  mengubah pesanan lama, kecuali admin menekan "Hitung ulang" (tercatat audit).
- `potongan_kode_unik`: bila `event.unique_code_enabled`, sistem memberi angka
  1–499 yang unik di antara pesanan berstatus `MENUNGGU_FEE` event itu.
  Nominal transfer = tagihan − kode. Default mati.

### 4.2 Status setelah pembayaran diverifikasi

`dibayar` = Σ Payment masuk berstatus `DITERIMA` (FEE + PELUNASAN + KEKURANGAN).

```
jika dibayar ≥ TOTAL_SEBELUM_WAR            → SIAP_WAR
jika dibayar ≥ TAGIHAN_AWAL (TITIP_BAYAR)   → MENUNGGU_PELUNASAN (tampilkan sisa)
selain itu                                   → MENUNGGU_FEE (tampilkan "kurang Rp X")
```

Customer TITIP_BAYAR boleh memilih **"Bayar sekaligus"** (fee + pelunasan dalam
1 transfer); aturan di atas otomatis menanganinya.

### 4.3 Setelah hasil war (final) — `services/settlement.py`

Per tiket (TicketSlot) `k` pada baris `L`:

| Hasil | fee_final(k) | harga_final(k) |
|---|---|---|
| `SECURED` di kategori `c` | `fee(tahap, s, tier(c))` | `harga(c)` bila TITIP_BAYAR, selain itu 0 |
| `GAGAL` | `min(event.booking_slot_fee, fee_awal per tiket)` | 0 |
| `GAGAL_CUSTOMER` | fee_awal per tiket (tidak direfund) | 0 |

```
TAGIHAN_FINAL        = Σ fee_final + Σ harga_final − potongan_kode_unik
SALDO                = dibayar − Σ REFUND berstatus DITERIMA − TAGIHAN_FINAL
SALDO > 0  → customer berhak refund sebesar SALDO
SALDO < 0  → customer kurang bayar |SALDO| (Payment KEKURANGAN)
SALDO = 0  → beres
```

Catatan: early booking adalah cicilan harga tiket yang dibayar di awal. Uangnya
sudah masuk `dibayar`, dan untuk tiket SECURED harganya sudah tercakup penuh di
`harga_final`, sehingga tidak dihitung dua kali. Untuk tiket gagal, early
booking otomatis ikut direfund. Tes wajib memastikan ini.

`SECURED` boleh di kategori di luar pilihan (aturan "semua habis → kategori
apa pun"). Jika lebih mahal dari `harga_dasar`, hasilnya `SALDO < 0`.

### 4.4 Pembatalan

| Status akhir | Kapan | TAGIHAN_FINAL |
|---|---|---|
| `DIBATALKAN` + `LEWAT_BATAS_FEE` | belum ada uang diterima, lewat batas bayar fee | 0 |
| `DIBATALKAN` + `BATAL_CUSTOMER` | customer batal **sebelum** ada uang diterima | 0 |
| `HANGUS` + `BATAL_CUSTOMER` | customer batal **setelah** fee diterima, sebelum `PROSES_WAR` | Σ fee_awal + Σ early_booking (uang harga tiket dikembalikan) |
| `HANGUS` + `LEWAT_BATAS_PELUNASAN` | admin "Lepas slot", kebijakan event `HANGUS` | Σ fee_awal + Σ early_booking |
| `DIBATALKAN` + `LEWAT_BATAS_PELUNASAN` | admin "Lepas slot", kebijakan `REFUND_KURANGI_BOOKING` | min(dibayar, q_total × booking_slot_fee) |
| `DIBATALKAN` + `BATAL_ADMIN` / `EVENT_BATAL` | admin membatalkan / konser batal | 0 (refund penuh) |

Customer **tidak bisa** membatalkan sendiri sejak `PROSES_WAR`.
Antrian refund berbasis **SALDO > 0**, apa pun statusnya (termasuk `HANGUS`).

### 4.5 Contoh wajib dijadikan tes

Data contoh (event fanmeet): tahap Presale. Harga tiket: Duality Package
Rp3.500.000 (tier VIP), CAT 1 Rp2.500.000 (REGULER), CAT 2 Rp2.000.000
(REGULER), CAT 3 Rp1.500.000 (REGULER). Fee Presale: JASWAR VIP 250.000,
JASWAR REGULER 200.000, JASTIP VIP 300.000, JASTIP REGULER 250.000.
Booking slot 50.000/tiket. Kode unik mati. Early booking 0.

**Contoh 1 — sebagian beda kategori.** 1 baris JASWAR, q=2, pilihan Duality /
CAT 1 / CAT 2, TITIP_BAYAR.
- TAGIHAN_AWAL = 2 × 250.000 = **500.000**
- TAGIHAN_PELUNASAN = 2 × 3.500.000 = **7.000.000** → dibayar 7.500.000
- Hasil: tiket 1 SECURED Duality, tiket 2 SECURED CAT 1
- TAGIHAN_FINAL = (250.000 + 200.000) + (3.500.000 + 2.500.000) = 6.450.000
- SALDO = 7.500.000 − 6.450.000 = **refund 1.050.000**

**Contoh 2 — gagal semua.** Sama dengan contoh 1, kedua tiket GAGAL.
- TAGIHAN_FINAL = 2 × 50.000 = 100.000 → **refund 7.400.000**

**Contoh 3 — VA, kelalaian customer.** 1 baris JASTIP, q=1, pilihan CAT 3 /
CAT 2 / CAT 1 (semua REGULER), VA_BCA. TAGIHAN_AWAL = 250.000. Customer tidak
membayar VA tepat waktu → GAGAL_CUSTOMER.
- TAGIHAN_FINAL = 250.000 → **SALDO 0, tidak ada refund**

**Contoh 4 — dua baris, beliin teman.** Baris A: JASWAR q=2 Duality/CAT1/CAT2
(pemegang: pemesan). Baris B: JASTIP q=1 CAT3/CAT2/CAT1 (pemegang: teman).
Metode TITIP_BAYAR.
- TAGIHAN_AWAL = 2×250.000 + 1×250.000 = **750.000**
- TAGIHAN_PELUNASAN = 2×3.500.000 + 1×2.500.000 = **9.500.000**
  (baris B memakai harga termahal di pilihannya = CAT 1)
- Hasil: A1 SECURED Duality, A2 GAGAL, B1 SECURED CAT 3
- fee_final = 250.000 + 50.000 + 250.000 = 550.000;
  harga_final = 3.500.000 + 0 + 1.500.000 = 5.000.000; TAGIHAN_FINAL = 5.550.000
- SALDO = 10.250.000 − 5.550.000 = **refund 4.700.000**

**Contoh 5 — kategori lebih mahal (fallback).** Baris JASWAR q=1 CAT3/CAT2/CAT1,
TITIP_BAYAR, dibayar 200.000 + 2.500.000. Semua pilihan habis, tim mengamankan
Duality.
- TAGIHAN_FINAL = 250.000 + 3.500.000 = 3.750.000 → SALDO −1.050.000 →
  **kekurangan 1.050.000**

**Contoh 6 — batal setelah lunas.** Contoh 1 dibatalkan customer sebelum war
(HANGUS). TAGIHAN_FINAL = 500.000 → **refund 7.000.000**.

## 5. Mesin status (`services/transitions.py`)

Hanya transisi di tabel ini yang diizinkan. Transisi lain → `InvalidTransition`.

| Dari | Ke | Pemicu | Oleh |
|---|---|---|---|
| (baru) | `MENUNGGU_FEE` | pesanan dibuat & kuota cukup | sistem |
| (baru) | `WAITING_LIST` | pesanan dibuat & kuota tidak cukup | sistem |
| `WAITING_LIST` | `MENUNGGU_FEE` | "Naikkan dari waiting list" (cek kuota) | admin |
| `WAITING_LIST` | `DIBATALKAN` | batal oleh customer/admin, atau tahap ditutup admin | customer/admin |
| `MENUNGGU_FEE` | `VERIFIKASI_FEE` | upload bukti transfer | customer/admin |
| `MENUNGGU_FEE` | `DIBATALKAN` | lewat `fee_deadline` tanpa bukti (tugas berkala) / batal | sistem/customer |
| `VERIFIKASI_FEE` | `MENUNGGU_FEE` / `MENUNGGU_PELUNASAN` / `SIAP_WAR` | verifikasi (aturan 4.2), atau tolak → `MENUNGGU_FEE` | admin |
| `MENUNGGU_PELUNASAN` | `VERIFIKASI_PELUNASAN` | upload bukti | customer/admin |
| `VERIFIKASI_PELUNASAN` | `MENUNGGU_PELUNASAN` / `SIAP_WAR` | verifikasi / tolak | admin |
| `MENUNGGU_PELUNASAN` | `HANGUS` / `DIBATALKAN` | "Lepas slot" setelah lewat batas (kebijakan 4.4) | admin |
| `MENUNGGU_*`, `VERIFIKASI_*`, `SIAP_WAR` | `HANGUS` / `DIBATALKAN` | customer batal (4.4) | customer |
| semua kecuali `SELESAI` | `DIBATALKAN` + `BATAL_ADMIN`/`EVENT_BATAL` | admin batalkan pesanan / event | admin (Owner) |
| `SIAP_WAR` | `PROSES_WAR` | "Mulai war" untuk tahapnya | admin |
| `PROSES_WAR` | `PENYELESAIAN` | semua slot punya hasil & masih ada saldo/penyerahan | sistem |
| `PROSES_WAR` / `PENYELESAIAN` | `SELESAI` | semua slot punya hasil, semua penyerahan tuntas, SALDO = 0, tidak ada pembayaran `MENUNGGU` | sistem |

Setiap transisi menulis: `OrderTimeline` (pesan ramah customer), `AuditLog`
(siapa, kapan, dari→ke), dan `Notification` sesuai `docs/08`.

Upload bukti saat status `PENYELESAIAN` dengan SALDO < 0 → Payment
`KEKURANGAN` (status order tetap `PENYELESAIAN`).

## 6. Kuota & waiting list (`services/quota.py`)

- Kuota ada di **tahap** (`SalePhase.slot_quota`, satuan tiket; kosong = tanpa batas).
- Terpakai = Σ jumlah tiket pesanan di tahap itu dengan status:
  `MENUNGGU_FEE`, `VERIFIKASI_FEE`, `MENUNGGU_PELUNASAN`, `VERIFIKASI_PELUNASAN`,
  `SIAP_WAR`, `PROSES_WAR`, `PENYELESAIAN`, `SELESAI`.
- Pembuatan pesanan dan "Naikkan dari waiting list" memakai transaksi +
  `select_for_update` pada baris `SalePhase` agar tidak terjadi rebutan.
- Pesanan waiting list **tidak membayar** sampai dinaikkan (lihat C7).
- Saat dinaikkan: `fee_deadline = sekarang + event.fee_payment_window_hours`.
- Halaman event menampilkan "Sisa ±N slot" atau "Kuota penuh — kamu akan
  masuk waiting list".

## 7. Batas waktu

| Batas | Nilai |
|---|---|
| `Order.fee_deadline` | `min(dibuat + event.fee_payment_window_hours (default 24 jam), phase.war_at − 2 jam)` |
| `SalePhase.pelunasan_deadline` | diisi admin (form lama: H-2 pukul 19.00 WIB; titip bayar maks H-1) |
| `SalePhase.order_close_at` | setelah ini form pesanan tahap itu tertutup otomatis |

Tugas berkala (tiap 15 menit, lihat `docs/10`):
1. `MENUNGGU_FEE` lewat `fee_deadline` tanpa pembayaran → `DIBATALKAN` (`LEWAT_BATAS_FEE`).
2. Pengingat: 3 jam sebelum `fee_deadline` → Notification `PENGINGAT_FEE`.
3. Pengingat: 24 jam sebelum `pelunasan_deadline` → `PENGINGAT_PELUNASAN`.
4. `MENUNGGU_PELUNASAN` lewat batas → **ditandai** "Lewat batas" di dashboard
   (tidak otomatis dibatalkan; admin menekan "Lepas slot").
5. `VaNotice` `AKTIF` lewat `expires_at` → `KEDALUWARSA`.
6. Tahap dengan `order_close_at` lewat → status `TUTUP` bila masih `BUKA`.

Semua tugas **idempoten** (aman dijalankan berulang).

## 8. Prosedur war

1. Admin membuka **Mode War** untuk satu tahap, menekan **Mulai war**:
   tahap → `WAR`; semua pesanan `SIAP_WAR` di tahap itu → `PROSES_WAR`.
   Pesanan yang belum siap ditampilkan sebagai peringatan (tidak ikut).
2. Daftar tiket diurutkan berdasarkan waktu pesanan (siapa cepat dia dapat),
   menampilkan pilihan kategori & layanan tiap baris.
3. **Pesanan VA**: admin mengisi `VaNotice` (bank, nomor VA, nominal, batas
   bayar, tiket mana yang dicakup). Halaman lacak customer langsung menampilkan
   banner VA (auto-refresh 10 detik) + tombol "Sudah saya bayar"
   (→ `DIKLAIM_CUSTOMER`). Admin juga mendapat tombol WA template `VA_DIKIRIM`.
4. **Pesanan TITIP_BAYAR**: tim membayar sendiri. Bila customer mengirim VA hasil
   war mandiri (`VaSource.CUSTOMER`, fitur bisa dimatikan per event), muncul di
   antrian Mode War.
5. Admin mengisi hasil per tiket: tombol cepat **Utama / Cadangan 1 /
   Cadangan 2 / Lainnya…** (= SECURED kategori itu), **Gagal**,
   **Gagal (customer)**; opsional nomor/kode tiket.
6. Saat semua tiket sebuah pesanan berhasil diisi → hitung penyelesaian (4.3) →
   status `PENYELESAIAN` atau `SELESAI` → Notification `HASIL_SECURED` /
   `HASIL_SEBAGIAN` / `HASIL_GAGAL`.
7. **Selesaikan war**: tahap → `SELESAI`. Tiket yang masih `MENUNGGU` harus
   diisi dulu, atau admin memilih "Tandai sisa sebagai Gagal" (konfirmasi).

## 9. Penyelesaian & penyerahan

**Refund** (SALDO > 0)
1. Customer mengisi rekening refund (bank, nomor, atas nama) di halaman lacak.
2. Antrian refund admin menampilkan nominal + rekening; admin transfer, upload
   bukti, simpan → Payment `REFUND` `DITERIMA`. Boleh bertahap.
3. Customer melihat bukti refund di halaman lacak.

**Kekurangan** (SALDO < 0)
- Halaman lacak menampilkan tagihan kekurangan + upload bukti (Payment
  `KEKURANGAN`). Penyerahan gelang diberi peringatan "belum lunas".

**Penyerahan per tiket SECURED**
- `JASTIP`: `MENUNGGU` → `DITUKAR` (gelang sudah ditukar, foto opsional) →
  `SIAP_DISERAHKAN` (metode `AMBIL_DI_VENUE` / `TITIK_TEMU` / `KIRIM_EKSPEDISI`,
  jadwal/lokasi atau no. resi) → `DISERAHKAN` (nama penerima, foto opsional).
- `JASWAR`: `MENUNGGU` → `INFO_DIKIRIM` (e-tiket/kode booking opsional +
  instruksi penukaran gelang dari `event.redemption_info`). Customer menukar sendiri.
- Tiket GAGAL / GAGAL_CUSTOMER: `TIDAK_PERLU`.

Pesanan otomatis `SELESAI` bila syarat di tabel transisi terpenuhi; lalu
Notification `SELESAI_MINTA_TESTIMONI`.

## 10. Akses lacak pesanan

- Masuk dengan **kode pesanan + nomor WA** (dinormalisasi ke format `62…`).
  Cocok → simpan izin di session (berlaku 12 jam) untuk kode itu.
- Link langsung `/lacak/<kode>/?t=<token>`: token bertanda tangan
  (`django.core.signing`, berlaku 30 hari) dikirim di halaman sukses & pesan WA.
- Rate limit: 10 percobaan / 15 menit per IP. Pesan gagal selalu umum
  ("Kode atau nomor WA tidak cocok").
- Kode pesanan: `DRM-` + 6 karakter dari `23456789ABCDEFGHJKMNPQRSTUVWXYZ`.

## 11. Perubahan data

- Customer boleh **mengubah data pemegang** (bukan kategori/jumlah) selama
  status sebelum `PROSES_WAR`. Tercatat di audit & timeline admin.
- Admin boleh mengubah apa pun sebelum `PROSES_WAR`; perubahan kategori/jumlah
  memicu hitung ulang tagihan (dengan konfirmasi & audit).
- Setelah `PROSES_WAR`, hanya Owner yang bisa koreksi, dengan alasan wajib.
