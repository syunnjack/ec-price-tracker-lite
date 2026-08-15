"""BOOTH配布用のZipを作るスクリプト。

Windows上で実行すると、PyInstallerでexeを作り、README.txtとExcelテンプレートを
まとめた dist/ec-price-tracker-gui.zip を作成します。

    python packaging/build_release.py

exeを作らずに同梱ファイルだけ確認したい場合は --skip-exe を付けます。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
STAGE = ROOT / "build" / "release"
APP_NAME = "ec-price-tracker"
ZIP_NAME = "ec-price-tracker-gui.zip"
TEMPLATE_NAME = "監視対象テンプレート.xlsx"

sys.path.insert(0, str(ROOT))

from excel_template import build_template  # noqa: E402


def build_app() -> Path:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--windowed",
            "--name",
            APP_NAME,
            str(ROOT / "gui.py"),
        ],
        cwd=ROOT,
        check=True,
    )
    return DIST / APP_NAME


def stage_files(app_dir: Path | None) -> Path:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    shutil.copy2(ROOT / "packaging" / "README.txt", STAGE / "README.txt")
    shutil.copy2(ROOT / "targets.example.json", STAGE / "targets.example.json")
    build_template(STAGE / TEMPLATE_NAME)
    if app_dir is not None:
        shutil.copytree(app_dir, STAGE, dirs_exist_ok=True)
    return STAGE


def make_zip(stage: Path) -> Path:
    DIST.mkdir(exist_ok=True)
    archive = DIST / ZIP_NAME
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(stage).as_posix())
    return archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BOOTH配布用のZipを作成します。")
    parser.add_argument("--skip-exe", action="store_true", help="PyInstallerを実行せず同梱ファイルのみZip化")
    args = parser.parse_args(argv)

    app_dir = None if args.skip_exe else build_app()
    archive = make_zip(stage_files(app_dir))
    print(f"{archive} を作成しました。")
    if app_dir is None:
        print("exeは含まれていません。Windows上で --skip-exe なしで実行してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
