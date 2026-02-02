"""
サムネイル自動生成モジュール
KIEAI NanoBananaPro でイラスト生成 + PIL でテキスト合成
"""

import os
import platform
import random
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from config import (
    KIEAI_API_KEY,
    KIEAI_API_BASE,
    IRASUTOYA_STYLE_PREFIX,
    THUMBNAIL_DIR,
    FONTS_DIR,
    ensure_directories,
)
from logger import logger

# サムネイルサイズ（YouTube推奨）
THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720

# テキスト設定
TITLE_FONT_SIZE = 86
TITLE_OUTLINE_WIDTH = 6
TITLE_MAX_CHARS_PER_LINE = 12

# グラデーション配色パターン（上, 下）
GRADIENT_PATTERNS = [
    ((255, 50, 50), (180, 0, 0)),       # 赤系
    ((50, 120, 255), (0, 50, 180)),     # 青系
    ((255, 180, 0), (220, 120, 0)),     # オレンジ系
    ((0, 180, 100), (0, 120, 60)),      # 緑系
    ((180, 50, 255), (100, 0, 180)),    # 紫系
    ((255, 80, 120), (200, 30, 80)),    # ピンク系
]

# テーマ → イラストプロンプトのマッピング
THEME_PROMPT_MAP = {
    "貯金": "piggy bank overflowing with gold coins, yen money, saving concept",
    "投資": "stock market chart going up, businessman celebrating, gold coins",
    "資産": "pile of gold coins and money bags, wealth concept, treasure",
    "節約": "wallet with yen bills, frugal lifestyle, money saving tips",
    "給料": "salary envelope with yen, office worker, payday concept",
    "借金": "empty wallet, debt concept, worried person with bills",
    "副業": "laptop with money, side business, working from home concept",
    "株": "stock market candlestick chart, bull market, investment success",
    "不動産": "house with yen sign, real estate investment, property",
    "FIRE": "person relaxing on beach, financial freedom, retirement celebration",
    "老後": "elderly couple smiling, retirement savings, pension concept",
    "結婚": "wedding couple, money planning, family finance",
    "転職": "businessman with briefcase, career change, new job",
    "年収": "salary chart going up, income growth, money stacks",
    "NISA": "investment growth chart, NISA logo concept, coins growing",
    "配当": "dividend income, money tree, passive income concept",
    "1000万": "million yen pile, wealth milestone, golden coins stacked high",
    "100万": "yen bills stack, savings goal achieved, celebration",
}

DEFAULT_PROMPT = "Japanese yen money coins and bills, finance concept, colorful illustration"


def _get_bold_font(fontsize: int) -> ImageFont.FreeTypeFont:
    """太字日本語フォントを取得"""
    font = None

    if platform.system() == "Windows":
        candidates = [
            "C:/Windows/Fonts/meiryob.ttc",
            "C:/Windows/Fonts/YuGothB.ttc",
            "C:/Windows/Fonts/msgothic.ttc",
        ]
        for fp in candidates:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, fontsize)
                    break
                except (OSError, IOError):
                    continue
    elif platform.system() == "Darwin":
        candidates = [
            "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        ]
        for fp in candidates:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, fontsize)
                    break
                except (OSError, IOError):
                    continue
    else:
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        ]
        for fp in candidates:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, fontsize, index=0)
                    break
                except (OSError, IOError):
                    continue

    # アセットフォントをフォールバック
    asset_font = FONTS_DIR / "NotoSansJP-Bold.ttf"
    if font is None and asset_font.exists():
        try:
            font = ImageFont.truetype(str(asset_font), fontsize)
        except (OSError, IOError):
            pass

    if font is None:
        logger.warning("太字フォントが見つかりません。デフォルトフォントを使用")
        font = ImageFont.load_default()

    return font


def _create_gradient_background(
    width: int,
    height: int,
    color_top: tuple[int, int, int],
    color_bottom: tuple[int, int, int],
) -> Image.Image:
    """グラデーション背景を生成"""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        ratio = y / height
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * ratio)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * ratio)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    return img


def _build_prompt(theme: str) -> str:
    """テーマからKIEAI NanoBananaPro用プロンプトを構築"""
    subject = DEFAULT_PROMPT
    for keyword, prompt_fragment in THEME_PROMPT_MAP.items():
        if keyword in theme:
            subject = prompt_fragment
            break

    return (
        f"YouTube thumbnail illustration. {subject}. "
        f"{IRASUTOYA_STYLE_PREFIX}, "
        "bright colorful background, high quality, "
        "eye-catching design, no text, no letters, no words, "
        "clean composition, professional thumbnail style"
    )


