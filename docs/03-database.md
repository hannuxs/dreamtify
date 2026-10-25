# 03 — Database (MariaDB, port 3309)

- Charset/collation: `utf8mb4` / `utf8mb4_unicode_ci`. Engine InnoDB.
- Semua model punya `created_at`, `updated_at` (abstract `TimeStampedModel`).
- Uang: `PositiveBigIntegerField` (atau `BigIntegerField` bila bisa negatif).
- `[E]` = dienkripsi (Fernet) — lihat `docs/09`.
- Enum: lihat `docs/02` §2.
- Tambahkan index pada field yang sering difilter (ditandai `idx`).

## core

### SiteSetting (singleton, id=1)
| Field | Tipe | Catatan |
|---|---|---|
| brand_name | char | "Dreamtify" |
| tagline | char | "Your Dream is Our Priority" |
| logo | image | default `static/img/logo-dreamtify.png` |
| admin_whatsapp | char | format 62…; tujuan tombol "Tanya admin" |
| instagram | char | |
| contact_email | email | |
| general_terms | text (markdown sederhana) | Syarat & ketentuan umum |
| privacy_policy | text | |
| refund_policy_summary | text | ringkasan yang tampil di form |
| default_fee_payment_window_hours | int | 24 |
| default_booking_slot_fee | int | 50000 |
| sensitive_data_retention_days | int | 30 |
| email_notifications_enabled | bool | false |

### BankAccount
bank_name, account_number, account_holder, is_active, sort_order, note.

### FaqItem
question, answer (text), sort_order, is_active.

### AuditLog
| Field | Catatan |
|---|---|
| actor | FK User, null (sistem/customer) |
| actor_label | "sistem", "customer DRM-XXXX", username |
| action | char idx, mis. `order.status`, `payment.verify`, `nik.reveal`, `export.promotor` |
| object_type, object_id | idx |
| summary | text ringkas (TANPA data sensitif) |
| data | JSON (diff dari→ke, tanpa NIK) |
| ip_address | |

## events

### Event
| Field | Tipe | Catatan |
|---|---|---|
| name | char | "BIGBANG in Jakarta" |
| slug | slug unik | |
| artist | char | |
| venue, city | char | |
| event_dates | char | teks bebas, mis. "29–30 Okt 2026" |
| first_show_date | date idx | untuk urutan & retensi |
| poster | image | publik |
| description | text | |
| ticketing_platform | char | mis. "tiket.com", info saja |
| status | `EventStatus` idx | |
| jaswar_enabled, jastip_enabled | bool | |
| payment_methods | JSON list `TicketPaymentMethod` | yang tersedia untuk event ini |
| max_lines_per_order | int | 6 |
| max_tickets_per_holder | int | 4 |
| required_backups | int 0–2 | 2 |
| fee_basis | `FeeBasis` | `TIER_TERTINGGI` |
| booking_slot_fee | int | default dari SiteSetting |
| early_booking_per_ticket | int | 0 = tidak ada |
| fee_payment_window_hours | int | default dari SiteSetting |
| late_pelunasan_policy | `LatePelunasanPolicy` | `HANGUS` |
| unique_code_enabled | bool | false |
| customer_va_enabled | bool | true (customer boleh kirim VA hasil war mandiri) |
| fallback_any_category | bool | true (aturan "semua habis → kategori apa pun") |
| terms | text | syarat khusus event (tampil di detail & form) |
| redemption_info | text | info penukaran gelang untuk JASWAR |
| promotor_name | char | |
| promotor_token | char unik | untuk `/p/<token>/`, bisa diganti |
| promotor_link_enabled | bool | false |
| promotor_include_nik | bool | false (hanya Owner yang bisa ubah) |
| created_by | FK User | |

### SalePhase
| Field | Catatan |
|---|---|
| event | FK |
| name | "Presale", "Gensale" |
| sort_order | |
| status | `PhaseStatus` idx |
| order_open_at, order_close_at | datetime |
| war_at | datetime |
| pelunasan_deadline | datetime, null |
| slot_quota | int null (tiket) |
| membership_required | bool |
| membership_label | char, mis. "No Membership (wajib sudah registrasi presale)" |
| war_started_at, war_finished_at | datetime null |

### TicketCategory
event FK, name, fee_tier (`FeeTier`), price (int), sort_order, is_active,
description (opsional, mis. "standing", "seated").
Unik: (event, name).

### FeeRule
phase FK, service_type, fee_tier, fee_per_ticket (int).
Unik: (phase, service_type, fee_tier). Admin mengisi sebagai **matriks**.

## orders

### Order
| Field | Catatan |
|---|---|
| code | char unik idx, `DRM-XXXXXX` |
| event, phase | FK idx |
| status | `OrderStatus` idx |
| cancel_reason | `CancelReason` null |
| ticket_payment_method | `TicketPaymentMethod` |
| buyer_name, buyer_whatsapp (idx, ternormalisasi 62…), buyer_email, buyer_instagram | kontak pemesan |
| referral | char "No WA / IG yang merekomendasikan" |
| customer_note | text |
| admin_note | text (internal) |
| fee_due, pelunasan_due, unique_discount | int, snapshot §4.1 |
| unique_code | int null |
| fee_deadline | datetime null idx |
| agreed_terms_at | datetime |
| refund_bank_name, refund_account_holder | char |
| refund_account_number | `[E]` |
| last_customer_view_at | datetime |
| is_late_pelunasan | bool idx (diisi tugas berkala) |
| has_duplicate_nik_warning | bool |
| source_ip, user_agent | untuk audit |

