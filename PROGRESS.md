# PROGRESS.md

Diperbarui oleh Claude Code di akhir setiap fase. Jangan dihapus.

## Status fase

| No | Fase | Status | Tanggal | Catatan |
|---|---|---|---|---|
| 00 | Pemanasan | ✅ selesai | 2026-10-25 | 5 keputusan dicatat di `ASUMSI-DAN-KEPUTUSAN.md` §D; MariaDB 11.4 dipasang |
| 01 | Fondasi proyek | ✅ selesai | 2026-10-26 | Django 5.2 + MariaDB 3309 + `dev.bat`, komponen dasar, 39 tes lulus |
| 02 | Model data | ✅ selesai | 2026-10-26 | Semua model + services (harga, status, kuota, penyelesaian), seed, admin; 131 tes lulus |
| 03 | Pengaturan & event | ✅ selesai | 2026-10-26 | Login + peran, beranda tugas, kelola event 6 tab (HTMX), duplikat, pengaturan, pengguna, log |
| 04 | Form pesanan | ✅ selesai | 2026-10-26 | Detail event, form 4 langkah multi-tiket, ringkasan live, halaman sukses; diuji di browser |
| 05 | Lacak & pembayaran | ✅ selesai | 2026-10-26 | Lacak (kode+WA/token), upload bukti aman, berkas privat, batal, ubah pemegang, rekening refund |
| 06 | Verifikasi & waiting list | ✅ selesai | 2026-10-26 | Daftar & detail pesanan, Lihat NIK (Owner), antrian verifikasi T/X/J/K, waiting list, hitung ulang, run_periodic |
| 07 | Mode war & hasil | ✅ selesai | 2026-10-26 | Mode War HP (1 ketukan/tiket, undo, konflik versi, refresh 15 dtk), VA admin & VA mandiri, lacak live |
| 08 | Penyelesaian (refund, gelang, e-tiket) | ✅ selesai | 2026-10-26 | Antrian refund/kekurangan + bukti bertahap, penyerahan massal, e-tiket, ekspor Excel |
| 09 | Kabar WA | ✅ selesai | 2026-10-26 | Kotak Kabar (wa.me), mode beruntun, kabar manual, edit template (Owner), email opsional, pengingat |
| 10 | Rekap & ekspor promotor | ⬜ belum | | |
| 11 | Testimoni, beranda, FAQ | ⬜ belum | | |
| 12 | Keamanan & tugas harian | ⬜ belum | | |
| 13 | Installer Windows | ⬜ belum | | |
| 14 | Uji akhir & serah terima | ⬜ belum | | |

Legenda: ⬜ belum · 🟡 sedang · ✅ selesai · ⚠️ selesai dengan catatan

## Hasil tes terakhir

- **2026-10-26, fase 07+08+09** — pytest di MariaDB: **209 lulus, 0 gagal** (+23 tes: mulai war & isi hasil
  via HTMX, undo, konflik versi admin lain, selesaikan war + tandai sisa gagal, filter, VA admin → lacak →
  klaim → lunas, customer tidak melihat VA orang lain, VA mandiri on/off, VA kedaluwarsa, kabar pra-war
  dibuang saat war; refund bertahap dengan bukti sampai Selesai (lebih dari saldo ditolak), ekspor refund
  (rekening sebagai teks), kekurangan + ingatkan, penyerahan JASTIP massal Ditukar → Siap (wajib metode) →
  Diserahkan + foto, info JASWAR + e-tiket diunduh customer, ekspor penyerahan; Kotak Kabar kirim → wa.me
  & Terkirim, ubah/lewati, beruntun, kabar manual, pengingat tidak dobel, email locmem bila diaktifkan,
  edit template + placeholder salah + reset default, Admin 403). pyflakes bersih.
- **Uji browser** (Edge headless, 390px): mulai war dari modal → tombol hasil 1 ketukan → toast + undo
  hitung mundur → undo → gagal → simpan VA → kartu menampilkan "Kirim WA"; lacak customer menampilkan VA +
  polling 10 dtk → "Sudah saya bayar" → Mode War menampilkan klaim; refresh otomatis 15 dtk berjalan;
  selesaikan war (sisa gagal) → antrian refund Rp400.000 & Rp1.000.000 (sesuai rumus) → penyerahan pilih
  semua → Ditukar → Kotak Kabar & mode beruntun. Tidak ada error JS. Diperbaiki: form VA mandiri dilipat,
  kabar pra-war basi dibuang saat war dimulai, judul topbar tidak lagi patah 2 baris di HP.

