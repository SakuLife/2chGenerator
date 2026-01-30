"""
動画編集スクリプト
台本、音声、画像を統合して最終的な動画を生成

新機能:
- テーマを画面右上に常時表示
- 字幕を画面左側に蓄積表示（2～4個）
- 話者別の枠色
- キャラクターを右側に1種類表示
- 音声に合わせて1つずつ字幕を表示
"""

import json
import textwrap
from pathlib import Path

import numpy as np
from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_audioclips,
)
from PIL import Image, ImageDraw, ImageFont

from config import (
    ASSET_IMAGES_DIR,
    BACKGROUND_VIDEO_OVERLAY_ALPHA,
    BGM_DIR,
    CHARACTER_BOTTOM_MARGIN,
    CHARACTER_HEIGHT_RATIO,
    CHARACTER_IMAGES_DIR,
    CHARACTER_RIGHT_MARGIN,
    DEFAULT_BGM_VOLUME,
    DEFAULT_FONT_SIZE,
    DEFAULT_FPS,
    DEFAULT_VIDEO_SIZE,
    FONTS_DIR,
    GENERATED_DIR,
    ICON_DIR,
    ICON_SIZE,
    ICON_LEFT_MARGIN,
    ICON_BOTTOM_MARGIN,
    IMAGES_DIR,
    INTRO_DURATION,
    INTRO_IMAGE_SCALE,
    INTRO_IMAGES_DIR,
    INTRO_NARRATION_BG_COLOR,
    INTRO_NARRATION_TEXT_COLOR,
    INTRO_THEME_BG_COLOR,
    INTRO_THEME_FONT_SIZE,
    INTRO_THEME_PADDING,
    INTRO_THEME_TEXT_COLOR,
    MAX_VISIBLE_SUBTITLES,
    SCRIPTS_DIR,
    SHOW_SPEAKER_NAME,
    SUBTITLE_LEFT_MARGIN,
    SUBTITLE_MAX_CHARS_PER_LINE,
    SUBTITLE_STACK_MARGIN,
    SUBTITLE_TOP_MARGIN,
    THEME_BG_COLOR,
    THEME_FONT_SIZE,
    THEME_PADDING,
    THEME_RIGHT_MARGIN,
    THEME_TEXT_COLOR,
    THEME_TOP_MARGIN,
    VOICES_DIR,
    ensure_directories,
    get_speaker_style,
)


def get_background_video_path() -> Path | None:
    """
    背景動画ファイルを取得

    Returns:
        動画ファイルのパス、なければNone
    """
    from config import BACKGROUND_IMAGES_DIR

    # 検索するフォルダ（優先順）
    search_dirs = [ASSET_IMAGES_DIR, BACKGROUND_IMAGES_DIR]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for ext in ["*.mp4", "*.mov", "*.avi", "*.webm"]:
            videos = list(search_dir.glob(ext))
            if videos:
                return videos[0]
    return None


def load_background_video(video_path: Path, target_size: tuple, total_duration: float):
    """
    背景動画を読み込み、必要に応じてループ

    Args:
        video_path: 動画ファイルのパス
        target_size: 目標サイズ (width, height)
        total_duration: 必要な総時間

    Returns:
        VideoFileClip (音声なし、リサイズ済み)
    """
    from moviepy import VideoFileClip, vfx

    video = VideoFileClip(str(video_path))

    # 音声を削除
    video = video.without_audio()

    # リサイズ
    video = video.resized(target_size)

    # 必要な長さまでループ
    if video.duration < total_duration:
        loops = int(total_duration / video.duration) + 1
        video = video.with_effects([vfx.Loop(n=loops)])
        video = video.subclipped(0, total_duration)
    else:
        video = video.subclipped(0, total_duration)

    return video
from logger import logger


def get_japanese_font(fontsize: int) -> ImageFont.FreeTypeFont:
    """
    日本語フォントを取得（Windows/Mac/Linux対応）

    Args:
        fontsize: フォントサイズ

    Returns:
        PIL ImageFont
    """
    import os
    import platform

    font = None

    if platform.system() == "Windows":
        font_candidates = [
            "C:/Windows/Fonts/meiryob.ttc",  # メイリオ Bold
            "C:/Windows/Fonts/YuGothB.ttc",   # 游ゴシック Bold
            "C:/Windows/Fonts/msgothic.ttc",  # MSゴシック
            "C:/Windows/Fonts/meiryo.ttc",    # メイリオ
        ]
        for fp in font_candidates:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, fontsize)
                    break
                except (OSError, IOError):
                    continue
    elif platform.system() == "Darwin":  # macOS
        font_candidates = [
            "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
            "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
        ]
        for fp in font_candidates:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, fontsize)
                    break
                except (OSError, IOError):
                    continue
    else:  # Linux
        font_candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        ]
        for fp in font_candidates:
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
        logger.warning("日本語フォントが見つかりません。デフォルトフォントを使用します。")
        font = ImageFont.load_default()

    return font


def smart_text_wrap(text: str, max_chars: int) -> list:
    """
    読みやすい位置で改行するテキスト折り返し

    Args:
        text: 折り返すテキスト
        max_chars: 1行の最大文字数

    Returns:
        行のリスト
    """
    if len(text) <= max_chars:
        return [text]

    # 改行しやすい位置（優先度順）
    # 句読点の後、助詞の後、記号の後
    break_after = ["。", "！", "？", "、", "」", "）", "】", "』", "…", "ｗ", "w"]
    break_before = ["「", "（", "【", "『"]

    lines = []
    current_line = ""

    i = 0
    while i < len(text):
        char = text[i]
        current_line += char

        # 最大文字数に達したら改行位置を探す
        if len(current_line) >= max_chars:
            # 改行位置を後ろから探す
            best_break = -1

            # 改行後の文字をチェック
            for j in range(len(current_line) - 1, max(0, len(current_line) - 8), -1):
                if current_line[j] in break_after:
                    best_break = j + 1
                    break
                if j + 1 < len(current_line) and current_line[j + 1] in break_before:
                    best_break = j + 1
                    break

            if best_break > 0 and best_break < len(current_line):
                # 見つかった位置で改行
                lines.append(current_line[:best_break])
                current_line = current_line[best_break:]
            else:
                # 見つからなければそのまま改行
                lines.append(current_line)
                current_line = ""

        i += 1

    if current_line:
        lines.append(current_line)

    return lines


