"""
初回セットアップスクリプト
環境確認とサンプルアセットの作成
"""
import subprocess
import sys
import os
from pathlib import Path

def check_python_version():
    """Pythonバージョンチェック"""
    print("1. Pythonバージョンチェック...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
    else:
        print(f"   ❌ Python 3.8以上が必要です（現在: {version.major}.{version.minor}）")
        sys.exit(1)

def check_ffmpeg():
    """FFmpegのインストール確認"""
    print("\n2. FFmpegチェック...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"   ✅ {version_line}")
        else:
            print("   ❌ FFmpegが正しくインストールされていません")
            print_ffmpeg_install_guide()
    except FileNotFoundError:
        print("   ❌ FFmpegが見つかりません")
        print_ffmpeg_install_guide()

def print_ffmpeg_install_guide():
    """FFmpegインストールガイド"""
    print("\n   FFmpegのインストール方法:")
    print("   Windows: choco install ffmpeg")
    print("   macOS:   brew install ffmpeg")
    print("   Linux:   sudo apt install ffmpeg")
    print()

def check_env_file():
    """環境変数ファイルのチェック"""
    print("\n3. 環境変数ファイルチェック...")
    env_path = Path(".env")
    env_example_path = Path(".env.example")

    if env_path.exists():
        print("   ✅ .env ファイルが存在します")

        # APIキーの設定確認
        with open(env_path, 'r') as f:
            content = f.read()

        if "your_openai_api_key_here" in content or "OPENAI_API_KEY=" not in content:
            print("   ⚠️  OpenAI APIキーが設定されていない可能性があります")
            print("      .env ファイルを編集して、APIキーを設定してください")
        else:
            print("   ✅ OpenAI APIキーが設定されています")

    else:
        print("   ⚠️  .env ファイルが見つかりません")
        if env_example_path.exists():
            print("      .env.example をコピーして .env を作成してください")
            print(f"      コマンド: copy .env.example .env  (Windows)")
            print(f"      コマンド: cp .env.example .env    (Mac/Linux)")
        else:
            print("   ❌ .env.example も見つかりません")

def install_dependencies():
    """依存パッケージのインストール"""
    print("\n4. 依存パッケージのインストール...")
    print("   インストール中... (数分かかる場合があります)")

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True
        )
        print("   ✅ 依存パッケージのインストール完了")
    except subprocess.CalledProcessError:
        print("   ❌ インストールに失敗しました")
        sys.exit(1)

def create_sample_assets():
    """サンプルアセットの作成"""
    print("\n5. サンプルアセットの作成...")

    try:
        subprocess.run(
            [sys.executable, "create_sample_assets.py"],
            check=True
        )
    except subprocess.CalledProcessError:
        print("   ⚠️  サンプルアセット作成に失敗しました")
    except FileNotFoundError:
        print("   ⚠️  create_sample_assets.py が見つかりません")

def print_next_steps():
    """次のステップを表示"""
    print("\n" + "=" * 60)
    print("  セットアップ完了！")
    print("=" * 60)
    print("\n次のステップ:")
    print()
    print("1. .env ファイルを編集して、OpenAI APIキーを設定")
    print("   https://platform.openai.com/api-keys でAPIキーを取得")
    print()
    print("2. （オプション）アセットを追加")
    print("   - assets/bgm/ にBGMファイルを追加")
    print("   - assets/fonts/ にフォントファイルを追加")
    print()
    print("3. 動画を生成！")
    print('   python main.py --theme "30代で貯金1000万貯めた話" --auto')
    print()

def main():
    print("=" * 60)
    print("  2ch/5ch まとめ動画自動生成システム")
    print("  セットアップスクリプト")
    print("=" * 60)
    print()

    check_python_version()
    check_ffmpeg()
    install_dependencies()
    check_env_file()
    create_sample_assets()
    print_next_steps()

if __name__ == "__main__":
    main()
