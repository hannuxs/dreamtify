"""
Panduan untuk customer & admin: "Yang perlu kamu lakukan sekarang" dan
berapa yang harus dibayar (docs/04 §5). Semua angka dari `settlement`.
"""
from dataclasses import dataclass, field

from django.utils import timezone

from apps.core.dates import format_local
from apps.core.enums import OrderStatus, PaymentKind, TicketPaymentMethod, VaStatus
from apps.core.money import format_rupiah

from . import settlement

S = OrderStatus


@dataclass(frozen=True)
class PaymentDue:
    kind: str  # PaymentKind yang akan dibuat bila customer upload bukti
    amount: int  # nominal yang disarankan
    full_amount: int = 0  # titip bayar: fee + pelunasan sekaligus (0 = tidak ada opsi)
    deadline: object = None
    label: str = ""


def payment_due(order, summary=None) -> PaymentDue | None:
    """Tagihan yang bisa dibayar sekarang; None bila tidak ada."""
    s = summary or settlement.summarize(order)
    titip = order.ticket_payment_method == TicketPaymentMethod.TITIP_BAYAR
    if order.status in (S.MENUNGGU_FEE, S.VERIFIKASI_FEE) and s.remaining_initial > 0:
        return PaymentDue(PaymentKind.FEE, s.remaining_initial,
                          full_amount=s.remaining_before_war if titip and s.pelunasan_due else 0,
                          deadline=order.fee_deadline, label="Fee jasa")
    if order.status in (S.MENUNGGU_PELUNASAN, S.VERIFIKASI_PELUNASAN) and s.remaining_before_war > 0:
        return PaymentDue(PaymentKind.PELUNASAN, s.remaining_before_war,
                          deadline=order.phase.pelunasan_deadline, label="Pelunasan tiket")
    if order.status in (S.PROSES_WAR, S.PENYELESAIAN) and s.results_final and s.shortfall > 0:
        return PaymentDue(PaymentKind.KEKURANGAN, s.shortfall, label="Kekurangan bayar")
    return None


@dataclass(frozen=True)
class NextAction:
    title: str
    text: str
    action: str = ""  # upload | refund_account | va | testimonial | ""
    tone: str = "info"  # info | warning | success | danger
    extra: dict = field(default_factory=dict)


def next_action(order, summary=None, now=None) -> NextAction:
    """Selalu satu aksi jelas, atau "tunggu kabar"."""
    now = now or timezone.now()
    s = summary or settlement.summarize(order)
    due = payment_due(order, s)
    pending = s.pending_in > 0
    st = order.status

    if st in (S.DIBATALKAN, S.HANGUS):
        if s.refund_due > 0 and not order.refund_account_number:
            return NextAction("Isi rekening refund",
                              f"Ada dana {format_rupiah(s.refund_due)} yang kami kembalikan. Isi rekening tujuan di bawah.",
                              "refund_account", "warning")
        if s.refund_due > 0:
            return NextAction("Refund sedang diproses",
                              f"Refund {format_rupiah(s.refund_due)} akan kami transfer ke rekeningmu.", "", "info")
        return NextAction("Pesanan dibatalkan", "Tidak ada yang perlu kamu lakukan.", "", "danger")

    if st == S.WAITING_LIST:
        return NextAction("Tunggu kabar slot",
                          "Kamu di waiting list dan belum perlu bayar. Kami kabari lewat WhatsApp bila ada slot.")
    if st in (S.MENUNGGU_FEE, S.MENUNGGU_PELUNASAN) and due:
        when = f" sebelum {format_local(due.deadline)}" if due.deadline else ""
        late = due.deadline and due.deadline < now
        return NextAction(f"Bayar {due.label.lower()} {format_rupiah(due.amount)}",
                          f"Transfer{when}, lalu upload buktinya di bawah." +
                          (" Batas waktunya sudah lewat — segera hubungi admin." if late else ""),
                          "upload", "danger" if late else "warning")
    if st in (S.VERIFIKASI_FEE, S.VERIFIKASI_PELUNASAN):
        if due and not pending:
            return NextAction(f"Bayar sisa {format_rupiah(due.amount)}", "Upload bukti transfer di bawah.",
                              "upload", "warning")
        return NextAction("Bukti sedang dicek", "Tidak ada yang perlu kamu lakukan. Kami kabari setelah dicek.")
    if st == S.SIAP_WAR:
        war = format_local(order.phase.war_at)
        if order.ticket_payment_method == TicketPaymentMethod.TITIP_BAYAR:
            return NextAction("Siap war 🎫", f"Pembayaran lengkap. War {war}. Tim kami yang bayar tiketnya.",
                              tone="success")
        return NextAction("Siap war — standby saat war", f"War {war}. VA muncul di halaman ini; "
                          "bayar sebelum batasnya. Telat bayar = tiket hangus.", tone="success")
    if st == S.PROSES_WAR:
        active_va = [v for v in order.va_notices.all() if v.status == VaStatus.AKTIF]
        if active_va:
            return NextAction("Bayar VA sekarang!", "VA untuk tiketmu sudah keluar. Bayar sebelum batas waktunya.",
                              "va", "danger")
        return NextAction("War sedang berlangsung", "Tim kami sedang berjuang. Hasil per tiket muncul di halaman ini.")
    if st == S.PENYELESAIAN:
        if due:
            return NextAction(f"Bayar kekurangan {format_rupiah(due.amount)}",
                              "Kategori yang didapat lebih mahal dari pilihanmu. Upload bukti transfer di bawah.",
                              "upload", "warning")
        if s.refund_due > 0 and not order.refund_account_number:
            return NextAction("Isi rekening refund",
                              f"Ada kelebihan bayar {format_rupiah(s.refund_due)}. Isi rekening tujuan di bawah.",
                              "refund_account", "warning")
        if s.refund_due > 0:
            return NextAction("Refund sedang diproses", f"Refund {format_rupiah(s.refund_due)} akan segera kami transfer.")
        if pending:
            return NextAction("Bukti sedang dicek", "Tidak ada yang perlu kamu lakukan.")
        return NextAction("Tunggu penyerahan tiket", "Info penukaran / penyerahan gelang muncul di bagian tiket.")
    return NextAction("Selesai ✨", "Terima kasih sudah memakai Dreamtify!", "testimonial", "success")