def intro_theme_text_wrap(text: str, target_chars: int = 12) -> list:
    """
    冒頭テーマ用の改行処理
    文字数の均等性よりも読みやすい位置（助詞・句切り）での改行を優先

    Args:
        text: テーマテキスト
        target_chars: 1行の目標文字数

    Returns:
        行のリスト
    """
    if len(text) <= target_chars + 3:
        return [text]

    # 改行候補位置を収集
    candidates = []
    i = 0
    while i < len(text):
        # 2文字の区切り表現
        if i + 1 < len(text):
            two = text[i:i + 2]
            if two in ('から', 'まで', 'けど', 'ので', 'のに', 'って', 'した', 'する', 'った'):
                candidates.append(i + 2)
                i += 2
                continue

        ch = text[i]

        # 1文字の助詞（前後に文字がある場合のみ）
        if ch in 'がはをにでともへ' and i >= 2 and i < len(text) - 1:
            candidates.append(i + 1)

        # 記号の後
        if ch in '、。！？」）…ｗw':
            candidates.append(i + 1)

        i += 1

    if not candidates:
        return smart_text_wrap(text, target_chars)

    # が/は の後は強い区切り（clause boundary）
    clause_breaks = set()
    for c in candidates:
        if c > 0 and text[c - 1] in 'がは':
            clause_breaks.add(c)

    # 改行位置を貪欲法で選択
    lines = []
    start = 0

    while start < len(text):
        remaining = len(text) - start
        if remaining <= target_chars + 3:
            lines.append(text[start:])
            break

        best = None
        best_dist = float('inf')

        for c in candidates:
            if c <= start:
                continue
            line_len = c - start
            if line_len < target_chars * 0.45:
                continue
            if line_len > target_chars * 1.4:
                break
            dist = abs(line_len - target_chars)
            # 強い区切り（が/は）にはボーナス
            if c in clause_breaks:
                dist = max(0, dist - 3)
            if dist < best_dist:
                best_dist = dist
                best = c

        if best and best > start:
            lines.append(text[start:best])
            start = best
        else:
            # 候補なし: smart_text_wrap にフォールバック
            fallback = smart_text_wrap(text[start:], target_chars)
            lines.extend(fallback)
            break

    return lines


def create_text_image(text: str, role: str, video_size: tuple, max_width: int = None) -> Image.Image:
    """
    枠線付きの2ch風字幕画像を作成

    Args:
        text: 表示するテキスト
        role: キャラクターの役割
        video_size: ビデオサイズ (width, height)
        max_width: 最大幅（指定しない場合は設定値から計算）

    Returns:
        PIL Image (RGBA)
    """
    # スタイル取得
    style = get_speaker_style(role)
    border_color = style["border_color"]
    bg_color = style["bg_color"]
    # text_colorがあれば使用、なければデフォルト
    text_color = style.get("text_color", (30, 30, 30))

    fontsize = DEFAULT_FONT_SIZE
    border_width = 4
    corner_radius = 15
    padding = 20

    # max_widthのデフォルト値を設定
    if max_width is None:
        max_width = int(video_size[0] * 0.6)  # 画面幅の60%

    # 日本語フォントを取得
    font = get_japanese_font(fontsize)

    # 1行あたりの最大文字数（設定値を使用）
    max_chars_per_line = SUBTITLE_MAX_CHARS_PER_LINE
    lines = []

    # 改行で分割後、各行をスマートに折り返す
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        wrapped = smart_text_wrap(paragraph, max_chars_per_line)
        lines.extend(wrapped if wrapped else [""])

    # テキストサイズを計算
    temp_img = Image.new("RGBA", (max_width, 100), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)

    line_heights = []
    max_line_width = 0
    for line in lines:
        bbox = temp_draw.textbbox((0, 0), line or " ", font=font)
        line_heights.append(bbox[3] - bbox[1])
        max_line_width = max(max_line_width, bbox[2] - bbox[0])

    line_spacing = 10
    total_text_height = sum(line_heights) + (len(lines) - 1) * line_spacing

    # 画像サイズ
    img_width = max_line_width + padding * 2 + border_width * 2
    img_height = total_text_height + padding * 2 + border_width * 2

    # RGBA画像を作成
    img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 角丸矩形（枠線）を描画
    draw.rounded_rectangle(
        [0, 0, img_width - 1, img_height - 1],
        radius=corner_radius,
        fill=bg_color,
        outline=border_color,
        width=border_width,
    )

    # テキストを描画
    y = padding + border_width
    for line in lines:
        bbox = draw.textbbox((0, 0), line or " ", font=font)
        text_height = bbox[3] - bbox[1]
        x = padding + border_width  # 左揃え

        # メインテキストを描画
        draw.text((x, y), line or " ", font=font, fill=text_color)
        y += text_height + line_spacing

    return img


