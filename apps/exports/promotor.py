"""Pembuat file promotor: Excel 3 sheet (write-only, ringan untuk ribuan baris) + CSV (docs/07)."""
import csv
import io
from datetime import date, datetime

from django.db.models import Prefetch
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from apps.core.enums import OrderStatus
from apps.events.models import TicketCategory
from apps.orders.models import OrderLine, TicketSlot
from apps.orders.services import links

from . import recap as recap_module
from .excel import HEADER_FILL, XLSX_TYPE, clean_text
from .promotor_format import (
    DATA_COLUMNS,
    DATE,
    DATE_FORMAT,
    DATETIME,
    DATETIME_FORMAT,
    LINK,
    NUMBER,
    RESULT_HEADERS,
    RESULT_KINDS,
    ExportContext,
    local_naive,
)

# Fee sudah diterima & tidak batal (docs/07 §2)
PAID_STATUSES = (OrderStatus.MENUNGGU_PELUNASAN, OrderStatus.VERIFIKASI_PELUNASAN, OrderStatus.SIAP_WAR,
                 OrderStatus.PROSES_WAR, OrderStatus.PENYELESAIAN, OrderStatus.SELESAI)
# ASUMSI: "termasuk yang belum bayar" tetap tanpa waiting list (belum dapat slot) & pesanan batal
UNPAID_STATUSES = (OrderStatus.MENUNGGU_FEE, OrderStatus.VERIFIKASI_FEE)

MAX_WIDTH = 50
LINK_FONT = Font(color="0563C1", underline="single")


def export_lines(event, phase=None, include_unpaid=False) -> list:
    statuses = PAID_STATUSES + UNPAID_STATUSES if include_unpaid else PAID_STATUSES
    qs = (OrderLine.objects.filter(order__event=event, order__status__in=statuses)
          .select_related("order__phase", "cat_primary", "cat_backup1", "cat_backup2")
          .prefetch_related("order__payments",
                            Prefetch("slots", queryset=TicketSlot.objects.select_related("secured_category")))
          .order_by("order__created_at", "order_id", "sort_order", "id"))
    if phase:
        qs = qs.filter(order__phase=phase)
    return list(qs)


def recap_for(event, lines) -> recap_module.Recap:
    return recap_module.build(lines, TicketCategory.objects.filter(event=event).order_by("sort_order", "id"))


def _data_rows(event, lines, include_nik) -> list:
    ctx = ExportContext(include_nik=include_nik, proof_url=lambda payment: links.promotor_proof_url(event, payment))
    return [[column.get(line, ctx) for column in DATA_COLUMNS] for line in lines]


def _result_rows(lines) -> list:
    rows = []
    for line in lines:
        choices = " / ".join(c.name for c in (line.cat_primary, line.cat_backup1, line.cat_backup2) if c)
        for slot in line.slots.all():
            rows.append([line.order.code, local_naive(line.order.created_at), line.holder_name, line.service_type,
                         slot.index, choices, slot.get_result_display(),
                         slot.secured_category.name if slot.secured_category else "", slot.ticket_reference,
                         slot.get_fulfillment_status_display()])
    return rows


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _text_cell(ws, value):
    cell = WriteOnlyCell(ws, value=clean_text(value))
    cell.number_format = "@"
    cell.data_type = "s"  # isi customer berawalan "=" tidak boleh jadi rumus
    return cell


def _cell(ws, value, kind):
    if value in ("", None):
        return None
    if kind == LINK:
        cell = _text_cell(ws, value)
        cell.hyperlink = value
        cell.font = LINK_FONT
        return cell
    if kind not in (DATETIME, DATE, NUMBER):
        return _text_cell(ws, value)
    cell = WriteOnlyCell(ws, value=value)
    if kind == DATETIME:
        cell.number_format = DATETIME_FORMAT
    elif kind == DATE:
        cell.number_format = DATE_FORMAT
    return cell


def _header(ws, titles) -> list:
    cells = []
    for title in titles:
        cell = WriteOnlyCell(ws, value=title)
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cells.append(cell)
    return cells