def _generate_illustration(theme: str, output_path: Path) -> Path | None:
    """KIEAI NanoBananaPro（高品質版）でイラストを生成"""
    if not KIEAI_API_KEY:
        logger.warning("KIEAI_API_KEY が未設定のためイラスト生成をスキップ")
        return None

    try:
        from kieai_client import KieAIClient

        client = KieAIClient(api_key=KIEAI_API_KEY, api_base=KIEAI_API_BASE)
        prompt = _build_prompt(theme)
        logger.info(f"サムネイルイラスト生成（NanoBananaPro）: {prompt[:80]}...")

        image_path = client.generate_pro_and_download(
            prompt=prompt,
            output_path=output_path,
            aspect_ratio="16:9",
            resolution="2K",
        )
        logger.info(f"イラスト生成完了: {image_path}")
        return image_path

    except Exception as e:
        logger.warning(f"イラスト生成失敗（フォールバックで続行）: {e}")
        return None


def _draw_text_with_outline(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int] = (255, 255, 255),
    outline_color: tuple[int, int, int] = (0, 0, 0),
    outline_width: int = TITLE_OUTLINE_WIDTH,
) -> None:
    """縁取り付きテキストを描画"""
    x, y = position
    # 縁取り（8方向 + 太さ分）
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx * dx + dy * dy <= outline_width * outline_width:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    # 本体テキスト
    draw.text((x, y), text, font=font, fill=fill)


def _wrap_theme_text(theme: str, max_chars: int = TITLE_MAX_CHARS_PER_LINE) -> list[str]:
    """テーマテキストを均等に折り返し"""
    if len(theme) <= max_chars:
        return [theme]

    total = len(theme)
    num_lines = (total + max_chars - 1) // max_chars
    num_lines = min(num_lines, 4)
    # 均等分割の目標文字数
    target_per_line = (total + num_lines - 1) // num_lines

    lines = []
    remaining = theme
    while remaining:
        if len(remaining) <= target_per_line + 2:
            lines.append(remaining)
            break

        cut_pos = target_per_line
        # 自然な切れ目を前後で探す
        best_cut = cut_pos
        for sep in ["、", "。", "！", "？", "…", "w"]:
            # 前方に探す
            idx = remaining[:cut_pos + 3].rfind(sep)
            if idx > cut_pos - 4 and idx > 0:
                best_cut = idx + 1
                break

        lines.append(remaining[:best_cut])
        remaining = remaining[best_cut:]

    return lines[:4]


def generate_thumbnail(
    theme: str,
    output_path: Path | None = None,
) -> Path:
    """
    サムネイル画像を生成

    1. KIEAI でテーマに合ったイラストを生成
    2. グラデーション背景にイラストを合成
    3. テーマ文を大きな縁取り文字で描画

    Args:
        theme: 動画テーマ
        output_path: 出力パス（省略時は generated/thumbnail/thumbnail.jpg）

    Returns:
        生成されたサムネイルのパス
    """
    ensure_directories()

    if output_path is None:
        output_path = THUMBNAIL_DIR / "thumbnail.jpg"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. グラデーション背景を生成
    color_top, color_bottom = random.choice(GRADIENT_PATTERNS)
    bg = _create_gradient_background(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT, color_top, color_bottom)

    # 2. KIEAI でイラスト生成・合成
    illustration_path = THUMBNAIL_DIR / "illustration_tmp.png"
    illust_path = _generate_illustration(theme, illustration_path)

    if illust_path and illust_path.exists():
        try:
            illust = Image.open(illust_path).convert("RGBA")
            # イラストをサムネイルサイズにリサイズ
            illust = illust.resize((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), Image.LANCZOS)
            # 半透明で合成（背景グラデーションが少し見える）
            blended = Image.blend(bg.convert("RGBA"), illust, alpha=0.6)
            bg = blended.convert("RGB")
        except Exception as e:
            logger.warning(f"イラスト合成失敗: {e}")

    # 3. 半透明の暗いオーバーレイ（テキスト読みやすくする）
    overlay = Image.new("RGBA", (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), (0, 0, 0, 80))
    bg_rgba = bg.convert("RGBA")
    bg_rgba = Image.alpha_composite(bg_rgba, overlay)

    # 4. テキスト描画
    draw = ImageDraw.Draw(bg_rgba)
    font = _get_bold_font(TITLE_FONT_SIZE)

    lines = _wrap_theme_text(theme)

    # 各行のサイズを計算
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    line_spacing = 16
    total_text_height = sum(line_heights) + line_spacing * (len(lines) - 1)

    # テキストをやや上寄りに配置（上35%あたり）
    y_start = int((THUMBNAIL_HEIGHT - total_text_height) * 0.35)

    for i, line in enumerate(lines):
        line_w = line_widths[i]
        x = (THUMBNAIL_WIDTH - line_w) // 2
        y = y_start + sum(line_heights[:i]) + line_spacing * i

        # 1行目は黄色、それ以降は白（参考サムネイルのスタイル）
        text_color = (255, 215, 0) if i == 0 else (255, 255, 255)
        _draw_text_with_outline(
            draw,
            (x, y),
            line,
            font,
            fill=text_color,
            outline_color=(0, 0, 0),
        )

    # 5. JPEG で保存
    final = bg_rgba.convert("RGB")
    final.save(output_path, "JPEG", quality=95)

    # 一時ファイル削除
    if illustration_path.exists():
        illustration_path.unlink(missing_ok=True)

    logger.info(f"サムネイル生成完了: {output_path}")
    return output_path