- **2026-10-26, fase 05+06** — pytest di MariaDB: **186 lulus, 0 gagal** (+27 tes: akses lacak
  benar/salah/rate limit/token kedaluwarsa, customer A ≠ B (pesanan & berkas), upload palsu / >10 MB /
  EXIF terbuang / PDF, batal sebelum/sesudah fee, ubah pemegang ditolak sejak war, rekening refund
  terenkripsi; daftar pesanan tanpa N+1, cari NIK lengkap, Lihat NIK hanya Owner + audit, verifikasi
  terima/tolak via antrian, waiting list & lepas slot, hitung ulang, `run_periodic` idempoten).
- **Uji browser** (Edge headless): customer di HP memilih **file asli** → pratinjau → kirim →
  "Bukti fee sedang dicek"; admin di desktop membuka antrian (nominal diharapkan = klaim, gambar
  bukti termuat) lalu menekan **tombol T** di keyboard → diterima → antrian kosong; "Lihat NIK";
  halaman lacak customer berubah ke "Bayar pelunasan Rp 9.500.000". Tidak ada error JS. Diperbaiki:
  form upload kini dilipat saat bukti sedang dicek, filter verifikasi sebaris, panel keuangan rapi.

- **2026-10-26, fase 03+04** — pytest di MariaDB: **159 lulus, 0 gagal** (+28 tes baru:
  login/rate limit/peran/timeout, tab event & validasi publikasi, duplikat, pengaturan,
  pengguna, log; detail event, form pesanan, kuota → waiting list, rate limit, honeypot,
  kirim ganda, akses halaman sukses, ringkasan live).
- **Uji browser sungguhan** (Edge headless, `scripts/tools/browser_flow.py`): alur customer
  di HP 390px (contoh 4 sampai halaman sukses: Rp 750.000 / Rp 9.500.000 / Rp 10.250.000),
  draf localStorage tanpa NIK + pemulihan, login & simpan tab via HTMX (toast), dashboard
  di 390px & 1366px tanpa scroll horizontal. **Tidak ada error JS.** Bug yang ketemu & sudah
  diperbaiki: tabrakan nama `valueOf` di Alpine (review "[object Object]"), maskot pengganti
  poster terlalu besar, kolom keterangan kategori terlalu tinggi.

- **2026-10-26, fase 02** — `.venv\Scripts\python -m pytest` di **MariaDB 11.4.13**:
  **131 lulus, 0 gagal** (±15 detik). Termasuk 6 contoh wajib `docs/02` §4.5 (persis),
  setiap baris tabel pembatalan §4.4, verifikasi kurang/pas/lebih/sekaligus, undo Mode War,
  enkripsi + rotasi kunci, dan tes kuota bersamaan (2 thread, sisa kuota 1).
  Tes kuota dibuktikan bermakna: tanpa `select_for_update` tes itu **gagal** (keduanya dapat slot).
- `makemigrations --check`: bersih. `seed_initial` dua kali: tanpa duplikat.

- **2026-10-26, fase 01** — `.venv\Scripts\python -m pytest` di **MariaDB 11.4.13**
  (DB tes `test_dreamtify_dev`): **39 lulus, 0 gagal**.
- `manage.py check` (dev): bersih. `check --deploy` (prod): hanya 4 peringatan
  HTTPS (W004/W008/W012/W016) — wajar karena `HTTPS=0`; otomatis hilang saat `HTTPS=1`.
- `collectstatic` prod (whitenoise manifest): 156 file, sukses.
- Cek visual (Edge headless + emulasi perangkat) di 360px & 1366px: beranda,
  `/_komponen/`, kerangka dashboard, 404, 500 — tanpa scroll horizontal.
  Interaksi diuji: laci menu, modal, toast, tombol salin (klik asli).

## Lingkungan pengembangan