def create_theme_image(theme_text: str, video_size: tuple) -> Image.Image:
    """
    テーマ表示用のスタイリッシュな吹き出し画像を作成（画面右上に表示）

    Args:
        theme_text: テーマテキスト
        video_size: ビデオサイズ

    Returns:
        PIL Image (RGBA)
    """
    font = get_japanese_font(THEME_FONT_SIZE)

    # テキストサイズを計算
    temp_img = Image.new("RGBA", (video_size[0], 100), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)

    # 最大幅（画面幅の50%）
    max_width = int(video_size[0] * 0.50)
    max_chars = max(18, int(max_width / (THEME_FONT_SIZE * 0.6)))

    # テキストを折り返し
    lines = textwrap.wrap(theme_text, width=max_chars, break_long_words=True)
    if not lines:
        lines = [theme_text]

    # サイズ計算
    line_heights = []
    max_line_width = 0
    for line in lines:
        bbox = temp_draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])
        max_line_width = max(max_line_width, bbox[2] - bbox[0])

    line_spacing = 4
    total_height = sum(line_heights) + (len(lines) - 1) * line_spacing

    padding_h = THEME_PADDING + 8
    padding_v = THEME_PADDING + 4
    img_width = max_line_width + padding_h * 2
    img_height = total_height + padding_v * 2
    corner_radius = 12

    # 透明画像作成
    img = Image.new("RGBA", (img_width, img_height + 8), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # スタイリッシュな吹き出し（角丸長方形 + グラデーション風）
    # 背景色: ダークグレーのグラデーション風
    bg_color = (35, 35, 45, 235)
    border_color = (80, 80, 100, 255)
    accent_color = (100, 150, 220, 255)

    # 角丸長方形を描画
    x0, y0 = 0, 0
    x1, y1 = img_width - 1, img_height - 1

    # 背景（角丸）
    draw.rounded_rectangle(
        [(x0, y0), (x1, y1)],
        radius=corner_radius,
        fill=bg_color,
        outline=border_color,
        width=2,
    )

    # 上部にアクセントライン
    draw.line(
        [(x0 + corner_radius, y0 + 2), (x1 - corner_radius, y0 + 2)],
        fill=accent_color,
        width=2,
    )

    # テキスト描画（センタリング）
    y = padding_v
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (img_width - text_width) // 2
        # シャドウ効果
        draw.text((x + 1, y + 1), line, font=font, fill=(0, 0, 0, 100))
        draw.text((x, y), line, font=font, fill=THEME_TEXT_COLOR)
        y += (bbox[3] - bbox[1]) + line_spacing

    return img


def create_intro_theme_image(theme_text: str, video_size: tuple) -> Image.Image:
    """
    冒頭用の大きなテーマ画像を作成（上部中央に表示）

    Args:
        theme_text: テーマテキスト
        video_size: ビデオサイズ

    Returns:
        PIL Image (RGBA)
    """
    font = get_japanese_font(INTRO_THEME_FONT_SIZE)

    # 読みやすい位置で改行（助詞・フレーズ区切り優先）
    lines = intro_theme_text_wrap(theme_text, target_chars=12)
    if not lines:
        lines = [theme_text]

    # サイズ計算
    temp_img = Image.new("RGBA", (video_size[0], 300), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)

    line_heights = []
    max_line_width = 0
    for line in lines:
        bbox = temp_draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])
        max_line_width = max(max_line_width, bbox[2] - bbox[0])

    line_spacing = 12
    total_height = sum(line_heights) + (len(lines) - 1) * line_spacing

    padding = INTRO_THEME_PADDING + 10
    img_width = max_line_width + padding * 2
    img_height = total_height + padding * 2

    # 角丸矩形で画像作成
    img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        [0, 0, img_width - 1, img_height - 1],
        radius=18,
        fill=INTRO_THEME_BG_COLOR,
    )

    # テキスト描画（中央揃え）
    y = padding
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = (img_width - line_width) // 2
        draw.text((x, y), line, font=font, fill=INTRO_THEME_TEXT_COLOR)
        y += (bbox[3] - bbox[1]) + line_spacing

    return img


def create_intro_narration_bar(text: str, video_size: tuple) -> Image.Image:
    """
    冒頭用のナレーションバーを作成（下部全幅）

    Args:
        text: ナレーションテキスト
        video_size: ビデオサイズ

    Returns:
        PIL Image (RGBA)
    """
    font = get_japanese_font(DEFAULT_FONT_SIZE)

    # 最大文字数
    max_chars = 40

    # テキストを折り返し
    lines = textwrap.wrap(text, width=max_chars, break_long_words=True)
    if not lines:
        lines = [text]

    # サイズ計算
    temp_img = Image.new("RGBA", (video_size[0], 200), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)

    line_heights = []
    for line in lines:
        bbox = temp_draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])

    line_spacing = 8
    total_height = sum(line_heights) + (len(lines) - 1) * line_spacing
    padding = 15

    # 画面幅いっぱいのバー
    img_width = video_size[0]
    img_height = total_height + padding * 2

    img = Image.new("RGBA", (img_width, img_height), INTRO_NARRATION_BG_COLOR)
    draw = ImageDraw.Draw(img)

    # テキスト描画（中央揃え）
    y = padding
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = (img_width - line_width) // 2
        draw.text((x, y), line, font=font, fill=INTRO_NARRATION_TEXT_COLOR)
        y += (bbox[3] - bbox[1]) + line_spacing

    return img


def load_icon_image(video_size: tuple) -> tuple:
    """
    アイコン画像を読み込み（iconという名前のファイルのみ）

    Returns:
        (icon_image, position) または (None, None)
    """
    if not ICON_DIR.exists():
        return None, None

    # 「icon」という名前のファイルのみ探す
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        icon_path = ICON_DIR / f"icon{ext}"
        if icon_path.exists():
            try:
                icon = Image.open(icon_path).convert("RGBA")
                # リサイズ
                aspect = icon.width / icon.height
                new_width = int(ICON_SIZE * aspect)
                icon = icon.resize((new_width, ICON_SIZE), Image.LANCZOS)

                # 位置（左下）
                pos_x = ICON_LEFT_MARGIN
                pos_y = video_size[1] - ICON_SIZE - ICON_BOTTOM_MARGIN

                return icon, (pos_x, pos_y)
            except Exception:
                pass

    return None, None


def load_ending_icons() -> list:
    """
    アイコンフォルダから「icon」以外のアイコン画像を読み込み
    最後のシーンで使用

    Returns:
        PIL Image のリスト
    """
    if not ICON_DIR.exists():
        return []

    icons = []
    for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
        for path in ICON_DIR.glob(ext):
            # 「icon」という名前以外のファイル（icon.pngなどは除外）
            if path.stem.lower() != "icon":
                try:
                    img = Image.open(path).convert("RGBA")
                    icons.append(img)
                except Exception:
                    pass

    return icons