Properti/metode (dihitung di services, bukan disimpan): `paid_in`,
`refunded`, `final_due`, `balance`, `total_tickets`.

### OrderLine
| Field | Catatan |
|---|---|
| order | FK |
| sort_order | |
| service_type | `ServiceType` |
| quantity | 1–4 |
| cat_primary, cat_backup1, cat_backup2 | FK TicketCategory (backup null bila tidak wajib) |
| holder_name | |
| holder_nik | `[E]` |
| holder_nik_hash | char idx (HMAC-SHA256 + pepper) untuk cek duplikat |
| holder_nik_last4 | char(4) untuk tampilan tersamar |
| holder_gender | `L`/`P` null |
| holder_birth_date | date null (dihapus saat retensi) |
| holder_email, holder_whatsapp, holder_instagram | |
| holder_membership_no | char null |
| same_as_buyer | bool |
| tier_snapshot | `FeeTier` |
| fee_per_ticket_snapshot | int |
| price_basis_per_ticket_snapshot | int |
| early_booking_per_ticket_snapshot | int |

### TicketSlot (dibuat otomatis sebanyak `quantity`)
| Field | Catatan |
|---|---|
| line | FK |
| index | 1..quantity |
| result | `SlotResult` idx, default `MENUNGGU` |
| secured_category | FK TicketCategory null |
| ticket_reference | char (kode booking / no. tiket) |
| result_set_by, result_set_at | |
| fulfillment_status | `FulfillmentStatus` idx |
| handover_method | `HandoverMethod` null |
| handover_detail | text (jadwal/lokasi/no. resi) |
| handover_receiver_name | char |
| handover_photo | file privat |
| eticket_file | file privat |
| fulfillment_note | text (tampil ke customer) |
| fulfillment_updated_at | |

### Payment
| Field | Catatan |
|---|---|
| order | FK idx |
| kind | `PaymentKind` |
| status | `PaymentStatus` idx |
| amount_claimed | int (diisi customer) |
| amount_received | int null (diisi admin saat terima; untuk REFUND = nominal keluar) |
| sender_name, sender_bank | |
| transfer_date | date |
| proof | file privat (wajib untuk masuk; untuk REFUND bukti dari admin) |
| destination_account | FK BankAccount null (rekening Dreamtify yang dituju) |
| reject_reason | text |
| verified_by, verified_at | |
| submitted_via | `CUSTOMER` / `ADMIN` |

### VaNotice
order FK, source (`VaSource`), bank, va_number, amount, expires_at,
status (`VaStatus`), slots (M2M TicketSlot), customer_claimed_at,
screenshot (file privat, untuk VA dari customer), note, created_by.

### OrderTimeline
order FK idx, status (null), title, message, is_public (bool), created_by_label,
created_at. Halaman lacak menampilkan baris `is_public=True` urut waktu.

## notifications

### MessageTemplate
key (unik, lihat `docs/08`), title, body (placeholder `{nama}` dst.),
is_active, send_email (bool).

### Notification
| Field | Catatan |
|---|---|
| order | FK idx |
| template_key | |
| channel | `WA` / `EMAIL` |
| recipient | nomor/email |
| rendered_text | |
| status | `PERLU_DIKIRIM` / `TERKIRIM` / `DILEWATI` / `GAGAL` idx |
| sent_by, sent_at | |
| dedupe_key | char unik (mencegah kabar ganda, mis. `DRM-ABC:HASIL:1`) |

## testimonials

### Testimonial
display_name, event (FK null), order (FK null → badge "Pembeli terverifikasi"),
rating (1–5), text, image (publik setelah disetujui), source (`ADMIN`/`CUSTOMER`),
status (`MENUNGGU`/`TAMPIL`/`DISEMBUNYIKAN`) idx, is_featured, consent_publish (bool),
approved_by, approved_at.

## Pengguna & peran

Django `User` + Group:
- `Owner`: semua akses, termasuk pengaturan, pengguna, lihat NIK penuh,
  ekspor dengan NIK, koreksi setelah war, batalkan event.
- `Admin`: operasional (event, pesanan, verifikasi, war, penyelesaian,
  penyerahan, kabar, testimoni, ekspor tanpa NIK).

Django admin bawaan dipasang di `/kelola/sistem/` hanya untuk superuser
(darurat), bukan untuk operasional sehari-hari.

## Lokasi file

```
media/public/   poster event, gambar testimoni yang disetujui
media/private/  bukti transfer, bukti refund, foto gelang, e-tiket, screenshot VA
```
Nama file acak (UUID). File privat hanya lewat view berizin (`docs/09`).
