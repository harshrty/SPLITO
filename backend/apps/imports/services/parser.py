"""Tolerant parser: xlsx/csv -> list of raw row dicts. Never validates, never crashes.

Values are preserved verbatim (including trailing spaces like 'rohan ') so the
detectors can see the mess. Dates from xlsx cells are emitted as ISO strings.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime

from openpyxl import load_workbook

COLUMNS = ["date", "description", "paid_by", "amount", "currency",
           "split_type", "split_with", "split_details", "notes"]


def _cell_to_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def parse(file_bytes: bytes, filename: str) -> list[dict]:
    if filename.lower().endswith(".xlsx"):
        return _parse_xlsx(file_bytes)
    return _parse_csv(file_bytes)


def _parse_xlsx(file_bytes: bytes) -> list[dict]:
    wb = load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    header = [(_cell_to_str(c)).strip().lower() for c in rows[0]]
    out = []
    for i, raw in enumerate(rows[1:], start=1):
        record = {header[j] if j < len(header) else f"col{j}": _cell_to_str(v)
                  for j, v in enumerate(raw)}
        # keep only the known columns (in order), defaulting missing to ""
        record = {col: record.get(col, "") for col in COLUMNS}
        out.append({"row_number": i, "raw": record})
    return out


def _parse_csv(file_bytes: bytes) -> list[dict]:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    out = []
    for i, row in enumerate(reader, start=1):
        record = {col: (row.get(col) or "") for col in COLUMNS}
        out.append({"row_number": i, "raw": record})
    return out
