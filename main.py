"""ECサイトの商品価格を取得し、CSVへ履歴を蓄積するCLI。

使い方:
    python main.py --config targets.json --output history.csv
    python main.py --config targets.json --output history.csv --report report.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from report import build_report
from tracker import append_records, fetch_all, load_targets


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ECサイトの価格を取得してCSVに記録します。")
    parser.add_argument("--config", type=Path, default=Path("targets.json"), help="監視対象の定義ファイル")
    parser.add_argument("--output", type=Path, default=Path("history.csv"), help="履歴CSVの出力先")
    parser.add_argument("--report", type=Path, help="指定すると価格推移グラフ付きExcelレポートを出力")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
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
