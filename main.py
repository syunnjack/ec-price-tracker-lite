"""ECサイトの商品価格を取得し、CSVへ履歴を蓄積するCLI。

使い方:
    python main.py --config targets.json --output history.csv
    python main.py --config targets.json --output history.csv --report report.xlsx
    python main.py --make-excel-template 監視対象テンプレート.xlsx
    python main.py --from-excel 監視対象テンプレート.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from excel_template import build_template, load_targets_from_excel
from report import build_report
from tracker import append_records, fetch_all, load_targets, save_targets


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ECサイトの価格を取得してCSVに記録します。")
    parser.add_argument("--config", type=Path, default=Path("targets.json"), help="監視対象の定義ファイル")
    parser.add_argument("--output", type=Path, default=Path("history.csv"), help="履歴CSVの出力先")
    parser.add_argument("--report", type=Path, help="指定すると価格推移グラフ付きExcelレポートを出力")
    parser.add_argument("--from-excel", type=Path, help="Excelテンプレートから --config のJSONを作成して終了")
    parser.add_argument("--make-excel-template", type=Path, help="監視対象テンプレートのxlsxを作成して終了")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.make_excel_template is not None:
        build_template(args.make_excel_template)
        print(f"テンプレートを {args.make_excel_template} に作成しました。")
        return 0

    if args.from_excel is not None:
        if not args.from_excel.exists():
            print(f"Excelファイルが見つかりません: {args.from_excel}", file=sys.stderr)
            return 1
        targets = load_targets_from_excel(args.from_excel)
        if not targets:
            print("Excelから監視対象を読み取れませんでした。", file=sys.stderr)
            return 1
        save_targets(targets, args.config)
        print(f"{len(targets)}件を {args.config} に書き出しました。")
        return 0

    if not args.config.exists():
        print(f"設定ファイルが見つかりません: {args.config}", file=sys.stderr)
        return 1

    records = fetch_all(load_targets(args.config))
    append_records(records, args.output)
    for record in records:
        price = f"{record.price:,}円" if record.price is not None else "-"
        print(f"{record.name}\t{price}\t{record.note}")
    print(f"{len(records)}件を {args.output} に追記しました。")

    if args.report is not None:
        build_report(args.output, args.report)
        print(f"レポートを {args.report} に出力しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
