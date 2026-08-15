"""価格取得と履歴CSVの読み書きを担う共通ロジック。"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

import requests
from bs4 import BeautifulSoup

USER_AGENT = "ec-price-tracker-lite/0.1 (+https://github.com/syunnjack/ec-price-tracker-lite)"
REQUEST_TIMEOUT = 15
CSV_HEADER = ["checked_at", "name", "url", "price", "note"]
CSV_ENCODING = "utf-8-sig"
PRICE_PATTERN = re.compile(r"\d[\d,]*")


@dataclass
class Target:
    name: str
    url: str
    selector: str
    threshold: int | None = None

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"name": self.name, "url": self.url, "selector": self.selector}
        if self.threshold is not None:
            data["threshold"] = self.threshold
        return data


@dataclass
class PriceRecord:
    checked_at: str
    name: str
    url: str
    price: int | None
    note: str

    def to_row(self) -> list[object]:
        return [self.checked_at, self.name, self.url, self.price, self.note]


def load_targets(path: Path) -> list[Target]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Target(
            name=entry["name"],
            url=entry["url"],
            selector=entry["selector"],
            threshold=entry.get("threshold"),
        )
        for entry in data["targets"]
    ]


def save_targets(targets: Iterable[Target], path: Path) -> None:
    payload = {"targets": [target.to_dict() for target in targets]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_price(text: str) -> int | None:
    match = PRICE_PATTERN.search(text)
    if match is None:
        return None
    return int(match.group().replace(",", ""))


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


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


def fetch_all(targets: Iterable[Target]) -> list[PriceRecord]:
    with create_session() as session:
        return [fetch_price(target, session) for target in targets]


def append_records(records: Iterable[PriceRecord], output: Path) -> None:
    is_new = not output.exists()
    with output.open("a", encoding=CSV_ENCODING, newline="") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(CSV_HEADER)
        for record in records:
            writer.writerow(record.to_row())


def read_history(path: Path) -> Iterator[PriceRecord]:
    with path.open(encoding=CSV_ENCODING, newline="") as handle:
        for row in csv.DictReader(handle):
            price = row["price"]
            yield PriceRecord(
                checked_at=row["checked_at"],
                name=row["name"],
                url=row["url"],
                price=int(price) if price else None,
                note=row["note"],
            )