| Item | Nilai |
|---|---|
| OS | Windows 10 Pro 22H2 64-bit |
| Python | 3.12.10 (`py -3.12`) |
| MariaDB | 11.4.13, layanan `MariaDB`, port 3309, `C:\Program Files\MariaDB 11.4` (dipasang 2026-10-25) |
| Password root MariaDB | file `%USERPROFILE%\dreamtify-mariadb-root.txt` (di luar proyek) — **pindahkan ke pengelola kata sandi lalu hapus file** |
| XAMPP | MariaDB 10.4 (layanan `mysql`, port 3306) tetap ada, **tidak dipakai** (terlalu lama untuk Django 5.2) |
| Git | repo di-init di `main` |

## Pertanyaan terbuka

(hal ambigu yang diputuskan sementara dengan `# ASUMSI:` — pemilik perlu mengonfirmasi)

**Fase 07–09**

33. **Undo hasil war 10 detik** di layar; setelah itu masih bisa "Ubah hasil" selama tahap berstatus War
    (dan belum ada refund/penyerahan). Dua admin mengisi tiket yang sama → yang kedua ditolak (versi).
34. **VA mandiri** (customer kirim VA sendiri) hanya untuk metode **titip bayar**, hanya saat war, dan bisa
    dimatikan per event (`customer_va_enabled`). Klaim "sudah saya bayar" hanya penanda; Lunas ditandai admin.
35. **Pengingat otomatis**: fee 3 jam sebelum batas, pelunasan 24 jam sebelum batas — **sekali** per pesanan.
    Pengingat manual dari detail pesanan / Penyelesaian boleh berulang.
36. **WA tetap manual** (tombol membuka wa.me dengan pesan siap kirim, lalu ditandai Terkirim). Gateway WA
    berbayar belum dipakai (`HttpWhatsAppGatewayBackend` hanya kerangka). **Email mati secara default**; bila
    diaktifkan di Pengaturan, terkirim otomatis untuk template yang dicentang "kirim email" (VA hanya WA).
37. Saat **war dimulai**, kabar pra-war yang **belum** dikirim (siap war, tagihan, pengingat, fee diterima)
    dibuang agar Kotak Kabar tidak berisi pesan basi. Yang sudah terkirim tetap di riwayat.
38. **Admin** (bukan hanya Owner) melihat nomor rekening refund lengkap di Penyelesaian & ekspor Excel,
    karena Admin yang mentransfer; setiap tampilan/ekspor dicatat di log aktivitas.
39. Penyerahan: **e-tiket hanya bisa dilampirkan bila 1 tiket dipilih**; foto serah terima massal disalin ke
    setiap tiket. "Siap diserahkan" wajib metode (COD/titik temu/kirim), "Diserahkan" wajib nama penerima.
40. **Edit template pesan hanya Owner**; template yang sudah diubah tidak ditimpa `seed_initial`, ada tombol
    "Kembalikan ke default". Placeholder tak dikenal hanya diperingatkan (tetap boleh disimpan).

**Fase 05–06**

24. `/berkas/…` dan `/lacak/<kode>/` tanpa izin menjawab **404** (bukan 403) agar tidak membocorkan keberadaan kode.
25. Customer **boleh upload bukti tambahan** saat status "sedang dicek" (mis. transfer kedua). Bila nominal yang
    sedang dicek sudah menutup tagihan, form dilipat ("Tidak perlu upload lagi").
26. Rate limit upload **10 / jam / pesanan** menghitung semua percobaan (termasuk yang gagal validasi).
27. **HEIC (foto iPhone) ditolak** dengan pesan ramah (kirim screenshot/JPG) — tidak menambah dependensi pillow-heif.
28. Rekening refund **tidak bisa diubah customer** setelah refund pertama dicatat (hubungi admin).
29. **Admin boleh membatalkan pesanan waiting list** (belum ada uang); pesanan berbayar hanya Owner.
30. **Hitung ulang / ubah jumlah-kategori** hanya sebelum war; bila tagihan naik, status bisa mundur dari
    Siap war ke Menunggu pelunasan/fee. Tambah tiket dicek terhadap kuota tahap.
31. Ubah data pemegang oleh customer: NIK dikosongkan = tidak berubah; JASTIP hanya nama & WA.
    Setelah war: hanya Owner, alasan wajib.
32. `run_periodic` belum dijadwalkan otomatis (Scheduled Task dibuat installer, fase 13) — jalankan manual:
    `.venv\Scripts\python manage.py run_periodic`. Pengingat & VA kedaluwarsa ditambahkan fase 07/09.

**Fase 03–04**

