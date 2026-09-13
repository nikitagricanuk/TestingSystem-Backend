"""Builds an .xlsx workbook from a list of row-dicts, honoring a caller-chosen
column subset and order (PV-A-1: "приёмная комиссия должна выбирать столбцы и
их порядок")."""
from io import BytesIO

from openpyxl import Workbook


class UnknownColumnError(Exception):
    pass


def build_workbook(
    rows: list[dict],
    columns: list[str],
    headers: dict[str, str],
    sheet_title: str = "Rating",
) -> bytes:
    unknown = [c for c in columns if c not in headers]
    if unknown:
        raise UnknownColumnError(f"Unknown column(s): {unknown}. Valid columns: {sorted(headers)}")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_title[:31]  # Excel sheet-title length limit

    sheet.append([headers[c] for c in columns])
    for row in rows:
        sheet.append([row.get(c, "") for c in columns])

    for i, column in enumerate(columns, start=1):
        max_len = max(
            [len(headers[column])] + [len(str(row.get(column, ""))) for row in rows],
            default=len(headers[column]),
        )
        sheet.column_dimensions[sheet.cell(row=1, column=i).column_letter].width = min(max_len + 2, 60)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
