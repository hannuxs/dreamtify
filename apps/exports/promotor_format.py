"""Format ekspor promotor — SATU tempat untuk judul & isi kolom (docs/07 §1).
Bila promotor meminta kolom lain, cukup ubah `DATA_COLUMNS`."""
from collections.abc import Callable
from dataclasses import dataclass

from django.utils import timezone

from apps.core.enums import PaymentKind, PaymentStatus, ServiceType, TicketPaymentMethod
from apps.core.phone import to_local

HIDDEN_NIK = "(disembunyikan)"

SERVICE_LABELS = {
    ServiceType.JASWAR: "JASWAR (Jasa War Only : Menggunakan Data Cust)",
    ServiceType.JASTIP: "JASTIP (Terima Beres Tiket Fisik : Menggunakan Data Tim Dreamtify)",
}
METHOD_LABELS = {
    TicketPaymentMethod.VA_BCA: "VA BCA",
    TicketPaymentMethod.VA_MANDIRI: "VA Mandiri",
    TicketPaymentMethod.TITIP_BAYAR: "TITIP BAYAR ADMIN (Max H-1 sebelum War)",
}

TEXT, NUMBER, DATETIME, DATE, LINK = "text", "number", "datetime", "date", "link"
DATETIME_FORMAT = "dd/mm/yyyy hh:mm:ss"
DATE_FORMAT = "dd/mm/yyyy"


@dataclass(frozen=True)
class ExportContext:
    include_nik: bool
    proof_url: Callable  # payment -> URL bertanda tangan


@dataclass(frozen=True)
class Column:
    title: str
    get: Callable  # (line, ctx) -> nilai
    kind: str = TEXT


def local_naive(value):
    """Excel tidak mengenal zona waktu: simpan waktu WIB apa adanya."""
    return timezone.localtime(value).replace(tzinfo=None, microsecond=0)


def _nik(line, ctx):
    if ctx.include_nik:
        return line.holder_nik
    # Cek last4 agar NIK tidak perlu didekripsi bila memang tidak diizinkan
    return HIDDEN_NIK if line.holder_nik_last4 else ""


def _category(attr):
    def get(line, ctx):
        category = getattr(line, attr)
        return category.name if category else ""
    return get


def _proof(line, ctx):
    for payment in line.order.payments.all():  # urut waktu dibuat
        if payment.kind == PaymentKind.FEE and payment.status == PaymentStatus.DITERIMA and payment.proof:
            return ctx.proof_url(payment)
    return ""


# Urutan & ejaan PERSIS Google Form lama
DATA_COLUMNS = (
    Column("Stempel waktu", lambda line, ctx: local_naive(line.order.created_at), DATETIME),
    Column("Nama Lengkap", lambda line, ctx: line.holder_name),
    Column("No WA", lambda line, ctx: to_local(line.holder_whatsapp or line.order.buyer_whatsapp)),
    Column("Email", lambda line, ctx: line.holder_email or line.order.buyer_email),
    Column("No. KTP", _nik),
    Column("Jenis Kelamin", lambda line, ctx: line.holder_gender),
    Column("Tanggal Lahir", lambda line, ctx: line.holder_birth_date, DATE),
    Column("Username IG", lambda line, ctx: line.holder_instagram or line.order.buyer_instagram),
    Column("Jumlah Tiket yang di inginkan", lambda line, ctx: line.quantity, NUMBER),
    Column("CAT UTAMA yang di inginkan", _category("cat_primary")),
    Column("CAT Cadangan 1 yang di inginkan (Wajib Beda dari CAT UTAMA)", _category("cat_backup1")),
    Column("CAT Cadangan 2 yang di inginkan (Wajib Beda dari CAT 1)", _category("cat_backup2")),
    Column("Punya membership?", lambda line, ctx: "Punya" if line.holder_membership_no else "Tidak"),
    Column("No Membership (wajib sudah registrasi presale)", lambda line, ctx: line.holder_membership_no),
    Column("Jenis Jastip", lambda line, ctx: SERVICE_LABELS[line.service_type]),
    Column("Bukti Transfer FEE JASTIP/JASWAR", _proof, LINK),
    Column("Metode Pembayaran Tiket", lambda line, ctx: METHOD_LABELS[line.order.ticket_payment_method]),
    Column("No WA / IG yg merekomendasikan jastip di Dreamtify", lambda line, ctx: line.order.referral),
)

RESULT_HEADERS = ("Kode Pesanan", "Stempel waktu", "Nama Pemegang", "Layanan", "Tiket ke-",
                  "Pilihan (Utama / Cad 1 / Cad 2)", "Hasil", "Kategori Didapat", "Kode Tiket", "Status Penyerahan")
RESULT_KINDS = (TEXT, DATETIME, TEXT, TEXT, NUMBER, TEXT, TEXT, TEXT, TEXT, TEXT)
