"""Pembuat file Excel sederhana (openpyxl) — gaya sesuai docs/07 §1."""
import io

from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="BCE2F5")
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def build_workbook(sheets) -> Workbook:
    """sheets: [(judul, [kolom], [[nilai, ...], ...], {indeks_kolom_teks})]."""
    wb = Workbook()
    wb.remove(wb.active)
    for title, headers, rows, text_cols in sheets:
        ws = wb.create_sheet(title=title[:31])
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        for row in rows:
            ws.append(list(row))
        for col in text_cols:  # nomor rekening / WA / NIK disimpan sebagai teks
            for cell in ws.iter_rows(min_row=2, min_col=col + 1, max_col=col + 1):
                cell[0].number_format = "@"
                if cell[0].value is not None:
                    cell[0].value = str(cell[0].value)
        ws.freeze_panes = "A2"
        if rows:
            ws.auto_filter.ref = ws.dimensions
        for i, header in enumerate(headers, start=1):
            width = max([len(str(header))] + [len(str(r[i - 1])) for r in rows if i - 1 < len(r) and r[i - 1] is not None])
            ws.column_dimensions[get_column_letter(i)].width = min(50, max(10, width + 2))
    return wb


def xlsx_response(filename_base: str, sheets) -> HttpResponse:
    buf = io.BytesIO()
    build_workbook(sheets).save(buf)
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    response = HttpResponse(buf.getvalue(), content_type=XLSX_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename_base}_{stamp}.xlsx"'
    response["Cache-Control"] = "no-store"
    return response
