"""
Semua enum Dreamtify. Nilai (yang disimpan di DB) persis `docs/02` §2;
label berbahasa Indonesia untuk tampilan.
"""
from django.db import models


class ServiceType(models.TextChoices):
    JASWAR = "JASWAR", "JASWAR (jasa war, data kamu)"
    JASTIP = "JASTIP", "JASTIP (terima beres, data tim)"


class FeeTier(models.TextChoices):
    VIP = "VIP", "VIP"
    REGULER = "REGULER", "Reguler"


# Urutan tier: VIP > REGULER
TIER_RANK = {FeeTier.REGULER: 1, FeeTier.VIP: 2}


class TicketPaymentMethod(models.TextChoices):
    VA_BCA = "VA_BCA", "VA BCA"
    VA_MANDIRI = "VA_MANDIRI", "VA Mandiri"
    TITIP_BAYAR = "TITIP_BAYAR", "Titip Bayar Admin"


class EventStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draf"
    TAMPIL = "TAMPIL", "Tampil"
    SELESAI = "SELESAI", "Selesai"
    DIBATALKAN = "DIBATALKAN", "Dibatalkan"
    ARSIP = "ARSIP", "Arsip"


class PhaseStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draf"
    BUKA = "BUKA", "Buka"
    TUTUP = "TUTUP", "Tutup"
    WAR = "WAR", "War"
    SELESAI = "SELESAI", "Selesai"


class OrderStatus(models.TextChoices):
    WAITING_LIST = "WAITING_LIST", "Masuk waiting list"
    MENUNGGU_FEE = "MENUNGGU_FEE", "Menunggu pembayaran fee"
    VERIFIKASI_FEE = "VERIFIKASI_FEE", "Bukti fee sedang dicek"
    MENUNGGU_PELUNASAN = "MENUNGGU_PELUNASAN", "Menunggu pelunasan tiket"
    VERIFIKASI_PELUNASAN = "VERIFIKASI_PELUNASAN", "Bukti pelunasan sedang dicek"
    SIAP_WAR = "SIAP_WAR", "Siap war 🎫"
    PROSES_WAR = "PROSES_WAR", "War sedang berlangsung"
    PENYELESAIAN = "PENYELESAIAN", "Hasil keluar — proses penyelesaian"
    SELESAI = "SELESAI", "Selesai ✨"
    DIBATALKAN = "DIBATALKAN", "Dibatalkan"
    HANGUS = "HANGUS", "Dibatalkan (fee hangus)"


# Status yang memakai kuota tahap (docs/02 §6)
QUOTA_STATUSES = (
    OrderStatus.MENUNGGU_FEE,
    OrderStatus.VERIFIKASI_FEE,
    OrderStatus.MENUNGGU_PELUNASAN,
    OrderStatus.VERIFIKASI_PELUNASAN,
    OrderStatus.SIAP_WAR,
    OrderStatus.PROSES_WAR,
    OrderStatus.PENYELESAIAN,
    OrderStatus.SELESAI,
)
CANCELLED_STATUSES = (OrderStatus.DIBATALKAN, OrderStatus.HANGUS)
# Status sebelum war: customer boleh batal & ubah data pemegang
PRE_WAR_STATUSES = (
    OrderStatus.WAITING_LIST,
    OrderStatus.MENUNGGU_FEE,
    OrderStatus.VERIFIKASI_FEE,
    OrderStatus.MENUNGGU_PELUNASAN,
    OrderStatus.VERIFIKASI_PELUNASAN,
    OrderStatus.SIAP_WAR,
)
WAR_STATUSES = (OrderStatus.PROSES_WAR, OrderStatus.PENYELESAIAN, OrderStatus.SELESAI)


class CancelReason(models.TextChoices):
    LEWAT_BATAS_FEE = "LEWAT_BATAS_FEE", "Lewat batas bayar fee"
    LEWAT_BATAS_PELUNASAN = "LEWAT_BATAS_PELUNASAN", "Lewat batas pelunasan"
    BATAL_CUSTOMER = "BATAL_CUSTOMER", "Dibatalkan customer"
    BATAL_ADMIN = "BATAL_ADMIN", "Dibatalkan admin"
    EVENT_BATAL = "EVENT_BATAL", "Event batal"


class SlotResult(models.TextChoices):
    MENUNGGU = "MENUNGGU", "Menunggu war"
    SECURED = "SECURED", "Dapat"
    GAGAL = "GAGAL", "Tidak dapat"
    GAGAL_CUSTOMER = "GAGAL_CUSTOMER", "Tidak dapat (VA tidak dibayar)"