14. Status tahap **War/Selesai** hanya diatur dari Mode War; form tahap hanya Draf/Buka/Tutup.
15. **Validasi publikasi**: event Tampil + tahap Buka wajib punya kategori aktif, waktu war, dan
    sel fee untuk *tier yang dipakai kategori aktif* (bila tidak ada kategori VIP, fee VIP tidak wajib).
    Diterapkan seragam: setiap simpan di tab mana pun dibatalkan (rollback) bila hasilnya melanggar.
16. **Pesanan tutup paling lambat 2 jam sebelum war** divalidasi di form tahap (D3a).
17. **Event yang tampil ke publik**: status Tampil & Selesai. Draf/Arsip/Dibatalkan → 404, kecuali admin (banner "Pratinjau").
18. **NIK tidak diisi ulang** setelah form ditolak validasi — customer mengetik ulang (aturan "NIK tidak tampil utuh setelah dikirim").
    Draf localStorage juga tidak menyimpan NIK, tanggal lahir, dan no. membership.
19. **JASTIP**: data identitas pemegang (KTP, tgl lahir, email, IG) tidak disimpan walau terisi (C2).
20. **Username IG pemesan wajib** (data B11). Perekomendasi opsional.
21. **Rate limit pesanan** dihitung dari kiriman yang lolos validasi (5 / 10 menit / IP), bukan dari salah isi.
22. Kartu beranda tugas "Refund siap diproses", "Kekurangan bayar", "Tiket menunggu penyerahan"
    belum tampil (dibangun fase 08). Tab "Template pesan" di Pengaturan = segera (fase 09).
23. Tombol **"Upload bukti sekarang"** di halaman sukses menuju halaman lacak — halaman itu dibangun di fase 05
    (sementara 404). Beranda masih "Segera hadir" + daftar event buka (beranda final fase 11).

**Fase 02**

6. **Snapshot harga per pesanan** (`Order.pricing_snapshot`): seluruh matriks fee, harga &
   tier semua kategori, booking slot, dan early booking disimpan saat pesanan dibuat. Hasil war
   (termasuk kategori "Lainnya" di luar pilihan) dihitung dari snapshot ini — perubahan harga
   event tidak mengubah pesanan lama (`docs/02` §4.1). "Hitung ulang" (fase 06) memperbaruinya.
7. **Pembatalan tidak pernah membuat customer berutang**: semua rumus §4.4 dibatasi
   `min(dibayar, …)`. Contoh: fee baru dibayar sebagian lalu batal → yang hangus = yang sudah dibayar.
8. **Batal oleh customer saat bukti masih dicek** → `HANGUS` (bukan `DIBATALKAN`). Bila bukti itu
   kemudian ditolak, yang hangus tetap `min(dibayar=0, …) = 0`; bila diterima, fee hangus sesuai aturan.
9. **Kuota semua-atau-tidak**: pesanan 3 tiket saat sisa 2 masuk waiting list utuh (tidak dipecah).
10. **Saldo saat war berlangsung**: tiket yang belum ada hasilnya dihitung seperti sebelum war
    (fee awal + harga dasar), jadi saldo baru "final" setelah semua tiket terisi.
11. **Admin boleh mencatat pembayaran tanpa bukti** (mis. customer kirim lewat WA); customer wajib upload bukti.
12. **Penyerahan hanya maju** (Menunggu → Ditukar → Siap → Diserahkan); status yang sama boleh
    diulang untuk memperbarui detail (mis. no. resi). Dari "Menunggu" boleh langsung lompat ke "Siap diserahkan".
13. **Batas fee setelah bukti ditolak** diperpanjang ke `sekarang + 6 jam` (maks. `war − 2 jam`) — D3(b).

1. Keputusan D1–D5 di `ASUMSI-DAN-KEPUTUSAN.md` §D sudah disetujui secara umum
   ("pakai usulan yang masuk akal"); D2 (early booking hangus) paling layak dicek ulang.
2. Penyamar log (`apps/core/log_filters.py`) menyamarkan **NIK 16 digit** (boleh
   dengan spasi/titik/strip) **dan semua deret ≥10 digit** (nomor WA, rekening).
   Hanya 4 digit terakhir yang tersisa. Lebih ketat dari `docs/09`, sengaja.
3. Menu header publik memakai path tetap (`/lacak/`, `/testimoni/`, `/faq/`, …)
   yang baru dibangun di fase 04–11; sementara ini menuju 404. Diganti `{% url %}` saat halamannya ada.
