"""
画像タグ付けユーティリティ
CharactersやBackgroundフォルダの画像にAI利用しやすいタグ名をつける

使用方法:
    python tag_images.py

フォルダ内の画像を確認し、タグベースの名前に変更できます。
タグはアンダースコアで区切ります（例: happy_money_success.png）
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import BACKGROUND_IMAGES_DIR, CHARACTER_IMAGES_DIR

# 推奨タグリスト
RECOMMENDED_TAGS = {
    "emotion": [
        "happy", "sad", "angry", "surprise", "worry", "thinking",
        "cry", "laugh", "smile", "shock", "calm", "excited",
    ],
    "topic": [
        "money", "work", "love", "food", "game", "travel",
        "family", "friend", "study", "health", "hobby",
    ],
    "action": [
        "talk", "listen", "walk", "run", "sit", "stand",
        "point", "wave", "nod", "shake",
    ],
    "context": [
        "success", "fail", "advice", "question", "answer",
        "agree", "disagree", "explain", "celebrate",
    ],
}


def print_recommended_tags():
    """推奨タグを表示"""
    print("\n=== 推奨タグリスト ===")
    for category, tags in RECOMMENDED_TAGS.items():
        print(f"\n【{category}】")
        print("  " + ", ".join(tags))


def list_images(folder: Path) -> list:
    """フォルダ内の画像をリスト"""
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)
        return []

    images = []
    for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
        images.extend(folder.glob(ext))
    return sorted(images)


def get_current_tags(filename: str) -> list:
    """ファイル名から現在のタグを抽出"""
    name = Path(filename).stem.lower()
    return [t.strip() for t in name.replace("-", "_").split("_") if t.strip()]


def rename_with_tags(image_path: Path, new_tags: list) -> Path:
    """画像ファイルをタグベースの名前にリネーム"""
    new_name = "_".join(new_tags) + image_path.suffix.lower()
    new_path = image_path.parent / new_name

    if new_path.exists() and new_path != image_path:
        print(f"  エラー: {new_name} は既に存在します")
        return image_path

    image_path.rename(new_path)
    print(f"  リネーム: {image_path.name} → {new_name}")
    return new_path


def interactive_tagging(folder: Path, folder_name: str):
    """対話的にタグ付け"""
    images = list_images(folder)

    if not images:
        print(f"\n{folder_name}フォルダに画像がありません: {folder}")
        return

    print(f"\n=== {folder_name}フォルダの画像 ({len(images)}個) ===")

    for i, img in enumerate(images, 1):
        current_tags = get_current_tags(img.name)
        print(f"\n[{i}/{len(images)}] {img.name}")
        print(f"  現在のタグ: {current_tags if current_tags else '(なし)'}")

        action = input("  アクション [r=リネーム, s=スキップ, q=終了]: ").strip().lower()

        if action == "q":
            break
        elif action == "s":
            continue
        elif action == "r":
            print("  タグをスペース区切りで入力（例: happy money success）")
            tags_input = input("  タグ: ").strip()
            if tags_input:
                new_tags = [t.strip().lower() for t in tags_input.split() if t.strip()]
                if new_tags:
                    rename_with_tags(img, new_tags)


def batch_preview(folder: Path, folder_name: str):
    """フォルダ内の画像とタグを一覧表示"""
    images = list_images(folder)

    if not images:
        print(f"\n{folder_name}フォルダに画像がありません")
        return

    print(f"\n=== {folder_name}フォルダの画像一覧 ===")
    for img in images:
        tags = get_current_tags(img.name)
        print(f"  {img.name}")
        print(f"    → タグ: {tags if tags else '(未設定)'}")


def main():
    print("=" * 50)
    print("画像タグ付けユーティリティ")
    print("=" * 50)

    # フォルダパス
    characters_dir = CHARACTER_IMAGES_DIR
    background_dir = BACKGROUND_IMAGES_DIR

    print(f"\nキャラクターフォルダ: {characters_dir}")
    print(f"背景フォルダ: {background_dir}")

    while True:
        print("\n--- メニュー ---")
        print("1. 推奨タグを表示")
        print("2. キャラクター画像を一覧表示")
        print("3. 背景画像を一覧表示")
        print("4. キャラクター画像をタグ付け")
        print("5. 背景画像をタグ付け")
        print("q. 終了")

        choice = input("\n選択: ").strip().lower()

        if choice == "q":
            print("終了します")
            break
        elif choice == "1":
            print_recommended_tags()
        elif choice == "2":
            batch_preview(characters_dir, "キャラクター")
        elif choice == "3":
            batch_preview(background_dir, "背景")
        elif choice == "4":
            print_recommended_tags()
            interactive_tagging(characters_dir, "キャラクター")
        elif choice == "5":
            print_recommended_tags()
            interactive_tagging(background_dir, "背景")
        else:
            print("無効な選択です")


if __name__ == "__main__":
    main()
