---
title: "毎朝の価格チェックをやめた話：Pythonで作るEC価格トラッカー（コード全文あり）"
emoji: "📉"
type: "tech"
topics: ["python", "スクレイピング", "業務効率化", "自動化", "csv"]
published: false
---

## この記事でやること

「競合ECサイトの価格を毎朝手で確認して、Excelに転記する」という作業を、Pythonスクリプト1本で置き換えます。

- 監視対象はJSONファイルで管理（コードを触らずに商品を追加できる）
- CSSセレクタで価格要素を指定して取得
- 結果はCSVに追記していくので、そのまま価格推移の分析に使える
- 目標価格を設定すると、下回った行に注記が付く

コードは全文このリポジトリに置いてあります。

- GitHub: https://github.com/syunnjack/ec-price-tracker-lite

動作環境はPython 3.10以降、依存は `requests` と `beautifulsoup4` の2つだけです。

## 完成イメージ

```
$ python main.py --config targets.json --output history.csv
サンプル商品A	2,780円	目標価格3,000円以下
サンプル商品B	5,400円
2件を history.csv に追記しました。
```

出力されるCSVはこうなります。UTF-8 BOM付きで書き出しているので、Excelでダブルクリックしても文字化けしません。

```csv
checked_at,name,url,price,note
2026-08-13T09:00:12,サンプル商品A,https://example.com/items/a,2780,"目標価格3,000円以下"
2026-08-13T09:00:13,サンプル商品B,https://example.com/items/b,5400,
```

## 設定ファイルの設計

まず「何を監視するか」をコードから切り離します。ここを分けておくと、非エンジニアの担当者でも商品の追加・削除ができます。

```json
{
  "targets": [
    {
      "name": "サンプル商品A",
      "url": "https://example.com/items/a",
      "selector": ".price",
      "threshold": 3000
    },
    {
      "name": "サンプル商品B",
      "url": "https://example.com/items/b",
      "selector": "#item-price span"
    }
  ]
}
```

| キー | 必須 | 説明 |
| --- | --- | --- |
| `name` | ○ | CSVに記録する商品名 |
| `url` | ○ | 商品ページのURL |
| `selector` | ○ | 価格が入っている要素のCSSセレクタ |
| `threshold` | - | 目標価格（円）。下回るとnote列に注記が入る |

`selector` はブラウザの検証ツールで価格部分を右クリック →「Copy」→「Copy selector」で取得できます。長すぎるセレクタはサイト更新で壊れやすいので、`.price` のようなクラス名まで手で削るのがおすすめです。

## 実装のポイント

### 1. 価格文字列から数値を取り出す

ECサイトの価格表記は `¥2,780`、`2,780円（税込）`、`2,780円〜` などバラバラです。正規表現で「最初に出てくる数字の並び」だけを拾い、カンマを除去して `int` にします。

```python
PRICE_PATTERN = re.compile(r"\d[\d,]*")


def parse_price(text: str) -> int | None:
    match = PRICE_PATTERN.search(text)
    if match is None:
        return None
    return int(match.group().replace(",", ""))
```

「税込」「送料」など複数の金額が並ぶ要素を指定すると先頭の数値を拾ってしまうので、セレクタは価格だけを含む要素まで絞り込みます。

### 2. 失敗しても止めない

自動化スクリプトで一番困るのは「1件が失敗して全部止まる」ことです。取得結果を必ず `PriceRecord` として返し、失敗理由も同じCSVに残します。

```python
@dataclass
class PriceRecord:
    checked_at: str
    name: str
    url: str
    price: int | None
    note: str


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
```

`note` 列に「セレクタに一致する要素なし」が並び始めたら、サイト側のHTML変更のサインです。エラーを潰さず記録しておくと、メンテナンスのきっかけになります。

### 3. CSVは「追記」でヘッダ1回だけ

履歴として使うので、実行するたびに追記します。ファイルが無い初回だけヘッダを書き、エンコーディングは `utf-8-sig` にしてExcel対応にします。

```python
def append_records(records: Iterable[PriceRecord], output: Path) -> None:
    is_new = not output.exists()
    with output.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(["checked_at", "name", "url", "price", "note"])
        for record in records:
            writer.writerow([record.checked_at, record.name, record.url, record.price, record.note])
```