def _write_table(wb, title, headers, kinds, rows) -> None:
    ws = wb.create_sheet(title)
    # Mode write-only: freeze & lebar kolom wajib diatur sebelum baris pertama
    ws.freeze_panes = "A2"
    for i, header in enumerate(headers):
        longest = max([len(header)] + [len(_as_text(row[i])) for row in rows])
        ws.column_dimensions[get_column_letter(i + 1)].width = min(MAX_WIDTH, max(10, longest + 2))
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"
    ws.append(_header(ws, headers))
    for row in rows:
        ws.append([_cell(ws, value, kind) for value, kind in zip(row, kinds)])


def _write_recap(wb, event, phase, recap, *, include_unpaid, include_nik) -> None:
    ws = wb.create_sheet("Rekap")
    ws.column_dimensions["A"].width = 36
    for letter in "BCD":
        ws.column_dimensions[letter].width = 16

    def section(titles, rows):
        ws.append(_header(ws, titles))
        for row in rows:
            ws.append([_text_cell(ws, v) if isinstance(v, str) else v for v in row])
        ws.append([])

    section(["Per kategori", "Diminta sebagai utama", "Secured"],
            [[r["name"], r["requested"], r["secured"]] for r in recap.categories])
    section(["Per layanan", "Pesanan", "Tiket", "Secured"],
            [[r["name"], r["orders"], r["tickets"], r["secured"]] for r in recap.services])
    section(["Per metode bayar", "Pesanan", "Tiket"], [[r["name"], r["orders"], r["tickets"]] for r in recap.methods])
    section(["Info ekspor", ""], [
        ["Waktu ekspor (WIB)", timezone.localtime().strftime("%d/%m/%Y %H:%M:%S")],
        ["Event", event.name],
        ["Tahap", phase.name if phase else "Semua tahap"],
        ["Status", "Termasuk yang belum bayar" if include_unpaid else "Fee sudah diterima, tidak batal"],
        ["No. KTP", "Disertakan" if include_nik else "Disembunyikan"],
    ])


def build_xlsx(event, phase, lines, *, include_nik, include_unpaid=False) -> bytes:
    wb = Workbook(write_only=True)
    _write_table(wb, "Data", [c.title for c in DATA_COLUMNS], [c.kind for c in DATA_COLUMNS],
                 _data_rows(event, lines, include_nik))
    _write_table(wb, "Hasil", list(RESULT_HEADERS), RESULT_KINDS, _result_rows(lines))
    _write_recap(wb, event, phase, recap_for(event, lines), include_unpaid=include_unpaid, include_nik=include_nik)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def csv_safe(value: str) -> str:
    """Cegah CSV injection: awalan yang dibaca Excel sebagai rumus diberi tanda kutip tunggal."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def build_csv(event, lines, *, include_nik) -> bytes:
    """Sheet `Data` saja; UTF-8 BOM agar Excel membaca karakter dengan benar (docs/07 §2)."""
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow([c.title for c in DATA_COLUMNS])
    for row in _data_rows(event, lines, include_nik):
        writer.writerow([csv_safe(clean_text(_as_text(value))) for value in row])
    return buf.getvalue().encode("utf-8-sig")


def filename(event, phase, ext: str) -> str:
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    return f"Dreamtify_{event.slug}_{slugify(phase.name) if phase else 'semua-tahap'}_{stamp}.{ext}"


def file_response(event, phase, lines, fmt: str, *, include_nik, include_unpaid=False) -> HttpResponse:
    if fmt == "csv":
        body, content_type = build_csv(event, lines, include_nik=include_nik), "text/csv; charset=utf-8"
    else:
        body = build_xlsx(event, phase, lines, include_nik=include_nik, include_unpaid=include_unpaid)
        content_type = XLSX_TYPE
    response = HttpResponse(body, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename(event, phase, fmt)}"'
    response["Cache-Control"] = "private, no-store"
    return response