def expected_amounts(order, kind: str, summary=None) -> tuple[int, int]:
    """Untuk antrian verifikasi: (nominal yang diharapkan, alternatif "bayar sekaligus" atau 0).
    Dihitung dari sisa tagihan saat ini (bukti yang sedang dicek belum dihitung)."""
    s = summary or settlement.summarize(order)
    if kind == PaymentKind.FEE:
        titip = order.ticket_payment_method == TicketPaymentMethod.TITIP_BAYAR
        return s.remaining_initial, (s.remaining_before_war if titip and s.pelunasan_due else 0)
    if kind == PaymentKind.PELUNASAN:
        return s.remaining_before_war, 0
    if kind == PaymentKind.KEKURANGAN:
        return s.shortfall, 0
    return 0, 0


# Kabar yang boleh dibuat manual dari detail pesanan (docs/05 §3 "Kirim kabar WA")
MANUAL_MESSAGE_KEYS = (
    "PENGINGAT_FEE", "FEE_DITERIMA", "TAGIHAN_PELUNASAN", "PENGINGAT_PELUNASAN", "SIAP_WAR",
    "HASIL_SECURED", "HASIL_SEBAGIAN", "HASIL_GAGAL", "REFUND_ISI_REKENING", "REFUND_SELESAI",
    "KEKURANGAN_BAYAR", "GELANG_SIAP", "ETIKET_INFO", "DIBATALKAN", "SELESAI_MINTA_TESTIMONI",
    "WAITING_LIST_NAIK",
)


def message_extra(order, key: str, summary=None) -> dict:
    """Nominal & batas waktu yang tepat untuk sebuah template pesan."""
    s = summary or settlement.summarize(order)
    if key in ("PENGINGAT_FEE", "WAITING_LIST_NAIK", "PESANAN_DIBUAT"):
        return {"nominal": s.remaining_initial, "batas_waktu": order.fee_deadline}
    if key in ("TAGIHAN_PELUNASAN", "PENGINGAT_PELUNASAN"):
        return {"nominal": s.remaining_before_war, "batas_waktu": order.phase.pelunasan_deadline}
    if key == "FEE_DITERIMA":
        return {"nominal": s.initial_due}
    if key == "SIAP_WAR":
        return {"batas_waktu": order.phase.war_at}
    if key in ("REFUND_ISI_REKENING", "REFUND_SELESAI"):
        return {"nominal": s.refund_due or s.refunded}
    if key == "KEKURANGAN_BAYAR":
        return {"nominal": s.shortfall}
    if key == "DIBATALKAN":
        return {"alasan": (order.get_cancel_reason_display() or "").lower()}
    if key == "ETIKET_INFO":
        return {"detail_penyerahan": order.event.redemption_info}
    return {}
