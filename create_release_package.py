"""
販売用パッケージ作成スクリプト
納品用のZIPファイルを自動生成します
"""
import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

# プロジェクトルート
ROOT_DIR = Path(__file__).parent
PACKAGE_NAME = "2ch-video-generator"

# 含めるファイル・フォルダ
INCLUDE_PATTERNS = [
    "main.py",
    "setup.py",
    "create_sample_assets.py",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "README.md",
    "QUICKSTART.md",
    "INSTALLATION_GUIDE.md",
    "はじめにお読みください.txt",
    "src/*.py",
]

# 除外するファイル・フォルダ
EXCLUDE_PATTERNS = [
    ".env",           # 実際のAPIキー
    "generated/",     # 生成ファイル
    "__pycache__/",   # Pythonキャッシュ
    "*.pyc",
    ".git/",          # Git管理情報
    ".DS_Store",
    "Thumbs.db",
    "create_release_package.py",  # このスクリプト自体
    "SALES_PACKAGE_GUIDE.md",     # 販売者向けガイド（顧客には不要）
]

def should_exclude(path: Path) -> bool:
    """ファイル/フォルダを除外すべきか判定"""
    path_str = str(path)

    for pattern in EXCLUDE_PATTERNS:
        if pattern in path_str:
            return True

    return False

def copy_directory_structure(src: Path, dst: Path):
    """
    ディレクトリ構造をコピー（除外パターンに従う）
    """
    if not dst.exists():
        dst.mkdir(parents=True)

    for item in src.rglob("*"):
        # 除外パターンチェック
        if should_exclude(item):
            continue

        # 相対パスを計算
        relative_path = item.relative_to(src)
        dest_path = dst / relative_path

        if item.is_file():
            # ファイルをコピー
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_path)
            print(f"  コピー: {relative_path}")
        elif item.is_dir():
            # ディレクトリを作成
            dest_path.mkdir(parents=True, exist_ok=True)

def create_release_package():
    """
    販売用パッケージを作成
    """
    print("=" * 60)
    print("  販売用パッケージ作成")
    print("=" * 60)
    print()

    # タイムスタンプ
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 一時ディレクトリ
    temp_dir = ROOT_DIR / "release_temp"
    package_dir = temp_dir / PACKAGE_NAME

    # ZIPファイル名
    zip_filename = f"{PACKAGE_NAME}_release_{timestamp}.zip"
    zip_path = ROOT_DIR / zip_filename

    try:
        # 一時ディレクトリをクリーンアップ
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        print("1. ファイルをコピー中...")
        copy_directory_structure(ROOT_DIR, package_dir)

        # assets フォルダ構造を作成（空でも良い）
        print("\n2. アセットフォルダ構造を作成...")
        (package_dir / "assets" / "bgm").mkdir(parents=True, exist_ok=True)
        (package_dir / "assets" / "images").mkdir(parents=True, exist_ok=True)
        (package_dir / "assets" / "fonts").mkdir(parents=True, exist_ok=True)

        # アセット用のREADMEを作成
        assets_readme = package_dir / "assets" / "README.md"
        with open(assets_readme, 'w', encoding='utf-8') as f:
            f.write("""# Assets フォルダ

このフォルダには、動画生成に使用する静的アセットを配置します。

## フォルダ構成

### bgm/
BGM用の音楽ファイル (.mp3) を配置してください。

### images/
背景画像を配置してください。
- background.png (1280x720 推奨)

### fonts/
日本語フォントファイル (.ttf) を配置してください。
- 推奨: Noto Sans JP

詳しくは INSTALLATION_GUIDE.md をご覧ください。
""")

        print("  ✅ アセットフォルダ準備完了")

        # 重要ファイルのチェック
        print("\n3. 重要ファイルの確認...")
        required_files = [
            "main.py",
            ".env.example",
            "INSTALLATION_GUIDE.md",
            "はじめにお読みください.txt"
        ]

        missing_files = []
        for file in required_files:
            if not (package_dir / file).exists():
                missing_files.append(file)

        if missing_files:
            print("  ⚠️  以下のファイルが見つかりません:")
            for file in missing_files:
                print(f"    - {file}")
            print("\n  パッケージ作成を中止します。")
            return False

        print("  ✅ すべての重要ファイルが揃っています")

        # 除外すべきファイルがないかチェック
        print("\n4. 除外ファイルの確認...")
        dangerous_files = [".env"]
        found_dangerous = []

        for file in dangerous_files:
            if (package_dir / file).exists():
                found_dangerous.append(file)

        if found_dangerous:
            print("  ❌ 警告: 以下のファイルが含まれています！")
            for file in found_dangerous:
                print(f"    - {file}")
            print("\n  これらのファイルを削除してから再実行してください。")
            return False

        print("  ✅ 問題ありません")

        # ZIPファイル作成
        print(f"\n5. ZIPファイル作成中: {zip_filename}")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in package_dir.rglob("*"):
                if file.is_file():
                    arcname = file.relative_to(temp_dir)
                    zipf.write(file, arcname)

        # ファイルサイズ取得
        file_size_mb = zip_path.stat().st_size / (1024 * 1024)

        print(f"  ✅ 作成完了: {file_size_mb:.2f} MB")

        # 一時ディレクトリを削除
        print("\n6. クリーンアップ中...")
        shutil.rmtree(temp_dir)
        print("  ✅ 完了")

        # 完了メッセージ
        print("\n" + "=" * 60)
        print("  🎉 パッケージ作成完了！")
        print("=" * 60)
        print(f"\nファイル: {zip_path}")
        print(f"サイズ: {file_size_mb:.2f} MB")
        print("\n次のステップ:")
        print("1. ZIPファイルの内容を確認")
        print("2. テスト環境で解凍＆セットアップ実行")
        print("3. 問題なければ顧客に送付")
        print()

        return True

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")

        # クリーンアップ
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        return False

if __name__ == "__main__":
    success = create_release_package()

    if not success:
        exit(1)
