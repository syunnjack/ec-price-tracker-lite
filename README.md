# ec-price-tracker-lite

ECサイトの商品ページから価格を取得し、CSVに履歴を蓄積する軽量スクリプトです。
「価格改定の見落ち」「毎朝の手動チェック」を自動化するための最小構成サンプルとして公開しています。

## できること

- 複数の商品ページを設定ファイル（JSON）で一括管理
- CSSセレクタで価格要素を指定して取得
- 取得結果を `history.csv` に追記（Excelでそのまま開けるUTF-8 BOM付き）
- 目標価格を設定すると、下回った行に注記を付与

## セットアップ

```bash
git clone https://github.com/syunnjack/ec-price-tracker-lite.git
cd ec-price-tracker-lite
python -m venv .venv && source .venv/bin/activate  # Windowsは .venv\Scripts\activate
pip install -r requirements.txt
```

## 使い方

```bash
cp targets.example.json targets.json  # 監視したい商品に書き換える
python main.py --config targets.json --output history.csv
```

出力例:

```
サンプル商品A	2,780円	目標価格3,000円以下
サンプル商品B	5,400円
2件を history.csv に追記しました。
```

### 設定ファイル

| キー | 必須 | 説明 |
| --- | --- | --- |
| `name` | ○ | CSVに記録する商品名 |
| `url` | ○ | 商品ページのURL |
| `selector` | ○ | 価格が入っている要素のCSSセレクタ |
| `threshold` | - | 目標価格（円）。下回るとCSVのnote列に注記が入る |

Windowsのタスクスケジューラや cron に登録すれば、定期実行での価格履歴収集ができます。

## 注意

対象サイトの利用規約・robots.txt を確認し、過度なリクエストを行わないようにしてください。
本スクリプトは学習・検証用のサンプルです。

## GUI版・Excelレポート版の配布（BOOTH）

コマンド操作なしで使えるWindows向けGUI版（.exe）と、集計済みExcelレポートのテンプレートをBOOTHで配布しています。

- BOOTH: 〔BOOTH商品ページURLをここに記載〕

## 個別カスタマイズのご相談（ココナラ）

「対象サイトを追加したい」「Slack/メール通知を付けたい」「社内システムと連携したい」といった個別要件は、ココナラでオーダーメイド対応しています。

- ココナラ: 〔ココナラ出品ページURLをここに記載〕

## ライセンス

MIT License