def create_icon_speech_bubble(
    text: str, icon_img: Image.Image, video_size: tuple
) -> Image.Image:
    """
    アイコンの隣に表示するセリフ風字幕を作成

    Args:
        text: セリフテキスト
        icon_img: アイコン画像
        video_size: ビデオサイズ

    Returns:
        PIL Image (RGBA) - アイコン+吹き出しの合成画像
    """
    font = get_japanese_font(DEFAULT_FONT_SIZE)

    # アイコンサイズ
    icon_size = ICON_SIZE if icon_img else 80
    icon_w = int(icon_size * (icon_img.width / icon_img.height)) if icon_img else icon_size

    # テキストエリアの幅（35文字で折り返し）
    max_chars = 35

    # テキストを折り返し
    lines = smart_text_wrap(text, max_chars)
    if not lines:
        lines = [text]

    # サイズ計算
    temp_img = Image.new("RGBA", (video_size[0], 200), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)

    line_heights = []
    max_line_width = 0
    for line in lines:
        bbox = temp_draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])
        max_line_width = max(max_line_width, bbox[2] - bbox[0])

    line_spacing = 6
    total_text_height = sum(line_heights) + (len(lines) - 1) * line_spacing
    padding = 15

    bubble_width = max_line_width + padding * 2 + 20
    bubble_height = max(total_text_height + padding * 2, icon_size)

    # 全体の画像サイズ（下に余白を確保）
    total_width = icon_w + 15 + bubble_width
    total_height = max(icon_size, bubble_height) + 5

    img = Image.new("RGBA", (total_width, total_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # アイコンを配置
    icon_y = (total_height - icon_size) // 2
    if icon_img:
        resized_icon = icon_img.resize((icon_w, icon_size), Image.LANCZOS)
        img.paste(resized_icon, (0, icon_y), resized_icon)

    # 吹き出しを描画
    bubble_x = icon_w + 15
    bubble_y = (total_height - bubble_height) // 2

    # 吹き出し背景（角丸）
    draw.rounded_rectangle(
        [(bubble_x, bubble_y), (bubble_x + bubble_width, bubble_y + bubble_height)],
        radius=10,
        fill=(40, 40, 50, 230),
        outline=(100, 100, 120, 255),
        width=2,
    )

    # 吹き出しの三角（アイコン方向）
    tri_x = bubble_x
    tri_y = bubble_y + bubble_height // 2
    draw.polygon(
        [(tri_x, tri_y), (tri_x - 10, tri_y - 8), (tri_x - 10, tri_y + 8)],
        fill=(40, 40, 50, 230),
    )

    # テキスト描画
    text_x = bubble_x + padding + 10
    text_y = bubble_y + (bubble_height - total_text_height) // 2
    for line in lines:
        draw.text((text_x, text_y), line, font=font, fill=(255, 255, 255))
        text_y += line_heights[lines.index(line)] + line_spacing

    return img


def load_intro_images(video_size: tuple) -> list:
    """
    冒頭用の画像を読み込み（KIEAI等で生成したもの）
    INTRO_IMAGE_SCALE倍で表示
    INTRO_IMAGES_DIRまたはNANOBANANA_DIRから読み込む

    Returns:
        [(image, position), ...] のリスト
    """
    from config import NANOBANANA_DIR

    # 検索するフォルダ（優先順）
    search_dirs = [INTRO_IMAGES_DIR, NANOBANANA_DIR]

    images = []
    max_images = 3
    # 基準サイズ（元画像512px）をスケールで拡大
    base_size = 512
    target_size = int(base_size * INTRO_IMAGE_SCALE / 2)

    # intro_で始まるファイルを優先的に探す
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
            # intro_で始まるファイルを優先
            for path in sorted(search_dir.glob(f"intro_*{ext[1:]}")):
                if len(images) >= max_images:
                    break
                try:
                    img = Image.open(path).convert("RGBA")
                    aspect = img.width / img.height
                    if aspect >= 1:
                        new_width = target_size
                        new_height = int(target_size / aspect)
                    else:
                        new_height = target_size
                        new_width = int(target_size * aspect)
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                    images.append(img)
                    logger.info(f"冒頭画像読み込み: {path.name}")
                except Exception:
                    pass
        if len(images) >= max_images:
            break

    if not images:
        return []

    # 画像を横に並べて配置（中央揃え）
    spacing = 30
    total_width = sum(img.width for img in images) + spacing * (len(images) - 1)
    start_x = (video_size[0] - total_width) // 2
    y = int(video_size[1] * 0.30)  # 画面の30%の位置

    result = []
    x = start_x
    for img in images:
        result.append((img, (x, y)))
        x += img.width + spacing

    return result


def create_speaker_label(name: str, role: str) -> Image.Image:
    """
    話者名のラベルを作成（字幕の左上に重ねて表示）

    Args:
        name: 話者名（イッチ、名無しさん等）
        role: キャラクターの役割

    Returns:
        PIL Image (RGBA)
    """
    if not name:
        return None

    # スタイル取得
    style = get_speaker_style(role)
    bg_color = style["name_bg_color"] + (255,)  # RGBにAlpha追加
    text_color = style["name_text_color"]

    fontsize = 28
    font = get_japanese_font(fontsize)

    # テキストサイズを計算
    temp_img = Image.new("RGBA", (500, 100), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.textbbox((0, 0), name, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # ラベル画像を作成
    padding_x = 12
    padding_y = 6
    label_w = text_w + padding_x * 2
    label_h = text_h + padding_y * 2

    img = Image.new("RGBA", (label_w, label_h), bg_color)
    draw = ImageDraw.Draw(img)
    draw.text((padding_x, padding_y - 2), name, font=font, fill=text_color)

    return img


def create_subtitle_with_label(text: str, role: str, name: str, video_size: tuple) -> Image.Image:
    """
    名前ラベル付きの字幕画像を作成

    Args:
        text: 字幕テキスト
        role: キャラクターの役割
        name: 話者名
        video_size: ビデオサイズ

    Returns:
        PIL Image (RGBA) - 名前ラベルと字幕を合成した画像
    """
    # 字幕画像を作成
    subtitle_img = create_text_image(text, role, video_size)

    # 名前ラベル非表示の場合はそのまま返す
    if not SHOW_SPEAKER_NAME:
        return subtitle_img

    # 名前ラベルを作成
    label_img = create_speaker_label(name, role)

    if label_img is None:
        return subtitle_img

    # 合成用の大きな画像を作成
    # ラベルは字幕の左上に少しはみ出して配置
    label_offset_x = 15
    label_offset_y = -label_img.height // 2

    total_width = max(subtitle_img.width, label_offset_x + label_img.width)
    total_height = subtitle_img.height + abs(label_offset_y)

    combined = Image.new("RGBA", (total_width, total_height), (0, 0, 0, 0))

    # 字幕を配置（ラベル分下にオフセット）
    subtitle_y = abs(label_offset_y)
    combined.paste(subtitle_img, (0, subtitle_y), subtitle_img)

    # ラベルを配置
    label_y = 0
    combined.paste(label_img, (label_offset_x, label_y), label_img)

    return combined


def calculate_subtitle_positions(
    subtitles: list, video_size: tuple
) -> list:
    """
    字幕の蓄積位置を計算（画像の高さを考慮）

    Args:
        subtitles: 表示する字幕リスト（各要素は画像高さを持つ）
        video_size: ビデオサイズ

    Returns:
        [(x, y), ...] 各字幕の位置リスト
    """
    positions = []
    current_y = SUBTITLE_TOP_MARGIN
    max_y = video_size[1] - 30  # 下部30pxマージン

    for sub in subtitles:
        # 画面下端を超える場合は追加しない
        if current_y + sub["height"] > max_y:
            break
        x = SUBTITLE_LEFT_MARGIN
        y = current_y
        positions.append((x, y))
        current_y += sub["height"] + SUBTITLE_STACK_MARGIN

    return positions


def get_all_character_images() -> list:
    """
    キャラクター画像を全て取得

    Returns:
        [(path, tags), ...] - パスとタグのリスト
    """
    char_dir = CHARACTER_IMAGES_DIR
    if not char_dir.exists():
        return []

    images = []
    for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
        for path in char_dir.glob(ext):
            # ファイル名からタグを抽出（例: happy_money_success.png → ["happy", "money", "success"]）
            name = path.stem.lower()
            tags = [t.strip() for t in name.replace("-", "_").split("_") if t.strip()]
            images.append({"path": path, "tags": tags, "name": name})

    return images


def get_character_image_path() -> Path | None:
    """
    デフォルトのキャラクター画像を取得（後方互換性のため）

    Returns:
        キャラクター画像のパス、なければNone
    """
    images = get_all_character_images()
    if images:
        return images[0]["path"]
    return None


def load_character_images(video_size: tuple) -> list:
    """
    全キャラクター画像を読み込んでリサイズ

    Args:
        video_size: ビデオサイズ

    Returns:
        [{"path": Path, "tags": list, "image": PIL.Image}, ...]
    """
    images = get_all_character_images()
    loaded = []

    char_height = int(video_size[1] * CHARACTER_HEIGHT_RATIO)

    for img_data in images:
        try:
            img = Image.open(img_data["path"]).convert("RGBA")
            aspect = img.width / img.height
            char_width = int(char_height * aspect)
            img = img.resize((char_width, char_height), Image.LANCZOS)
            loaded.append({
                "path": img_data["path"],
                "tags": img_data["tags"],
                "name": img_data["name"],
                "image": img,
                "width": char_width,
                "height": char_height,
            })
        except Exception as e:
            logger.warning(f"キャラ画像読み込みエラー: {img_data['path']} - {e}")

    return loaded


def select_character_for_context(images: list, context_keywords: list, used_indices: set) -> int:
    """
    コンテキストに合ったキャラクター画像を選択

    Args:
        images: 画像リスト
        context_keywords: コンテキストのキーワード
        used_indices: 既に使用した画像のインデックス

    Returns:
        選択された画像のインデックス
    """
    if not images:
        return -1

    # 未使用の画像を優先
    available = [i for i in range(len(images)) if i not in used_indices]
    if not available:
        # 全て使用済みならリセット
        available = list(range(len(images)))

    # キーワードマッチングでスコア付け
    best_idx = available[0]
    best_score = 0

    for idx in available:
        img = images[idx]
        score = sum(1 for kw in context_keywords if any(kw in tag for tag in img["tags"]))
        if score > best_score:
            best_score = score
            best_idx = idx

    return best_idx


def extract_keywords_from_subtitles(subtitles: list) -> list:
    """
    字幕からキーワードを抽出

    Args:
        subtitles: 字幕リスト

    Returns:
        キーワードリスト
    """
    keywords = []
    keyword_map = {
        # お金関連
        "貯金": ["money", "saving", "happy"],
        "投資": ["invest", "stock", "money", "thinking"],
        "借金": ["debt", "sad", "worry", "money"],
        "節約": ["saving", "frugal", "money"],
        "給料": ["salary", "work", "money"],
        "収入": ["income", "money", "work"],
        "支出": ["expense", "money"],
        "万円": ["money"],
        "円": ["money"],
        # 感情
        "嬉しい": ["happy", "joy", "smile"],
        "悲しい": ["sad", "cry"],
        "怒り": ["angry", "mad"],
        "驚き": ["surprise", "shock"],
        "困る": ["worry", "trouble", "thinking"],
        "笑": ["happy", "laugh", "smile"],
        "泣": ["sad", "cry"],
        "怖い": ["fear", "worry"],
        "楽しい": ["happy", "excited"],
        # 結果
        "成功": ["success", "happy", "celebrate"],
        "失敗": ["fail", "sad", "worry"],
        "勝ち": ["success", "happy", "celebrate"],
        "負け": ["fail", "sad"],
        "やった": ["success", "happy", "excited"],
        "ダメ": ["fail", "sad", "worry"],
        # 状況
        "仕事": ["work", "thinking"],
        "転職": ["work", "thinking", "worry"],
        "結婚": ["love", "happy", "family"],
        "恋愛": ["love", "happy"],
        "別れ": ["sad", "love"],
        "旅行": ["travel", "happy", "excited"],
        "食事": ["food", "happy"],
        "ゲーム": ["game", "happy", "excited"],
        "勉強": ["study", "thinking"],
        "健康": ["health", "worry"],
        "病気": ["health", "sad", "worry"],
        # 会話
        "質問": ["question", "thinking"],
        "答え": ["answer", "explain"],
        "アドバイス": ["advice", "explain", "thinking"],
        "相談": ["advice", "thinking", "worry"],
        "説明": ["explain", "thinking"],
        "なるほど": ["agree", "thinking", "nod"],
        "そうだね": ["agree", "nod"],
        "違う": ["disagree", "shake"],
    }

    for sub in subtitles:
        text = sub.get("text", "") if isinstance(sub, dict) else ""
        for jp_word, en_tags in keyword_map.items():
            if jp_word in text:
                keywords.extend(en_tags)

    return list(set(keywords))


def create_video_with_stacked_subtitles(
    subtitles_data: list,
    voice_map: dict,
    theme_text: str,
    video_size: tuple = DEFAULT_VIDEO_SIZE,
) -> tuple:
    """
    字幕蓄積表示の動画を作成

    Args:
        subtitles_data: 字幕データリスト
        voice_map: {index: voice_path} のマップ
        theme_text: テーマテキスト
        video_size: ビデオサイズ

    Returns:
        (total_duration, make_frame, audio_clips, bg_video) - 動画長、フレーム関数、音声リスト、背景動画
    """
    # 背景動画または画像を準備
    bg_video_path = get_background_video_path()
    bg_video_clip = None  # 後で設定（total_duration計算後）
    use_video_background = bg_video_path is not None
    background_img = None  # 静止画用（動画背景時は使わない）

    if use_video_background:
        logger.info(f"背景動画を使用: {bg_video_path.name}")
    else:
        # 静止画背景
        background_path = ASSET_IMAGES_DIR / "background.png"
        if background_path.exists():
            background_img = Image.open(background_path).convert("RGBA")
            background_img = background_img.resize(video_size, Image.LANCZOS)
        else:
            logger.warning("背景画像が見つかりません。ダークグレー背景を使用します。")
            background_img = Image.new("RGBA", video_size, (40, 45, 55, 255))

    # 白オーバーレイを準備（背景動画用）
    white_overlay = Image.new("RGBA", video_size, (255, 255, 255, int(255 * BACKGROUND_VIDEO_OVERLAY_ALPHA)))

    # キャラクター画像を全て読み込み
    all_char_images = load_character_images(video_size)
    logger.info(f"キャラクター画像数: {len(all_char_images)}")

    # デフォルトキャラクター（画像がない場合のフォールバック）
    default_char_img = None
    default_char_position = None

    if all_char_images:
        first_char = all_char_images[0]
        default_char_img = first_char["image"]
        char_x = video_size[0] - first_char["width"] - CHARACTER_RIGHT_MARGIN
        char_y = video_size[1] - first_char["height"] - CHARACTER_BOTTOM_MARGIN
        default_char_position = (char_x, char_y)

    # テーマ画像を作成（本編用：小さく右上）
    theme_img = None
    theme_position = None
    if theme_text:
        theme_img = create_theme_image(theme_text, video_size)
        theme_x = video_size[0] - theme_img.width - THEME_RIGHT_MARGIN
        theme_y = THEME_TOP_MARGIN
        theme_position = (theme_x, theme_y)

    # 冒頭用要素を準備
    intro_theme_img = None
    intro_theme_position = None
    if theme_text:
        intro_theme_img = create_intro_theme_image(theme_text, video_size)
        intro_theme_x = (video_size[0] - intro_theme_img.width) // 2
        # Y位置: 上から5%を基準にしつつ、見切れないよう最低20px確保
        intro_theme_y = max(20, int(video_size[1] * 0.05))
        intro_theme_position = (intro_theme_x, intro_theme_y)

    # アイコンを読み込み
    icon_img, icon_position = load_icon_image(video_size)
    if icon_img:
        logger.info(f"アイコンを読み込みました")

    # 最後のシーン用の別ポーズアイコンを読み込み
    ending_icons = load_ending_icons()
    if ending_icons:
        logger.info(f"エンディング用アイコン: {len(ending_icons)}枚")

    # 冒頭用画像を読み込み
    intro_images = load_intro_images(video_size)
    if intro_images:
        logger.info(f"冒頭用画像: {len(intro_images)}枚")

    # 字幕画像を事前生成
    subtitle_images = []
    stack_subtitles = []  # 蓄積対象の字幕
    special_subtitles = []  # ナレーター/タイトル

    for sub in subtitles_data:
        role = sub.get("role", "narrator")
        text = sub.get("text", "")
        name = sub.get("name", "")

        if role in ["narrator", "title_card"]:
            img = create_text_image(text, role, video_size)
        else:
            img = create_subtitle_with_label(text, role, name, video_size)

        sub_data = {
            "image": img,
            "width": img.width,
            "height": img.height,
            "role": role,
            "text": text,
            "start_time": sub.get("start_time", 0),
            "duration": sub.get("duration", 3.0),
            "index": sub.get("index", 0),
        }
        subtitle_images.append(sub_data)

        if role in ["narrator", "title_card"]:
            special_subtitles.append(sub_data)
        else:
            stack_subtitles.append(sub_data)

    # 蓄積字幕をグループに分ける（画面高さに収まるように）
    subtitle_groups = []
    used_char_indices = set()
    max_group_height = video_size[1] - SUBTITLE_TOP_MARGIN - 30  # 下部30pxマージン

    i = 0
    while i < len(stack_subtitles):
        group = []
        total_height = 0
        while i < len(stack_subtitles) and len(group) < MAX_VISIBLE_SUBTITLES:
            sub = stack_subtitles[i]
            added_height = sub["height"] + (SUBTITLE_STACK_MARGIN if group else 0)
            if total_height + added_height > max_group_height and group:
                break  # これ以上追加すると画面からはみ出す
            group.append(sub)
            total_height += added_height
            i += 1
        if group:
            # グループの表示期間を計算
            group_start = group[0]["start_time"]
            last_sub = group[-1]
            group_end = last_sub["start_time"] + last_sub["duration"]

            # グループのキーワードを抽出してキャラクターを選択
            keywords = extract_keywords_from_subtitles(group)
            char_idx = select_character_for_context(all_char_images, keywords, used_char_indices)

            # キャラクター画像と位置を設定
            char_img = None
            char_position = None
            if char_idx >= 0 and char_idx < len(all_char_images):
                used_char_indices.add(char_idx)
                char_data = all_char_images[char_idx]
                char_img = char_data["image"]
                char_x = video_size[0] - char_data["width"] - CHARACTER_RIGHT_MARGIN
                char_y = video_size[1] - char_data["height"] - CHARACTER_BOTTOM_MARGIN
                char_position = (char_x, char_y)
                logger.info(f"グループ{len(subtitle_groups)+1}: キャラクター={char_data['name']}")
            elif default_char_img:
                char_img = default_char_img
                char_position = default_char_position

            subtitle_groups.append({
                "subtitles": group,
                "start_time": group_start,
                "end_time": group_end,
                "char_img": char_img,
                "char_position": char_position,
            })

            # 全キャラクター使用済みならリセット
            if len(used_char_indices) >= len(all_char_images):
                used_char_indices.clear()

    logger.info(f"字幕グループ数: {len(subtitle_groups)}")

    # 総時間を計算
    if subtitle_images:
        last_sub = max(subtitle_images, key=lambda x: x["start_time"] + x["duration"])
        total_duration = last_sub["start_time"] + last_sub["duration"]
    else:
        total_duration = 5.0

    # 背景動画を読み込み（総時間が決まってから）
    if use_video_background:
        bg_video_clip = load_background_video(bg_video_path, video_size, total_duration)
        logger.info(f"背景動画を読み込み完了: {total_duration:.2f}秒")

    # フレームごとの画像を生成する関数
    import math

    # 冒頭セクションの終了時間を計算（最初のicchi/res_*が始まる時間）
    intro_end_time = INTRO_DURATION
    for sub in subtitles_data:
        if sub.get("role") not in ["narrator", "title_card"]:
            intro_end_time = sub.get("start_time", INTRO_DURATION)
            break

    logger.info(f"冒頭セクション: 0 - {intro_end_time:.2f}秒")

    # 最後のナレーター（エンディング）を特定
    ending_narrator = None
    if special_subtitles:
        last_special = special_subtitles[-1]
        if last_special.get("role") == "narrator":
            ending_narrator = last_special
            logger.info(f"エンディングナレーター: {ending_narrator['start_time']:.2f}秒〜")

    # 中間ナレーター（冒頭・エンディング以外）を特定
    mid_story_narrators = []
    for sub in special_subtitles:
        if sub.get("role") != "narrator":
            continue
        st = sub["start_time"]
        # 冒頭セクション外 かつ エンディング以外
        if st >= intro_end_time and sub is not ending_narrator:
            mid_story_narrators.append(sub)
    if mid_story_narrators:
        logger.info(f"中間ナレーター数: {len(mid_story_narrators)}")

    def make_frame(t):
        # ベース画像（背景）
        if use_video_background and bg_video_clip:
            # 動画フレームを取得
            video_frame = bg_video_clip.get_frame(t)
            frame = Image.fromarray(video_frame).convert("RGBA")
            # 白オーバーレイを合成
            frame = Image.alpha_composite(frame, white_overlay)
        else:
            frame = background_img.copy()

        # ====== エンディングセクション（最後のナレーター）======
        if ending_narrator:
            ending_start = ending_narrator["start_time"]
            ending_end = ending_start + ending_narrator["duration"]

            if ending_start <= t < ending_end:
                # 大きなアイコンを中央に揺らしながら表示
                if ending_icons:
                    # アイコンを選択（時間で切り替え可能）
                    icon_idx = 0
                    ending_icon = ending_icons[icon_idx]

                    # 大きくリサイズ（画面高さの75%）
                    target_h = int(video_size[1] * 0.75)
                    aspect = ending_icon.width / ending_icon.height
                    target_w = int(target_h * aspect)
                    large_icon = ending_icon.resize((target_w, target_h), Image.LANCZOS)

                    # ふわふわエフェクト（キャラクターと同じ控えめな上下動）
                    # 周期3秒、振幅8pxの緩やかなsin波
                    bob_offset = int(math.sin(t * 2 * math.pi / 3) * 8)

                    icon_x = (video_size[0] - target_w) // 2
                    icon_y = int(video_size[1] * 0.15) + bob_offset

                    frame.paste(large_icon, (icon_x, icon_y), large_icon)

                # アイコン付き吹き出し字幕を下部に表示
                if icon_img:
                    speech = create_icon_speech_bubble(
                        ending_narrator.get("text", ""), icon_img, video_size
                    )
                    speech_x = ICON_LEFT_MARGIN
                    speech_y = video_size[1] - speech.height - ICON_BOTTOM_MARGIN
                    frame.paste(speech, (speech_x, speech_y), speech)

                return np.array(frame.convert("RGB"))

        # ====== 冒頭セクション ======
        if t < intro_end_time:
            # 冒頭テーマを中央上部に大きく表示
            if intro_theme_img and intro_theme_position:
                frame.paste(intro_theme_img, intro_theme_position, intro_theme_img)

            # 冒頭用画像を表示（テーマの下）
            for img, pos in intro_images:
                frame.paste(img, pos, img)

            # 冒頭ナレーション字幕をアイコン付き吹き出しで下部に表示
            for sub in special_subtitles:
                start = sub["start_time"]
                end = start + sub["duration"]
                if start <= t < end and sub.get("role") != "title_card":
                    text = sub.get("text", "")
                    if text and icon_img:
                        speech = create_icon_speech_bubble(text, icon_img, video_size)
                        speech_x = ICON_LEFT_MARGIN
                        speech_y = video_size[1] - speech.height - ICON_BOTTOM_MARGIN
                        frame.paste(speech, (speech_x, speech_y), speech)
                    break

            return np.array(frame.convert("RGB"))

        # ====== メインコンテンツセクション ======

        # 中間ナレーターが現在アクティブか確認
        mid_narrator_active = False
        for sub in mid_story_narrators:
            mn_start = sub["start_time"]
            mn_end = mn_start + sub["duration"]
            if mn_start <= t < mn_end:
                mid_narrator_active = True
                # テーマを右上に小さく表示
                if theme_img and theme_position:
                    frame.paste(theme_img, theme_position, theme_img)
                # アイコン付き吹き出しを下部に表示（冒頭と同じ形式）
                if icon_img:
                    speech = create_icon_speech_bubble(
                        sub.get("text", ""), icon_img, video_size
                    )
                    speech_x = ICON_LEFT_MARGIN
                    speech_y = video_size[1] - speech.height - ICON_BOTTOM_MARGIN
                    frame.paste(speech, (speech_x, speech_y), speech)
                break

        if mid_narrator_active:
            return np.array(frame.convert("RGB"))

        # 現在表示すべきグループを特定
        current_group = None
        for group in subtitle_groups:
            if group["start_time"] <= t < group["end_time"]:
                current_group = group
                break

        # キャラクターを描画（グループに応じて切り替え、上下にゆっくり動くエフェクト）
        char_img = current_group["char_img"] if current_group and current_group.get("char_img") else default_char_img
        char_position = current_group["char_position"] if current_group and current_group.get("char_position") else default_char_position

        if char_img and char_position:
            # sin波で上下に動かす（周期3秒、振幅8px）
            bob_offset = int(math.sin(t * 2 * math.pi / 3) * 8)
            animated_pos = (char_position[0], char_position[1] + bob_offset)
            frame.paste(char_img, animated_pos, char_img)

        # テーマを右上に小さく表示
        if theme_img and theme_position:
            frame.paste(theme_img, theme_position, theme_img)

        # グループ内の字幕を蓄積表示
        if current_group:
            current_y = SUBTITLE_TOP_MARGIN
            max_y = video_size[1] - 30  # 下部30pxマージン
            for sub in current_group["subtitles"]:
                # この字幕が始まっているかチェック
                if sub["start_time"] <= t:
                    # 画面下端を超える場合は描画しない
                    if current_y + sub["height"] > max_y:
                        break
                    img = sub["image"]
                    x = SUBTITLE_LEFT_MARGIN
                    y = current_y
                    frame.paste(img, (x, y), img)
                    current_y += sub["height"] + SUBTITLE_STACK_MARGIN

        return np.array(frame.convert("RGB"))

    # 音声クリップを作成
    audio_clips = []
    for sub in subtitle_images:
        idx = sub["index"]
        if idx in voice_map:
            voice_path = Path(voice_map[idx])
            if voice_path.exists():
                try:
                    audio = AudioFileClip(str(voice_path))
                    audio = audio.with_start(sub["start_time"])
                    audio_clips.append(audio)
                except Exception as e:
                    logger.warning(f"音声読み込みエラー [{idx}]: {e}")

    return total_duration, make_frame, audio_clips, bg_video_clip


def create_video_from_script(
    script_path: Path,
    output_filename: str = "output_video.mp4",
    use_bgm: bool = True,
) -> Path:
    """
    台本から最終動画を生成（字幕蓄積表示対応）

    Args:
        script_path: 台本JSONファイルのパス
        output_filename: 出力ファイル名
        use_bgm: BGMを使用するか

    Returns:
        生成された動画ファイルのパス
    """
    from moviepy import VideoClip

    ensure_directories()

    # 台本を読み込み
    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    logger.info(f"台本を読み込みました: {script_path.name}")
    logger.info(f"シーン数: {len(script)}個")

    # テーマを取得（title_cardのテキストのみ）
    theme_text = ""
    for scene in script:
        if scene.get("role") == "title_card":
            theme_text = scene.get("text", "")
            break

    # 字幕タイミング情報を読み込み
    subtitles_path = VOICES_DIR / "subtitles.json"
    subtitles_list = []

    if subtitles_path.exists():
        with open(subtitles_path, "r", encoding="utf-8") as f:
            subtitles_data = json.load(f)
        subtitles_list = subtitles_data.get("subtitles", [])
        logger.info(
            f"字幕タイミング情報を読み込みました: 総時間 {subtitles_data.get('total_duration', 0):.2f}秒"
        )
    else:
        # 字幕情報がない場合は台本から生成
        logger.warning("subtitles.jsonが見つかりません。台本から字幕情報を生成します。")
        current_time = 0.0
        for i, scene in enumerate(script):
            duration = 3.0  # デフォルト
            subtitles_list.append({
                "index": i,
                "role": scene.get("role", "narrator"),
                "name": scene.get("name", ""),
                "text": scene.get("text", ""),
                "start_time": current_time,
                "duration": duration,
            })
            current_time += duration

    # 音声マップを読み込み
    voice_map_path = VOICES_DIR / "voice_map.json"
    voice_map = {}
    if voice_map_path.exists():
        with open(voice_map_path, "r", encoding="utf-8") as f:
            voice_map = {int(k): v for k, v in json.load(f).items()}

    logger.info("字幕蓄積表示で動画を生成中...")

    # 動画を作成
    total_duration, make_frame, audio_clips, bg_video_clip = create_video_with_stacked_subtitles(
        subtitles_list,
        voice_map,
        theme_text,
        DEFAULT_VIDEO_SIZE,
    )

    logger.info(f"総時間: {total_duration:.2f}秒")

    # VideoClipを作成
    video = VideoClip(make_frame, duration=total_duration)

    # 音声を合成
    if audio_clips:
        logger.info(f"音声クリップ数: {len(audio_clips)}")
        combined_audio = CompositeAudioClip(audio_clips)
        video = video.with_audio(combined_audio)

    # BGMを追加
    if use_bgm:
        bgm_files = list(BGM_DIR.glob("*.mp3"))
        if bgm_files:
            import random
            selected_bgm = random.choice(bgm_files)
            logger.info(f"BGMを追加中: {selected_bgm.name}")
            try:
                bgm = AudioFileClip(str(selected_bgm))

                # 音量調整
                bgm = bgm.with_volume_scaled(DEFAULT_BGM_VOLUME)

                # BGMをループまたはカット
                if bgm.duration < total_duration:
                    loops = int(total_duration / bgm.duration) + 1
                    bgm = concatenate_audioclips([bgm] * loops).subclipped(0, total_duration)
                else:
                    bgm = bgm.subclipped(0, total_duration)

                # 音声合成
                if video.audio:
                    final_audio = CompositeAudioClip([video.audio, bgm])
                    video = video.with_audio(final_audio)
                else:
                    video = video.with_audio(bgm)

            except Exception as e:
                logger.error(f"BGM追加エラー: {e}")

    # 動画出力
    output_path = GENERATED_DIR / output_filename
    logger.info(f"\n動画を書き出し中: {output_path}")

    video.write_videofile(
        str(output_path),
        fps=DEFAULT_FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
    )

    # 背景動画クリップをクリーンアップ
    if bg_video_clip:
        try:
            bg_video_clip.close()
        except Exception:
            pass

    logger.info(f"\n動画生成完了！")
    logger.info(f"出力先: {output_path}")
    logger.info(f"長さ: {total_duration:.2f}秒")

    return output_path


if __name__ == "__main__":
    script_path = SCRIPTS_DIR / "script.json"

    if not script_path.exists():
        print(f"エラー: 台本ファイルが見つかりません: {script_path}")
        exit(1)

    create_video_from_script(script_path)
