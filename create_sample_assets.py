"""
サンプルアセットを作成するスクリプト
背景画像のプレースホルダーを生成
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# プロジェクトルート
ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
IMAGES_DIR = ASSETS_DIR / "images"

def create_background_image():
    """
    シンプルなグラデーション背景画像を作成
    """
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # 画像サイズ
    width, height = 1280, 720

    # 画像を作成
    image = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(image)

    # グラデーション背景（暗めの青〜紫）
    for y in range(height):
        # RGB値を徐々に変化させる
        r = int(20 + (y / height) * 30)
        g = int(20 + (y / height) * 20)
        b = int(40 + (y / height) * 60)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 中央にテキストを追加（オプション）
    try:
        # デフォルトフォントを使用
        text = "2ch/5ch まとめ動画"
        # 画像の中央に薄いテキストを配置
        bbox = draw.textbbox((0, 0), text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (width - text_width) // 2
        y = (height - text_height) // 2

        # 半透明のテキスト効果（グレー）
        draw.text((x, y), text, fill=(80, 80, 80))

    except Exception as e:
        print(f"テキスト追加スキップ: {e}")

    # 保存
    output_path = IMAGES_DIR / "background.png"
    image.save(output_path)

    print(f"✅ 背景画像を作成しました: {output_path}")
    print(f"   サイズ: {width}x{height}")

def create_readme_for_assets():
    """
    assetsフォルダに説明ファイルを作成
    """
    readme_content = """# Assets フォルダ

このフォルダには、動画生成に使用する静的アセットを配置します。

## フォルダ構成

### bgm/
BGM用の音楽ファイル (.mp3) を配置してください。

おすすめフリーBGM:
- DOVA-SYNDROME: https://dova-s.jp/
- 魔王魂: https://maou.audio/

### images/
背景画像やその他の静的画像を配置してください。

必須ファイル:
- background.png (1280x720 推奨)

### fonts/
日本語フォントファイル (.ttf) を配置してください。

推奨フォント:
- Noto Sans JP: https://fonts.google.com/noto/specimen/Noto+Sans+JP
- 配置例: fonts/NotoSansJP-Bold.ttf
"""

    readme_path = ASSETS_DIR / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print(f"✅ アセット説明ファイルを作成しました: {readme_path}")

if __name__ == "__main__":
    print("サンプルアセットを作成します...\n")

    create_background_image()
    create_readme_for_assets()

    print("\n✅ 完了！")
    print("\nさらにカスタマイズするには:")
    print("1. assets/bgm/ にBGMファイル (.mp3) を追加")
    print("2. assets/fonts/ に日本語フォント (.ttf) を追加")
    print("3. assets/images/background.png を好みの画像に置き換え")