4. Menu sidebar dashboard ditulis statis dengan label "segera"; dijadikan data-driven + cek peran di fase 03.
5. Favicon: bagian awan dari logo (dipotong dari atas tulisan, sudut bawah dibulatkan)
   di atas ubin navy — awan pucat tidak terbaca di tab browser bila latarnya transparan.

## Dependensi tambahan

Tidak ada. Semua paket sesuai `CLAUDE.md` §2 (versi di-pin di `requirements*.txt`):
Django 5.2.18, mysqlclient 2.3.0, PyMySQL 1.2.3, waitress 3.0.2, whitenoise 6.12.0,
django-environ 0.14.0, openpyxl 3.1.5, Pillow 13.0.0, cryptography 50.0.2;
dev: pytest 9.1.1, pytest-django 4.14.0, freezegun 1.5.5.
Vendor JS: htmx 2.0.11, `@alpinejs/csp` 3.17.4. Font: Fredoka & Nunito (variable, latin + latin-ext, OFL).

## Catatan untuk fase berikutnya

**Dari fase 07–09:**

- **Mode War**: `/kelola/war/<phase>/` (`apps/dashboard/views_war.py`, `templates/dashboard/war/`). Kartu per
  pesanan dirender ulang lewat HTMX (`hx-target="closest .war-order"`); `warRefresh` (Alpine) memuat ulang
  `#war-list` tiap 15 dtk kecuali ada input aktif / `<details>` terbuka / undo berjalan.
- **VA**: `orders/services/va.py` (`create_va_notice`, `claim_va_paid`, `mark_va_paid`, `expire_vas`).
  Lacak customer melakukan polling diri sendiri (`hx-select="#live"` + `hx-select-oob="#tiket-live"`) saat war.
- **Penyelesaian**: `views_settlement.py` (refund/kekurangan, penyerahan massal). Antrian di
  `orders/selectors.py` (`refund_queue`, `shortfall_queue`, `handover_slots`).
- **Excel**: `apps/exports/excel.py` → `build_workbook(sheets)` / `xlsx_response(name, sheets)`; sheet =
  `(judul, header, rows, text_cols)`. Kolom teks diformat `@` (nol di depan aman). **Pakai ulang di fase 10.**
- **Kabar**: `notifications/services.py` (`enqueue`, `enqueue_manual`, `discard_pending`, `mark_sent`,
  `mark_skipped`, `update_text`, `preview`, `unknown_placeholders`); backend di `notifications/backends.py`.
  Email dikirim di `transaction.on_commit` → di tes pakai `django_capture_on_commit_callbacks(execute=True)`.
  Teks kabar manual per pesanan: `guidance.MANUAL_MESSAGE_KEYS` + `message_extra(order, key)`.
- `run_periodic` kini juga: pengingat fee/pelunasan & VA kedaluwarsa (tetap idempoten).
- Filter template `urlencode_dict` (`{% load ui %}`) untuk mempertahankan query filter di link.

**Dari fase 05–06:**

- `orders/services/guidance.py`: `next_action(order)` (teks "yang perlu dilakukan"), `payment_due(order)`
  (jenis + nominal + batas; dipakai lacak, sukses, pembayaran manual), `expected_amounts(order, kind)` (verifikasi).
- `orders/services/updates.py`: `update_holder`, `set_refund_account`, `save_admin_note` (audit tanpa NIK/rekening).
- `transitions.recalculate_order`, `recalculate_preview`, `admin_update_line` (+ `RECALC_STATUSES`).
- Akses customer: `apps/public/access.py` (`has_access`, `grant`; token di URL dicatat ke sesi 12 jam).
- Upload: `core/uploads.py` (`process_private_upload` → gambar di-encode ulang JPEG ≤2000px tanpa EXIF, atau PDF;
  `process_public_image`). Berkas privat: `/berkas/<bukti|etiket|foto|va>/<id>/` (admin / pemilik / tanda tangan
  promotor `links.promotor_file_signature` untuk fase 10).
- Alpine baru: `fileDrop` (upload + pratinjau data URL), `verifyPanel` (pintasan & zoom/putar), `payChoice`.
- Alat uji browser kini punya langkah `file` (pilih file asli) dan `key` (tombol keyboard asli).

