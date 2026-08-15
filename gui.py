"""価格取得ツールのGUI（tkinter）。

コマンド操作なしで監視対象の編集・価格取得・Excelレポート出力ができる。
    python gui.py
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from excel_template import load_targets_from_excel
from report import build_report
from tracker import PriceRecord, Target, append_records, fetch_all, load_targets, save_targets

CONFIG_PATH = Path("targets.json")
HISTORY_PATH = Path("history.csv")
REPORT_PATH = Path("price_report.xlsx")


class TargetDialog(simpledialog.Dialog):
    """監視対象1件の追加・編集ダイアログ。"""

    def __init__(self, parent: tk.Misc, title: str, target: Target | None = None) -> None:
        self._target = target
        self.result: Target | None = None
        super().__init__(parent, title=title)

    def body(self, master: tk.Misc) -> tk.Widget:
        labels = ("商品名", "商品ページURL", "価格のセレクタ", "目標価格（任意）")
        initial = (
            self._target.name if self._target else "",
            self._target.url if self._target else "",
            self._target.selector if self._target else ".price",
            str(self._target.threshold) if self._target and self._target.threshold is not None else "",
        )
        self._entries: list[tk.Entry] = []
        for row, (label, value) in enumerate(zip(labels, initial)):
            ttk.Label(master, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
            entry = ttk.Entry(master, width=52)
            entry.insert(0, value)
            entry.grid(row=row, column=1, padx=6, pady=4)
            self._entries.append(entry)
        ttk.Label(
            master,
            text="セレクタは価格の文字を右クリック →「検証」で表示される class 名を \".クラス名\" の形で入力します。",
            wraplength=440,
            foreground="#555555",
        ).grid(row=len(labels), column=0, columnspan=2, sticky="w", padx=6, pady=(2, 6))
        return self._entries[0]

    def validate(self) -> bool:
        name, url, selector, threshold_text = (entry.get().strip() for entry in self._entries)
        if not name or not url or not selector:
            messagebox.showwarning("入力エラー", "商品名・URL・セレクタは必須です。", parent=self)
            return False
        threshold: int | None = None
        if threshold_text:
            digits = threshold_text.replace(",", "").replace("円", "")
            if not digits.isdigit():
                messagebox.showwarning("入力エラー", "目標価格は数字で入力してください。", parent=self)
                return False
            threshold = int(digits)
        self.result = Target(name=name, url=url, selector=selector, threshold=threshold)
        return True


class App(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.targets: list[Target] = []
        self.latest: dict[str, PriceRecord] = {}
        self._build_widgets()
        self._load_config()

    def _build_widgets(self) -> None:
        self.grid(sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        buttons = (
            ("監視対象を追加", self.add_target),
            ("監視対象を編集", self.edit_target),
            ("削除", self.delete_target),
            ("Excelから読込", self.import_from_excel),
            ("今すぐ取得", self.fetch_now),
            ("Excelに出力", self.export_report),
        )
        for column, (label, command) in enumerate(buttons):
            ttk.Button(toolbar, text=label, command=command).grid(row=0, column=column, padx=(0, 6))

        columns = ("name", "price", "threshold", "note", "url")
        headings = {
            "name": "商品名",
            "price": "価格",
            "threshold": "目標価格",
            "note": "備考",
            "url": "URL",
        }
        widths = {"name": 200, "price": 100, "threshold": 100, "note": 220, "url": 320}
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        for column in columns:
            self.tree.heading(column, text=headings[column])
            anchor = "e" if column in {"price", "threshold"} else "w"
            self.tree.column(column, width=widths[column], anchor=anchor)
        self.tree.tag_configure("below", background="#DFF5E1")
        self.tree.tag_configure("error", background="#FBE3E4")
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", lambda _event: self.edit_target())

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.status = tk.StringVar(value="準備完了")
        ttk.Label(self, textvariable=self.status, foreground="#333333").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

    def _load_config(self) -> None:
        if not CONFIG_PATH.exists():
            self.status.set(f"{CONFIG_PATH} が無いため空の状態で開始します。「監視対象を追加」から登録してください。")
            return
        try:
            self.targets = load_targets(CONFIG_PATH)
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("設定ファイルエラー", f"{CONFIG_PATH} を読み込めません:\n{exc}")
            return
        self._refresh_tree()
        self.status.set(f"{len(self.targets)}件の監視対象を読み込みました。")

    def _save_config(self) -> None:
        save_targets(self.targets, CONFIG_PATH)

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, target in enumerate(self.targets):
            record = self.latest.get(target.name)
            price = f"{record.price:,}" if record and record.price is not None else "-"
            note = record.note if record else ""
            tags: tuple[str, ...] = ()
            if record is not None:
                if record.price is None:
                    tags = ("error",)
                elif record.note:
                    tags = ("below",)
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    target.name,
                    price,
                    f"{target.threshold:,}" if target.threshold is not None else "-",
                    note,
                    target.url,
                ),
                tags=tags,
            )

    def _selected_index(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("未選択", "対象の行を選択してください。")
            return None
        return int(selection[0])

    def add_target(self) -> None:
        dialog = TargetDialog(self.master, "監視対象を追加")
        if dialog.result is None:
            return
        self.targets.append(dialog.result)
        self._save_config()
        self._refresh_tree()
        self.status.set(f"「{dialog.result.name}」を追加しました。")

    def edit_target(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        dialog = TargetDialog(self.master, "監視対象を編集", self.targets[index])
        if dialog.result is None:
            return
        self.latest.pop(self.targets[index].name, None)
        self.targets[index] = dialog.result
        self._save_config()
        self._refresh_tree()
        self.status.set(f"「{dialog.result.name}」を更新しました。")

    def delete_target(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        target = self.targets[index]
        if not messagebox.askyesno("削除の確認", f"「{target.name}」を監視対象から削除しますか？"):
            return
        del self.targets[index]
        self.latest.pop(target.name, None)
        self._save_config()
        self._refresh_tree()
        self.status.set(f"「{target.name}」を削除しました。")

    def import_from_excel(self) -> None:
        path = filedialog.askopenfilename(
            title="監視対象テンプレートを選択",
            filetypes=[("Excelファイル", "*.xlsx"), ("すべて", "*.*")],
        )
        if not path:
            return
        try:
            targets = load_targets_from_excel(Path(path))
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("読み込みエラー", f"Excelを読み込めません:\n{exc}")
            return
        if not targets:
            messagebox.showinfo("対象なし", "「監視対象」シートに商品名・URL・セレクタが記入されていません。")
            return
        if self.targets and not messagebox.askyesno(
            "入れ替えの確認", f"現在の{len(self.targets)}件を、Excelの{len(targets)}件で置き換えますか？"
        ):
            return
        self.targets = targets
        self.latest.clear()
        self._save_config()
        self._refresh_tree()
        self.status.set(f"Excelから{len(targets)}件を読み込み、{CONFIG_PATH} に保存しました。")

    def fetch_now(self) -> None:
        if not self.targets:
            messagebox.showinfo("監視対象なし", "先に「監視対象を追加」から商品を登録してください。")
            return
        self.status.set("取得中です…")
        self._set_buttons_state("disabled")
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self) -> None:
        try:
            records = fetch_all(self.targets)
            append_records(records, HISTORY_PATH)
        except OSError as exc:
            self.after(0, self._fetch_failed, str(exc))
            return
        self.after(0, self._fetch_done, records)

    def _fetch_done(self, records: list[PriceRecord]) -> None:
        self.latest = {record.name: record for record in records}
        self._refresh_tree()
        failures = sum(1 for record in records if record.price is None)
        message = f"{len(records)}件を取得し、{HISTORY_PATH} に追記しました。"
        if failures:
            message += f"（うち{failures}件は取得に失敗しています。備考欄を確認してください）"
        self.status.set(message)
        self._set_buttons_state("normal")

    def _fetch_failed(self, error: str) -> None:
        self.status.set("取得に失敗しました。")
        self._set_buttons_state("normal")
        messagebox.showerror("エラー", f"履歴ファイルに書き込めません:\n{error}")

    def export_report(self) -> None:
        if not HISTORY_PATH.exists():
            messagebox.showinfo("履歴なし", "先に「今すぐ取得」を実行してください。")
            return
        try:
            build_report(HISTORY_PATH, REPORT_PATH)
        except OSError as exc:
            messagebox.showerror("エラー", f"レポートを保存できません:\n{exc}\nExcelで開いている場合は閉じてください。")
            return
        self.status.set(f"{REPORT_PATH} を出力しました。")
        messagebox.showinfo("出力完了", f"{REPORT_PATH.resolve()} に出力しました。")

    def _set_buttons_state(self, state: str) -> None:
        for child in self.winfo_children():
            if isinstance(child, ttk.Frame):
                for button in child.winfo_children():
                    if isinstance(button, ttk.Button):
                        button.configure(state=state)


def main() -> None:
    root = tk.Tk()
    root.title("EC価格チェック自動化ツール")
    root.geometry("1000x520")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
