"""履歴CSVから価格推移グラフ付きのExcelレポートを生成する。"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from tracker import PriceRecord, read_history

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True)
BELOW_THRESHOLD_FILL = PatternFill("solid", fgColor="C6EFCE")
ERROR_FILL = PatternFill("solid", fgColor="FFC7CE")
PRICE_FORMAT = "#,##0"


def _display_width(text: str) -> int:
    """全角文字を幅2と数えた表示幅。商品名の列が切れるのを防ぐために使う。"""
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def _format_timestamp(checked_at: str) -> str:
    return checked_at.replace("T", " ")[:16]


def _sorted_names(records: Iterable[PriceRecord]) -> list[str]:
    names: list[str] = []
    for record in records:
        if record.name not in names:
            names.append(record.name)
    return names


def _style_header(sheet: Worksheet) -> None:
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
    sheet.freeze_panes = "A2"


def _autosize(sheet: Worksheet, min_width: int = 10, max_width: int = 60) -> None:
    for column in sheet.columns:
        length = max(
            (_display_width(str(cell.value)) for cell in column if cell.value is not None), default=0
        )
        letter = get_column_letter(column[0].column)
        sheet.column_dimensions[letter].width = min(max(length + 2, min_width), max_width)


def _write_trend_sheet(sheet: Worksheet, records: list[PriceRecord], names: list[str]) -> None:
    sheet.append(["日時", *names])
    by_timestamp: dict[str, dict[str, int | None]] = {}
    for record in records:
        by_timestamp.setdefault(record.checked_at, {})[record.name] = record.price

    for checked_at in sorted(by_timestamp):
        prices = by_timestamp[checked_at]
        sheet.append([_format_timestamp(checked_at), *(prices.get(name) for name in names)])

    for row in sheet.iter_rows(min_row=2, min_col=2):
        for cell in row:
            cell.number_format = PRICE_FORMAT

    _style_header(sheet)
    _autosize(sheet)

    if sheet.max_row < 2:
        return

    chart = LineChart()
    chart.title = "価格推移"
    chart.y_axis.title = "価格（円）"
    chart.x_axis.title = "取得日時"
    chart.height = 10
    chart.width = 24
    data = Reference(sheet, min_col=2, max_col=1 + len(names), min_row=1, max_row=sheet.max_row)
    categories = Reference(sheet, min_col=1, min_row=2, max_row=sheet.max_row)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(categories)
    sheet.add_chart(chart, f"A{sheet.max_row + 3}")


def _write_history_sheet(sheet: Worksheet, records: list[PriceRecord]) -> None:
    sheet.append(["取得日時", "商品名", "URL", "価格", "備考"])
    for record in records:
        sheet.append([_format_timestamp(record.checked_at), record.name, record.url, record.price, record.note])
        row = sheet[sheet.max_row]
        row[3].number_format = PRICE_FORMAT
        if record.price is None:
            fill = ERROR_FILL
        elif record.note:
            fill = BELOW_THRESHOLD_FILL
        else:
            continue
        for cell in row:
            cell.fill = fill

    _style_header(sheet)
    _autosize(sheet)


def build_report(history: Path, output: Path) -> Path:
    """履歴CSVを読み込み、価格推移シートと取得履歴シートを持つxlsxを書き出す。"""
    records = list(read_history(history))
    workbook = Workbook()
    trend = workbook.active
    trend.title = "価格推移"
    _write_trend_sheet(trend, records, _sorted_names(records))
    _write_history_sheet(workbook.create_sheet("取得履歴"), records)
    workbook.save(output)
    return output