**Dari fase 03–04:**

- **Dashboard**: view memakai `dash_render(request, template, ctx, active=...)` (menu + peran),
  `saved(request, msg, url, rerender)` (HTMX → render ulang panel + toast; biasa → PRG redirect),
  `actor_for(request)`. Izin: `@admin_required` / `@owner_required` (`apps/dashboard/permissions.py`),
  `is_owner(user)` / `role_of(user)`. Menu di `apps/dashboard/nav.py` — item "segera" otomatis aktif
  begitu diberi `url_name`.
- Pola simpan per tab: form `hx-post` ke URL yang sama dengan `hx-target/hx-select="#tab-panel"`.
- Form: `StyledFormMixin`, `RupiahField` (terima "3.500.000"), `DateTimeLocalInput`, partial
  `components/field.html` & `components/form_errors.html`.
- Validasi publikasi event: `apps/events/services.py` (`publication_problems`, `checklist`,
  `phase_accepts_orders`, `duplicate_event`, `copy_fee_matrix`).
- Rate limit: `apps/core/ratelimit.py` (`hit`, `is_blocked`, `reset`, `client_ip`). Gambar publik:
  `apps/core/images.process_public_image` (validasi isi, buang EXIF, lebar ≤1600, JPEG) disajikan
  lewat `/media/public/...` (view berizin, hanya jpg/png/webp, cache 1 hari).
- Form pesanan: kartu tiket dirender server sebanyak `max_lines_per_order`; yang tidak aktif
  disembunyikan **dan** di-`disabled` sehingga tidak terkirim. Server membaca baris aktif dari
  keberadaan `lines-N-service_type`. Alpine: `orderForm` + `lineCard` (`static/js/app.js`).
  ⚠️ Jangan memberi nama metode Alpine yang sama dengan properti bawaan objek (`valueOf`, `toString`, …).
- Halaman sukses bisa dibuka oleh sesi pemesan (`session["my_orders"]`) atau token lacak (`?t=`).
- Event contoh **"Contoh Fanmeet"** (`/event/contoh-fanmeet/`) ada di DB dev: Presale (Buka, kuota 40,
  war ±5 hari dari 26 Okt) & Gensale (Draf), 7 kategori, matriks fee sesuai form lama.
- **Uji browser**: `scripts/tools/browser_flow.py skenario.json` (lihat docstring) — dipakai lagi di fase 14.

**Dari fase 02 (penting untuk fase 03+):**

- **API services** (`apps/orders/services/transitions.py`) — semua menerima `actor=Actor`
  (`apps.core.actors`: `Actor.staff(user, ip)`, `Actor.customer(code, ip)`, `Actor.system()`):
  `create_order(phase, buyer=BuyerData, lines=[LineData], payment_method)`, `submit_payment`,
  `verify_payment`, `reject_payment(reason)`, `promote_from_waitlist`, `release_slot`,
  `cancel_by_customer`, `cancel_by_admin(reason)`, `cancel_expired_fee` (untuk `run_periodic`),
  `start_war`, `set_slot_result(result, category, expected_version)` (result=`MENUNGGU` = undo),
  `finish_war(mark_rest_failed)`, `set_fulfillment`, `record_refund`, `refresh_completion`.
  Error: `InvalidTransition` (+ `QuotaFull`), `SlotConflict`, `django ValidationError` dengan kunci
  field seperti `lines.0.holder_nik` (cocok untuk dipetakan ke form fase 04).
- **Angka** untuk tampilan: `settlement.summarize(order)` → `initial_due`, `pelunasan_due`,
  `paid_in`, `refunded`, `pending_in`, `final_due`, `balance`, `refund_due`, `shortfall`,
  `remaining_before_war`. Dialog batal: `settlement.cancellation_preview(order)`.
  Pratinjau form: `pricing.quote_order(PricingContext.for_phase(phase), [LineInput…], method)`.
- **Query**: `apps/orders/selectors.py` (`get_order(code)`, `orders_for_phase`, `pending_payments`) — pakai ini di view (prefetch).
- **Template**: `{% load ui %}` → `|rupiah`, `|status_tone`, `|result_tone`. Brand dari `SiteSetting.load()`.
- **Link lacak**: `links.tracking_url(order)` / `check_tracking_token(code, token)` (30 hari) — dipakai fase 05.
- **Notifikasi**: `notifications.services.enqueue(order, KEY, extra=…, dedupe=…)`; template default
  di `apps/notifications/defaults.py` (20 key, semua sudah berisi `{kode}` & `{link_lacak}`).
  Email baru dibuat barisnya (status PERLU_DIKIRIM) bila diaktifkan — pengiriman di fase 09.
