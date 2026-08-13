"""ECサイトの商品価格を定期的に取得し、CSVへ履歴を蓄積する軽量トラッカー。

使い方:
    python main.py --config targets.json --output history.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup

USER_AGENT = "ec-price-tracker-lite/0.1 (+https://github.com/syunnjack/ec-price-tracker-lite)"
REQUEST_TIMEOUT = 15
PRICE_PATTERN = re.compile(r"\d[\d,]*")


@dataclass
class Target:
    name: str
    url: str
    selector: str
    threshold: int | None = None


@dataclass
class PriceRecord:
    checked_at: str
    name: str
    url: str
    price: int | None
    note: str


def load_targets(path: Path) -> list[Target]:
    data = json.loads(path.read_text(encoding="utf-8"))
    targets = []
    for entry in data["targets"]:
        targets.append(
            Target(
                name=entry["name"],
                url=entry["url"],
                selector=entry["selector"],
                threshold=entry.get("threshold"),
            )
        )
    return targets


def parse_price(text: str) -> int | None:
    match = PRICE_PATTERN.search(text)
    if match is None:
        return None
    return int(match.group().replace(",", ""))


def fetch_price(target: Target, session: requests.Session) -> PriceRecord:
    checked_at = datetime.now().isoformat(timespec="seconds")
    try:
        response = session.get(target.url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        return PriceRecord(checked_at, target.name, target.url, None, f"取得失敗: {exc}")

    element = BeautifulSoup(response.text, "html.parser").select_one(target.selector)
    if element is None:
        return PriceRecord(checked_at, target.name, target.url, None, "セレクタに一致する要素なし")

    price = parse_price(element.get_text(" ", strip=True))
    if price is None:
        return PriceRecord(checked_at, target.name, target.url, None, "価格の数値を抽出できず")

    note = ""
    if target.threshold is not None and price <= target.threshold:
        note = f"目標価格{target.threshold:,}円以下"
    return PriceRecord(checked_at, target.name, target.url, price, note)


def append_records(records: Iterable[PriceRecord], output: Path) -> None:
    is_new = not output.exists()
    with output.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(["checked_at", "name", "url", "price", "note"])
        for record in records:
            writer.writerow([record.checked_at, record.name, record.url, record.price, record.note])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ECサイトの価格を取得してCSVに記録します。")
    parser.add_argument("--config", type=Path, default=Path("targets.json"), help="監視対象の定義ファイル")
    parser.add_argument("--output", type=Path, default=Path("history.csv"), help="履歴CSVの出力先")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.config.exists():
        print(f"設定ファイルが見つかりません: {args.config}", file=sys.stderr)
        return 1

    targets = load_targets(args.config)
    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        records = [fetch_price(target, session) for target in targets]

    append_records(records, args.output)
    for record in records:
        price = f"{record.price:,}円" if record.price is not None else "-"
        print(f"{record.name}\t{price}\t{record.note}")
    print(f"{len(records)}件を {args.output} に追記しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
