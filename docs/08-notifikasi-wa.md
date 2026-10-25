# 08 — Notifikasi & Template Pesan WhatsApp

## 1. Cara kerja

- Setiap kejadian penting membuat baris `Notification` lewat
  `notifications.services.enqueue(order, key, context)`. Dipanggil dari
  `orders/services/transitions.py` (dan dari aksi Mode War / penyerahan).
- `dedupe_key` mencegah kabar ganda (mis. `DRM-ABC123:HASIL`).
- Channel default **WA manual**: admin mengirim dari Kotak Kabar
  (`docs/05` §9) dengan tombol `wa.me`. Teks di-URL-encode, nomor tanpa `+`.
- Channel **EMAIL** otomatis bila `SiteSetting.email_notifications_enabled`,
  template `send_email=True`, dan customer punya email (SMTP dari `.env`).
- Antarmuka backend `notifications/backends.py`:
  `ManualWhatsAppBackend` (default), `EmailBackend`, dan kelas kosong
  `HttpWhatsAppGatewayBackend` (stub, belum aktif) agar kelak bisa
  memakai gateway berbayar tanpa mengubah pemanggil.
- Halaman lacak tetap sumber utama; pesan WA selalu menyertakan `{link_lacak}`.

## 2. Placeholder

| Placeholder | Isi |
|---|---|
| `{nama}` | nama pemesan (kata pertama) |
| `{kode}` | kode pesanan |
| `{event}` | nama event |
| `{tahap}` | nama tahap |
| `{nominal}` | nominal yang relevan, format `Rp 1.250.000` |
| `{batas_waktu}` | "Sen, 14 Sep 2026 19.00 WIB" |
| `{rekening}` | daftar rekening aktif (multi-baris) |
| `{link_lacak}` | link lacak bertoken (`SITE_URL` + `/lacak/<kode>/?t=…`) |
| `{ringkasan_tiket}` | daftar tiket (pemegang · kategori) |
| `{ringkasan_hasil}` | per tiket: "✅ CAT 1 a.n. Rina", "❌ Tidak dapat a.n. Dodi" |
| `{va_bank}`, `{va_nomor}`, `{va_batas}` | info VA |
| `{alasan}` | alasan penolakan bukti |
| `{detail_penyerahan}` | metode, jadwal, lokasi / no. resi |
| `{brand}` | "Dreamtify" |

Template yang memakai placeholder tak dikenal → tampilkan peringatan di
halaman Pengaturan (tes wajib: render semua template default tanpa error).

## 3. Template default (seed, bisa diubah Owner)

| Key | Kapan dibuat | Email? |
|---|---|---|
| `PESANAN_DIBUAT` | pesanan baru (`MENUNGGU_FEE`) — **tidak** dimasukkan Kotak Kabar (customer sudah melihat halaman sukses); hanya email | ya |
| `WAITING_LIST_MASUK` | pesanan baru `WAITING_LIST` (hanya email) | ya |
| `WAITING_LIST_NAIK` | dinaikkan dari waiting list | ya |
| `PENGINGAT_FEE` | 3 jam sebelum `fee_deadline` | ya |
| `FEE_DITERIMA` | fee diverifikasi | ya |
| `BUKTI_DITOLAK` | bukti ditolak | ya |
| `TAGIHAN_PELUNASAN` | masuk `MENUNGGU_PELUNASAN` (bila belum bayar sekaligus) | ya |
| `PENGINGAT_PELUNASAN` | 24 jam sebelum batas pelunasan | ya |
| `SIAP_WAR` | masuk `SIAP_WAR` | ya |
| `VA_DIKIRIM` | admin membuat VaNotice | tidak (mendesak → WA) |
| `HASIL_SECURED` | semua tiket SECURED | ya |
| `HASIL_SEBAGIAN` | sebagian SECURED | ya |
| `HASIL_GAGAL` | semua gagal | ya |
| `REFUND_ISI_REKENING` | SALDO > 0 dan rekening belum diisi | ya |
| `REFUND_SELESAI` | refund dicatat | ya |
| `KEKURANGAN_BAYAR` | SALDO < 0 | ya |
| `GELANG_SIAP` | JASTIP `SIAP_DISERAHKAN` | ya |
| `ETIKET_INFO` | JASWAR `INFO_DIKIRIM` | ya |
| `DIBATALKAN` | dibatalkan (alasan apa pun) | ya |
| `SELESAI_MINTA_TESTIMONI` | pesanan `SELESAI` | ya |

Contoh isi (gaya: ramah, ringkas, sapaan "kak", emoji secukupnya):

**FEE_DITERIMA**
```
Halo kak {nama} ☁️
Pembayaran fee untuk pesanan *{kode}* ({event} – {tahap}) sudah kami terima. Slot kakak aman!

Langkah berikutnya bisa dicek di sini:
{link_lacak}

— {brand}
```

**VA_DIKIRIM**
```
Kak {nama}, VA untuk pesanan *{kode}* sudah keluar! ⏰
Bank: {va_bank}
No. VA: *{va_nomor}*
Nominal: *{nominal}*
Bayar sebelum: *{va_batas}*

Setelah bayar, tekan "Sudah saya bayar" di:
{link_lacak}
Telat bayar = tiket hangus & fee tidak kembali ya kak 🙏
```

**HASIL_SEBAGIAN**
```
Halo kak {nama}, hasil war {event} untuk pesanan *{kode}*:
{ringkasan_hasil}

Kelebihan bayar akan kami refund. Mohon isi rekening refund di:
{link_lacak}
```

**BUKTI_DITOLAK**
```
Halo kak {nama}, bukti transfer untuk *{kode}* belum bisa kami terima: {alasan}.
Mohon upload ulang di {link_lacak} ya kak 🙏
```

Tulis juga isi default untuk semua key lain dengan gaya yang sama
(semua harus menyertakan `{kode}` dan `{link_lacak}`).