- **Zona waktu MariaDB**: Django butuh tabel zona waktu MariaDB untuk filter tanggal (mis.
  `date_hierarchy`, `__date`). Di Windows diisi dari paket `tzdata` lewat
  `Install-TimeZoneTables` (`scripts/common.ps1`); `dev.bat` menawarkannya otomatis bila
  `manage.py cek_db` menjawab `OK:TZ`. **Fase 13: `install.ps1` wajib memanggilnya juga.**
- `dev.bat` kini juga menjalankan `seed_initial` (idempoten) setelah migrasi.
- Izin: grup **Owner** (semua + `orders.view_full_nik`) dan **Admin** (operasional, tanpa NIK
  penuh & tanpa ubah pengaturan). Cek "Lihat NIK" pakai `user.has_perm("orders.view_full_nik")`.

**Dari fase 01:**

- **Settings**: `config/settings/{base,dev,prod,test}.py`. `test.py` (tambahan) dipakai
  pytest: hasher MD5, email `locmem`, log ke NullHandler; `DJANGO_TEST_SQLITE=1` → SQLite.
- **`dev.bat`** = `scripts/dev.ps1` + `scripts/common.ps1`: venv & pip (dipasang ulang
  otomatis bila `requirements*.txt` berubah), `.env` acak, cek port & login DB
  (`manage.py cek_db`), buat DB+user bila perlu (`$env:MARIADB_ROOT_PASSWORD` untuk
  non-interaktif), migrate, createcachetable, runserver `0.0.0.0:8383`.
  Fungsi `Initialize-AppDatabase`, `New-DotEnvFile`, `Find-MariaDbBin`,
  `Test-TcpPort` siap dipakai ulang oleh `install.ps1` (fase 13).
  File `.ps1` sengaja **ASCII murni** (PowerShell 5.1 membaca file tanpa BOM sebagai ANSI).
- **Komponen**: `templates/components/` (button, card, badge, copy_button, modal,
  accordion_item, countdown, stepper, empty_state, toast_host, `_head`). Ikon lewat
  `{% load ui %}{% icon "nama" %}` (sprite `static/img/icons.svg`).
  ⚠️ Parameter lebar penuh tombol bernama `full`, **bukan** `block` (bentrok dengan
  variabel bawaan Django di dalam `{% block %}`).
- **Alpine CSP**: komponen didaftarkan di `static/js/app.js` (`toastHost`, `toastTrigger`,
  `drawer`, `modal`, `copyButton`, `countdown`); atribut template hanya nama properti/metode.
  `app.js` dimuat sebelum Alpine (keduanya `defer`). Script per-halaman yang mendaftar
  komponen Alpine **harus dimuat sebelum** `alpine-csp.min.js`, jadi taruh di `app.js`
  atau tambahkan blok sebelum Alpine di `_head.html`.
- **Toast dari server**: Django messages otomatis jadi toast; respons HTMX bisa memicu
  toast lewat header `HX-Trigger: {"dt:toast": {"message": "...", "tone": "success"}}`.
- **HTMX**: CSRF lewat `hx-headers` di `<body>`; `htmx-config` mematikan eval &
  style indikator inline (persiapan CSP fase 12).
- **Tombol salin** punya fallback `execCommand` karena produksi berjalan di HTTP polos
  (Clipboard API butuh HTTPS).
- **Brand** sementara dari settings (`BRAND_NAME`, `BRAND_TAGLINE`) via
  `apps.core.context_processors.site`; fase 02 pindah ke `SiteSetting`
  (termasuk `admin_whatsapp` — tombol WA di header/404 baru muncul bila terisi).
- Django admin bawaan sudah terpasang di `/kelola/sistem/`; pendaftaran model di fase 02.
- Aset brand dibuat ulang dengan `scripts/tools/make_brand_images.py` (Pillow).
- `/_komponen/`, `/_komponen/dashboard/`, `/_komponen/404/`, `/_komponen/500/`
  hanya aktif saat `DEBUG` (404 di produksi, ada tesnya).