`newline=""` を忘れるとWindowsで空行が入るので注意です。

### 4. セッションを使い回す

`requests.Session` を使うとTCP接続とヘッダ設定を共有できます。User-Agentも明示して、どこからのアクセスか分かるようにしておきます。

```python
with requests.Session() as session:
    session.headers["User-Agent"] = USER_AGENT
    records = [fetch_price(target, session) for target in targets]
```

## 定期実行する

- Windows: タスクスケジューラで「プログラム: `python.exe`」「引数: `main.py --config targets.json`」「開始: リポジトリのフォルダ」を指定
- Linux / macOS: cron に1行追加

```cron
0 9 * * * cd /path/to/ec-price-tracker-lite && .venv/bin/python main.py --config targets.json >> cron.log 2>&1
```

これで毎朝9時に価格が1行ずつ積み上がっていきます。

## スクレイピングの前に確認すること

- 対象サイトの利用規約と `robots.txt` を必ず確認する
- 取得は必要最小限の頻度に留める（1日1回で足りることが多い）
- 公式APIが提供されているサイトでは、スクレイピングではなくAPIを使う
- 取得したデータの二次利用範囲にも注意する

「動くから正しい」ではなく、運用として続けられる形にすることが大事です。

## 非エンジニアに使ってもらうまでの手順

コードが動くのと、現場の非エンジニアメンバーが毎日使えるのとは別問題です。実際に毎朝30分かかっていた価格チェックを1分にするまでにやったこと（導入の進め方、依存の少ない配布方法、セレクタが壊れたときの運用フロー）は、こちらの記事にまとめています。

- Brain: [毎朝30分の「価格チェック」を1分にした話｜非エンジニアでも使える業務自動化の作り方](https://brain-market.com/u/chitamaru/a/byMzMxYjMgoTZsNWa0JXY)
- note: [導入の背景と費用対効果](https://note.com/chitamaru/n/n645cbb9768f1)

## GUI版とExcelレポート版

上のスクリプトはCLIですが、実務では「Pythonを入れられないPCで使いたい」「結果をグラフ付きのExcelで受け取りたい」という要望が出てきます。そのためにWindows向けのGUI版（.exe・インストール不要）と、価格推移グラフ入りExcelレポートのテンプレートを用意しました。

GUI版は監視対象の追加・編集をウィンドウ内で行い、目標価格を下回った行を緑、取得に失敗した行を赤で表示します。

![GUI版で価格を取得した画面](/images/ec-price-tracker-lite/gui.png)

出力したExcelレポートは「価格推移」と「取得履歴」の2シートです。価格推移シートには折れ線グラフが入るので、そのまま社内共有できます。

![Excelレポートの価格推移シート](/images/ec-price-tracker-lite/excel-chart.png)

![Excelレポートの取得履歴シート](/images/ec-price-tracker-lite/excel-log.png)

- Excelテンプレート集（無料）: https://wangan-base.booth.pm/items/8720572
- CSSセレクタ調査ガイド＋導入チェックシート（無料・PDF）: https://wangan-base.booth.pm/items/8720637
- CLI版（自動実行bat・手順書つき）: https://wangan-base.booth.pm/items/8720631
- 導入・運用ガイド（PDF全11章）: https://wangan-base.booth.pm/items/8720621
- GUI版本体（GUI＋CLI・ソース同梱）: https://wangan-base.booth.pm/items/8714957

## 個別カスタマイズの相談

「対象サイトを追加したい」「在庫状況も一緒に取りたい」「Slackやメールに通知したい」「社内の基幹システムに取り込みたい」といった個別要件は、オーダーメイドで対応しています。

- ご相談はこちら: https://coconala.com/services/2561235

## まとめ

- 監視対象はコードから切り離してJSONで管理する
- 失敗を握りつぶさず、理由をCSVに残す
- CSVはUTF-8 BOM＋追記でExcel運用に馴染ませる

小さなスクリプトでも、毎日15分の作業がゼロになれば月5時間の削減になります。まずは1商品から試してみてください。