class FulfillmentStatus(models.TextChoices):
    TIDAK_PERLU = "TIDAK_PERLU", "Tidak perlu"
    MENUNGGU = "MENUNGGU", "Menunggu penukaran"
    DITUKAR = "DITUKAR", "Gelang sudah ditukar"
    SIAP_DISERAHKAN = "SIAP_DISERAHKAN", "Siap diserahkan"
    DISERAHKAN = "DISERAHKAN", "Sudah diserahkan"
    INFO_DIKIRIM = "INFO_DIKIRIM", "Info penukaran dikirim"


# Alur penyerahan per layanan (docs/02 §9)
FULFILLMENT_FLOW = {
    ServiceType.JASTIP: (
        FulfillmentStatus.MENUNGGU,
        FulfillmentStatus.DITUKAR,
        FulfillmentStatus.SIAP_DISERAHKAN,
        FulfillmentStatus.DISERAHKAN,
    ),
    ServiceType.JASWAR: (FulfillmentStatus.MENUNGGU, FulfillmentStatus.INFO_DIKIRIM),
}
FULFILLMENT_DONE = {
    ServiceType.JASTIP: FulfillmentStatus.DISERAHKAN,
    ServiceType.JASWAR: FulfillmentStatus.INFO_DIKIRIM,
}


class HandoverMethod(models.TextChoices):
    AMBIL_DI_VENUE = "AMBIL_DI_VENUE", "Ambil di venue"
    TITIK_TEMU = "TITIK_TEMU", "Titik temu"
    KIRIM_EKSPEDISI = "KIRIM_EKSPEDISI", "Kirim ekspedisi"


class PaymentKind(models.TextChoices):
    FEE = "FEE", "Fee jasa"
    PELUNASAN = "PELUNASAN", "Pelunasan tiket"
    KEKURANGAN = "KEKURANGAN", "Kekurangan bayar"
    REFUND = "REFUND", "Refund"


INCOMING_PAYMENT_KINDS = (PaymentKind.FEE, PaymentKind.PELUNASAN, PaymentKind.KEKURANGAN)


class PaymentStatus(models.TextChoices):
    MENUNGGU = "MENUNGGU", "Menunggu dicek"
    DITERIMA = "DITERIMA", "Diterima"
    DITOLAK = "DITOLAK", "Ditolak"


class SubmittedVia(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Customer"
    ADMIN = "ADMIN", "Admin"


class VaStatus(models.TextChoices):
    AKTIF = "AKTIF", "Aktif"
    DIKLAIM_CUSTOMER = "DIKLAIM_CUSTOMER", "Customer bilang sudah bayar"
    LUNAS = "LUNAS", "Lunas"
    KEDALUWARSA = "KEDALUWARSA", "Kedaluwarsa"


class VaSource(models.TextChoices):
    ADMIN = "ADMIN", "Dikirim tim"
    CUSTOMER = "CUSTOMER", "Dari customer (war mandiri)"


class LatePelunasanPolicy(models.TextChoices):
    HANGUS = "HANGUS", "Fee hangus"
    REFUND_KURANGI_BOOKING = "REFUND_KURANGI_BOOKING", "Refund dikurangi booking slot"


class FeeBasis(models.TextChoices):
    TIER_TERTINGGI = "TIER_TERTINGGI", "Tier tertinggi di antara pilihan"
    KATEGORI_UTAMA = "KATEGORI_UTAMA", "Tier kategori utama"


class Gender(models.TextChoices):
    L = "L", "Laki-laki"
    P = "P", "Perempuan"


class NotificationChannel(models.TextChoices):
    WA = "WA", "WhatsApp"
    EMAIL = "EMAIL", "Email"


class NotificationStatus(models.TextChoices):
    PERLU_DIKIRIM = "PERLU_DIKIRIM", "Perlu dikirim"
    TERKIRIM = "TERKIRIM", "Terkirim"
    DILEWATI = "DILEWATI", "Dilewati"
    GAGAL = "GAGAL", "Gagal"


class TestimonialSource(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    CUSTOMER = "CUSTOMER", "Customer"


class TestimonialStatus(models.TextChoices):
    MENUNGGU = "MENUNGGU", "Menunggu moderasi"
    TAMPIL = "TAMPIL", "Tampil"
    DISEMBUNYIKAN = "DISEMBUNYIKAN", "Disembunyikan"
