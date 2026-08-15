"""監視対象をExcelで管理するためのテンプレート生成と読み込み。"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from tracker import Target

SHEET_TITLE = "監視対象"
HEADERS = ["商品名", "商品ページURL", "価格のセレクタ", "目標価格"]
HEADER_FILL = PatternFill("solid", fgColor="1F3864")
COLUMN_WIDTHS = [24, 52, 28, 12]
SAMPLE_ROWS = [
    ["サンプル商品A", "https://example.com/items/1", ".price", 3000],
    ["サンプル商品B", "https://example.com/items/2", "#item-price span", None],
]
HINTS = [
    "商品名: 一覧やレポートに表示される名前です。自由に付けてください。",
    "商品ページURL: 価格が表示されている商品ページのURLです。",
    "価格のセレクタ: Chromeで価格を右クリック→検証→Copy→Copy selector で取得できます。",
    "目標価格: 数値を入れるとその金額以下になった行が緑色で強調されます。空欄でも構いません。",
    "3行目以降にご自身の商品を追記し、サンプル行は削除してください。",
]


def build_template(output: Path) -> Path:
    """記入例と入力ガイドを含む監視対象テンプレートを書き出す。"""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SHEET_TITLE
    sheet.append(HEADERS)
    for row in SAMPLE_ROWS:
        sheet.append(row)

    for index, width in enumerate(COLUMN_WIDTHS, start=1):
        sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = width
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
    sheet.freeze_panes = "A2"

    guide = workbook.create_sheet("記入ガイド")
    guide.column_dimensions["A"].width = 100
    for hint in HINTS:
        guide.append([hint])

    workbook.save(output)
    return output


def load_targets_from_excel(path: Path) -> list[Target]:
    """テンプレートに記入された監視対象を読み込む。空行と記入例の行は無視する。"""
    workbook = load_workbook(path, data_only=True)
    sheet = workbook[SHEET_TITLE] if SHEET_TITLE in workbook.sheetnames else workbook.worksheets[0]
    return [target for target in _iter_targets(sheet)]


def _iter_targets(sheet: Worksheet):
    for name, url, selector, threshold in sheet.iter_rows(min_row=2, max_col=4, values_only=True):
        if not name or not url or not selector:
            continue
        yield Target(
            name=str(name).strip(),
            url=str(url).strip(),
            selector=str(selector).strip(),
            threshold=int(threshold) if threshold not in (None, "") else None,
        )
