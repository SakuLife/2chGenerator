"""
サムネイル自動生成モジュール
参考: image copy 6.png スタイル（2chまとめ動画サムネイル）

NanoBananaPro で全体を一発生成。PILフォールバック付き。
"""

import json
import os
import platform
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import (
    KIEAI_API_KEY,
    KIEAI_API_BASE,
    THUMBNAIL_DIR,
    FONTS_DIR,
    SCRIPTS_DIR,
    CHARACTER_IMAGES_DIR,
    ensure_directories,
)
from logger import logger

# サイズ
W = 1280
H = 720


# ====================================================================
#  テーマ分割・テキスト準備
# ====================================================================

def _split_theme(theme: str) -> tuple[str, str | None]:
    """テーマをタイトル部とフック部に分割"""
    clean = re.sub(r'【[^】]*】', '', theme).strip()

    for marker in ["方法が", "結果", "末路", "した結果", "だった"]:
        idx = clean.find(marker)
        if 0 < idx < len(clean) - 3:
            return clean[:idx], clean[idx:]

    if len(clean) > 16:
        mid = len(clean) * 2 // 3
        for sep in ["、", "で", "が", "を", "に", "は"]:
            pos = clean[mid - 3:mid + 5].find(sep)
            if pos >= 0:
                c = mid - 3 + pos + 1
                return clean[:c], clean[c:]
        return clean[:mid], clean[mid:]

    return clean, None


def _extract_bubble_texts(script_path: Path | None, theme: str = "") -> list[str]:
    """
    台本から吹き出し用テキストを抽出（4-5本）
    反応・質問系は除外し、具体的なデータ・ためになる情報だけ選ぶ
    """
    EXCLUDE_WORDS = [
        "草", "www", "ww", "すげ", "すごい", "マジか", "マジで", "ガチ",
        "ワロタ", "無理", "やばい", "ヤバい", "それな", "わかる",
        "えぐ", "神", "天才", "参考になる", "真似できん", "羨ましい",
        "うらやま", "欲しい", "つらい", "しんどい", "泣", "涙",
        "怖い", "イメージ", "ワイも", "俺も", "頑張ろう", "みたい",
    ]
    QUESTION_ENDINGS = ["？", "?", "んやろ", "のか", "かな", "やろか", "かね"]

    if script_path and script_path.exists():
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            candidates = []
            for scene in data:
                role = scene.get("role", "")
                text = scene.get("text", "")
                if (role.startswith("res_") or role == "icchi") and 6 <= len(text) <= 30:
                    if any(w in text for w in EXCLUDE_WORDS):
                        continue
                    if any(text.rstrip().endswith(q) for q in QUESTION_ENDINGS):
                        continue
                    candidates.append(text)

            if candidates:
                scored = []
                for t in candidates:
                    score = 0
                    digit_count = sum(1 for c in t if c.isdigit())
                    if digit_count >= 3:
                        score += 5
                    elif digit_count >= 1:
                        score += 3
                    if any(w in t for w in ["万", "円", "年", "月", "%", "歳"]):
                        score += 2
                    if any(w in t for w in ["積立", "投資", "貯金", "節約", "固定費",
                                             "手取り", "家賃", "食費", "保険", "NISA",
                                             "iDeCo", "配当", "利回り", "資産"]):
                        score += 2
                    scored.append((score, t))

                scored.sort(key=lambda x: x[0], reverse=True)
                top = [t for s, t in scored if s >= 3][:10]
                if len(top) >= 3:
                    count = min(5, len(top))
                    return random.sample(top[:8], count)

        except Exception as e:
            logger.warning(f"台本読込エラー: {e}")

    # フォールバック（具体的データ・ためになる情報のみ）
    return [
        "年収600万で月15万貯金してる",
        "固定費 月8万まで削った結果",
        "ふるさと納税で年12万節約",
        "積立NISA満額+iDeCoで月10万",
        "30代で2000万は上位8%",
    ]


def _mask_bubble_texts(texts: list[str]) -> list[str]:
    """
    吹き出しテキストの一部を●で隠してクリック誘導する
    5本中2-3本をランダムにマスク。数字や名詞の一部を●に置換。
    """
    # マスク対象の数字パターン（数字を●に）
    # 例: "月15万" → "月●●万", "年12万" → "年●●万"
    def _mask_numbers(text: str) -> str:
        """テキスト中の数字を●に置換（単位は残す）"""
        result = []
        i = 0
        while i < len(text):
            if text[i].isdigit():
                # 連続する数字を●に
                j = i
                while j < len(text) and text[j].isdigit():
                    j += 1
                result.append("●" * (j - i))
                i = j
            else:
                result.append(text[i])
                i += 1
        return "".join(result)

    # マスク対象の名詞パターン（先頭の漢字2文字を●●に）
    # 例: "固定費" → "●●費", "積立NISA" → "●●NISA"
    NOUN_MASKS = {
        "固定費": "●●費",
        "ふるさと納税": "ふるさと●●",
        "積立NISA": "●●NISA",
    }

    def _mask_one(text: str) -> str:
        """1つのテキストをマスク"""
        # 名詞マスクを先に試す
        for word, masked in NOUN_MASKS.items():
            if word in text:
                return text.replace(word, masked)
        # 名詞マスクが無ければ数字マスク
        return _mask_numbers(text)

    if len(texts) <= 2:
        return texts

    # 2-3本をランダムにマスク対象に選ぶ
    mask_count = random.randint(2, min(3, len(texts)))
    mask_indices = set(random.sample(range(len(texts)), mask_count))

    result = []
    for i, text in enumerate(texts):
        if i in mask_indices:
            result.append(_mask_one(text))
        else:
            result.append(text)
    return result


# ====================================================================
#  NanoBananaPro 全体一発生成
# ====================================================================

def _get_character_variation(title: str) -> dict:
    """
    テーマに応じてキャラクターのバリエーションを決定（イッチを表現）

    Returns:
        {"appearance": str, "expression": str, "pose": str}
    """
    import random

    title_lower = title.lower()

    # 職業・外見パターン
    appearances = [
        "スーツを着た日本人男性サラリーマン",
        "スーツを着た日本人女性OL",
        "カジュアルな服装の若い日本人男性",
        "カジュアルな服装の若い日本人女性",
        "作業着を着た日本人男性",
        "エプロンをつけた主婦",
    ]

    # テーマに応じた外見選択
    if any(word in title_lower for word in ["主婦", "専業", "パート", "家計"]):
        appearance = random.choice(["エプロンをつけた主婦", "カジュアルな服装の若い日本人女性"])
    elif any(word in title_lower for word in ["ol", "女性", "独身女", "彼女"]):
        appearance = "スーツを着た日本人女性OL"
    elif any(word in title_lower for word in ["フリーランス", "副業", "在宅"]):
        appearance = random.choice(["カジュアルな服装の若い日本人男性", "カジュアルな服装の若い日本人女性"])
    elif any(word in title_lower for word in ["工場", "現場", "転職"]):
        appearance = random.choice(["作業着を着た日本人男性", "スーツを着た日本人男性サラリーマン"])
    else:
        appearance = random.choice(appearances)

    # 表情パターン
    expressions = [
        "驚いた表情",
        "困った表情",
        "嬉しそうな笑顔",
        "考え込む表情",
        "ドヤ顔",
        "焦った表情",
    ]

    # テーマに応じた表情選択
    if any(word in title_lower for word in ["成功", "貯め", "達成", "増え", "勝"]):
        expression = random.choice(["嬉しそうな笑顔", "ドヤ顔"])
    elif any(word in title_lower for word in ["失敗", "損", "減", "借金", "後悔"]):
        expression = random.choice(["困った表情", "焦った表情"])
    elif any(word in title_lower for word in ["衝撃", "驚", "まさか"]):
        expression = "驚いた表情"
    else:
        expression = random.choice(expressions)

    # ポーズパターン
    poses = [
        "正面を向いて立っている",
        "腕を組んでいる",
        "頭を抱えている",
        "ガッツポーズをしている",
        "指を立てて説明している",
        "スマホを見ている",
    ]

    # テーマに応じたポーズ選択
    if any(word in title_lower for word in ["成功", "達成", "勝"]):
        pose = random.choice(["ガッツポーズをしている", "指を立てて説明している"])
    elif any(word in title_lower for word in ["失敗", "損", "後悔"]):
        pose = random.choice(["頭を抱えている", "正面を向いて立っている"])
    elif any(word in title_lower for word in ["投資", "株", "nisa"]):
        pose = random.choice(["スマホを見ている", "腕を組んでいる"])
    else:
        pose = random.choice(poses)

    return {"appearance": appearance, "expression": expression, "pose": pose}


def _smart_title_wrap(title: str, max_chars: int = 14) -> str:
    """
    タイトルを適切な位置で改行（単語の途中で切らない）

    Args:
        title: タイトル文字列
        max_chars: 1行の最大文字数

    Returns:
        改行を含むタイトル
    """
    if len(title) <= max_chars:
        return title

    # 改行しやすい位置（助詞の後、句読点の後）
    good_breaks = ["、", "。", "！", "？", "で", "が", "を", "に", "は", "の", "と", "も", "へ", "から", "まで", "より"]
    # 改行してはいけない位置（単語の途中）- 後ろにこれらが来たら切らない
    no_break_before = ["門", "家", "者", "員", "人", "生", "長", "部", "課", "係", "手", "方", "様", "氏", "君", "達"]

    lines = []
    remaining = title

    while remaining:
        if len(remaining) <= max_chars + 2:
            lines.append(remaining)
            break

        # 最適な切り位置を探す
        best_pos = max_chars
        found_good = False

        # 良い切り位置を探す（後ろから前へ）
        for i in range(min(max_chars + 2, len(remaining) - 1), max(max_chars - 5, 0), -1):
            char = remaining[i]
            next_char = remaining[i + 1] if i + 1 < len(remaining) else ""

            # 次の文字が単語の一部なら切らない
            if next_char in no_break_before:
                continue

            # 助詞や句読点の後は良い切り位置
            for sep in good_breaks:
                if remaining[max(0, i-len(sep)+1):i+1].endswith(sep):
                    best_pos = i + 1
                    found_good = True
                    break
            if found_good:
                break

        lines.append(remaining[:best_pos])
        remaining = remaining[best_pos:]

    return "\n".join(lines)


def _build_thumbnail_prompt(
    title: str,
    hook: str | None,
    bubbles: list[str],
) -> str:
    """サムネイル生成用プロンプト（20:07版ベース + データ指示強化）"""
    bubble_colors = [
        "白い背景に細い黒枠",
        "薄い紫の背景に細い暗色枠",
        "薄い青の背景に細い暗色枠",
        "薄い緑の背景に細い暗色枠",
        "薄い黄色の背景に細い暗色枠",
    ]
    bubble_lines = []
    for i, text in enumerate(bubbles[:5]):
        color = bubble_colors[i % len(bubble_colors)]
        bubble_lines.append(f"  - {color}の大きな吹き出し、中に太い黒文字で「{text}」")
    bubble_section = "\n".join(bubble_lines)

    hook_line = ""
    if hook:
        hook_line = f"- 画面下部25%: 非常に大きな太い赤文字（白縁取り）で「{hook}」"

    # テーマに応じたキャラクターバリエーション
    char = _get_character_variation(title)

    # タイトルを適切な位置で改行（単語の途中で切らない）
    wrapped_title = _smart_title_wrap(title, max_chars=14)

    return f"""日本語の2chまとめ動画のYouTubeサムネイル画像を作成してください。

★重要: すべてのテキストは日本語で正確に描画してください。英語禁止。★
★重要: タイトルは以下の改行位置を守ること。単語の途中で改行しないこと。★

レイアウト:
- 画面上部20%: 非常に大きな太い黒文字（白縁取り付き）で以下のタイトルを表示（改行位置を守ること）:
「{wrapped_title}」

- 画面中央55%:
  1. 「いらすとや」スタイルのキャラクターを中央に配置
     ★いらすとやスタイルの特徴（必須）:
     - 丸い頭、ぽっちゃりした体型
     - 太い黒い輪郭線（アウトライン）
     - 目は小さな丸か点、シンプルな口
     - フラットで明るい色使い（グラデーション禁止）
     - {char['appearance']}
     - {char['expression']}で{char['pose']}
  2. キャラクターの周りに大きな吹き出しを5つ配置。吹き出しの中身は具体的な数字データ（感想やリアクションではなく、金額・割合・節約術などの有益情報）:
{bubble_section}

{hook_line}

- 背景: 日本の一万円札（福沢諭吉）が画面いっぱいに散らばっている

スタイル:
- キャラクターは必ず「いらすとや」風のシンプルで可愛いイラスト（リアル調禁止）
- 吹き出しはパステル/淡い色の背景に細い暗色枠、中は太い黒文字
- 吹き出しの中身は「すごい」「草」「マジか」などの感想禁止。具体的な数字・金額・投資データなど有益情報のみ
- 2chまとめ動画サムネイル風の情報量の多い構図
- すべてのテキストは正確な日本語で"""


def _generate_with_ai(prompt: str, output_path: Path) -> Path | None:
    """NanoBananaPro Pro で画像生成"""
    if not KIEAI_API_KEY:
        logger.warning("KIEAI_API_KEY が未設定")
        return None

    try:
        from kieai_client import KieAIClient

        client = KieAIClient(api_key=KIEAI_API_KEY, api_base=KIEAI_API_BASE)
        logger.info("サムネイルAI生成中...")
        logger.info(f"  プロンプト: {prompt[:100]}...")

        result = client.generate_pro_and_download(
            prompt=prompt,
            output_path=output_path,
            aspect_ratio="16:9",
            resolution="2K",
        )
        logger.info(f"サムネイルAI生成完了: {result}")
        return result

    except Exception as e:
        logger.warning(f"AI生成失敗: {e}")
        return None


# ====================================================================
#  PIL フォールバック
# ====================================================================

BUBBLE_STYLES = [
    {"bg": (255, 255, 255, 230), "border": (50, 50, 50)},
    {"bg": (230, 220, 248, 230), "border": (80, 50, 110)},
    {"bg": (215, 235, 255, 230), "border": (50, 80, 140)},
    {"bg": (215, 248, 215, 230), "border": (50, 100, 50)},
    {"bg": (255, 248, 215, 230), "border": (130, 100, 30)},
]

BUBBLE_LAYOUTS = [
    (30, 155, 340),
    (700, 135, 340),
    (30, 340, 340),
    (700, 320, 340),
    (350, 260, 320),
]


def _get_bold_font(size: int) -> ImageFont.FreeTypeFont:
    """太字日本語フォントを取得"""
    asset = FONTS_DIR / "NotoSansJP-Bold.ttf"
    if asset.exists():
        try:
            return ImageFont.truetype(str(asset), size)
        except (OSError, IOError):
            pass

    if platform.system() == "Windows":
        cands = ["C:/Windows/Fonts/meiryob.ttc", "C:/Windows/Fonts/YuGothB.ttc"]
    elif platform.system() == "Darwin":
        cands = ["/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"]
    else:
        cands = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        ]

    for fp in cands:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except (OSError, IOError):
                continue

    return ImageFont.load_default()


def _draw_outlined_text(draw, xy, text, font, fill, outline_color, outline_w):
    """縁取り付きテキスト"""
    x, y = xy
    for dx in range(-outline_w, outline_w + 1):
        for dy in range(-outline_w, outline_w + 1):
            if dx * dx + dy * dy <= outline_w * outline_w:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text((x, y), text, font=font, fill=fill)


def _parse_highlight_segments(text: str) -> list[tuple[str, bool]]:
    """
    テキストを強調部分と通常部分に分割

    Returns:
        [(text, is_highlight), ...]
    """
    import re
    # 金額パターン: 数字+万/円/%/歳/年/ヶ月 等
    pattern = r'(\d+(?:,\d+)*(?:\.\d+)?(?:万|円|%|歳|年|ヶ月|か月|カ月|倍|件|人|回|個|本|枚|kg|g|時間|分|秒|億|千万)?)'

    segments = []
    last_end = 0

    for match in re.finditer(pattern, text):
        # マッチ前の通常テキスト
        if match.start() > last_end:
            segments.append((text[last_end:match.start()], False))
        # マッチした強調テキスト
        segments.append((match.group(), True))
        last_end = match.end()

    # 残りの通常テキスト
    if last_end < len(text):
        segments.append((text[last_end:], False))

    return segments if segments else [(text, False)]


def _draw_highlighted_title(draw, center_x, y, text, font, outline_w):
    """
    金額・数字を強調色で描画するタイトル

    Args:
        draw: ImageDraw
        center_x: 中央X座標
        y: Y座標
        text: テキスト
        font: フォント
        outline_w: 縁取り幅
    """
    segments = _parse_highlight_segments(text)

    # 総幅を計算
    total_width = 0
    segment_widths = []
    for seg_text, _ in segments:
        bbox = draw.textbbox((0, 0), seg_text, font=font)
        w = bbox[2] - bbox[0]
        segment_widths.append(w)
        total_width += w

    # 開始X座標（中央揃え）
    x = center_x - total_width // 2

    # 各セグメントを描画
    NORMAL_COLOR = (15, 15, 15)  # 通常: 黒
    HIGHLIGHT_COLOR = (200, 30, 30)  # 強調: 赤
    OUTLINE_COLOR = (255, 255, 255)  # 縁取り: 白

    for i, (seg_text, is_highlight) in enumerate(segments):
        fill = HIGHLIGHT_COLOR if is_highlight else NORMAL_COLOR
        _draw_outlined_text(draw, (x, y), seg_text, font, fill, OUTLINE_COLOR, outline_w)
        x += segment_widths[i]


def _wrap_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    lines, remaining = [], text
    while remaining:
        if len(remaining) <= max_chars + 2:
            lines.append(remaining)
            break
        cut = max_chars
        best = cut
        for sep in ["、", "で", "が", "を", "に", "は", "の", "と", "万", "…"]:
            idx = remaining[cut - 3:cut + 3].find(sep)
            if idx >= 0:
                best = cut - 3 + idx + 1
                break
        lines.append(remaining[:best])
        remaining = remaining[best:]
    return lines[:4]


def _generate_with_pil(
    title: str,
    hook: str | None,
    bubbles: list[str],
    output_path: Path,
) -> None:
    """PILフォールバック"""
    logger.info("PILフォールバックでサムネイル生成中...")

    bg = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(bg)
    for y in range(H):
        r = 195 + 50 * y // H
        g = 210 + 30 * y // H
        b = 170 + 40 * y // H
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # キャラクター（assetsから）
    chars = list(CHARACTER_IMAGES_DIR.glob("*.png"))
    if chars:
        try:
            char_img = Image.open(random.choice(chars)).convert("RGBA")
            th = int(H * 0.50)
            ratio = th / char_img.height
            tw = min(int(char_img.width * ratio), int(W * 0.30))
            ratio = tw / char_img.width
            th = int(char_img.height * ratio)
            char_img = char_img.resize((tw, th), Image.LANCZOS)
            cx = (W - tw) // 2
            cy = (H - th) // 2 + 20
            bg.paste(char_img, (cx, cy), char_img)
        except Exception:
            pass

    # 吹き出し
    font_b = _get_bold_font(28)
    for i, text in enumerate(bubbles[:min(5, len(BUBBLE_LAYOUTS))]):
        bx, by, max_w = BUBBLE_LAYOUTS[i]
        style = BUBBLE_STYLES[i % len(BUBBLE_STYLES)]
        if len(text) > 18:
            text = text[:16] + "…"
        bbox = draw.textbbox((0, 0), text, font=font_b)
        tw, th_t = bbox[2] - bbox[0], bbox[3] - bbox[1]
        px, py = 16, 10
        x1, y1 = bx, by
        draw.rounded_rectangle(
            [x1, y1, x1 + tw + px * 2, y1 + th_t + py * 2],
            radius=16, fill=style["bg"][:3], outline=style["border"], width=2,
        )
        draw.text((x1 + px, y1 + py), text, font=font_b, fill=(30, 30, 30))

    # タイトル
    font_t = _get_bold_font(60)
    lines = _wrap_text(title, 15)
    sizes = [draw.textbbox((0, 0), l, font=font_t) for l in lines]
    sizes = [(s[2] - s[0], s[3] - s[1]) for s in sizes]
    total_h = sum(h for _, h in sizes) + 8 * (len(sizes) - 1)
    bg_rgba = bg.convert("RGBA")
    banner = Image.new("RGBA", (W, total_h + 28), (255, 255, 255, 215))
    bg_rgba.paste(banner, (0, 0), banner)
    draw2 = ImageDraw.Draw(bg_rgba)
    y_pos = 14
    for i, line in enumerate(lines):
        # 金額・数字を強調色で描画
        _draw_highlighted_title(draw2, W // 2, y_pos, line, font_t, outline_w=4)
        y_pos += sizes[i][1] + 8
    bg.paste(bg_rgba.convert("RGB"))

    # フック
    if hook:
        draw3 = ImageDraw.Draw(bg)
        font_h = _get_bold_font(68)
        hlines = _wrap_text(hook, 18)
        hsizes = [draw3.textbbox((0, 0), l, font=font_h) for l in hlines]
        hsizes = [(s[2] - s[0], s[3] - s[1]) for s in hsizes]
        ht = sum(h for _, h in hsizes) + 8 * (len(hsizes) - 1)
        y_pos = H - ht - 18
        for i, line in enumerate(hlines):
            lw = hsizes[i][0]
            _draw_outlined_text(
                draw3, ((W - lw) // 2, y_pos), line, font_h,
                fill=(220, 20, 20), outline_color=(255, 255, 255), outline_w=6,
            )
            y_pos += hsizes[i][1] + 8

    bg.save(output_path, "JPEG", quality=95)
    logger.info(f"PILフォールバック完了: {output_path}")


# ====================================================================
#  メイン
# ====================================================================

def generate_thumbnail(
    theme: str,
    script_path: Path | None = None,
    output_path: Path | None = None,
) -> dict:
    """
    image copy 6 スタイルのサムネイルを生成

    NanoBananaPro で全体を一発生成（20:07版方式）
    失敗時は PIL フォールバック

    Args:
        theme: 動画テーマ
        script_path: 台本JSONパス（吹き出しテキスト用）
        output_path: 出力パス

    Returns:
        dict: {"path": Path, "kieai_credits": int}
    """
    ensure_directories()

    if output_path is None:
        output_path = THUMBNAIL_DIR / "thumbnail.jpg"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if script_path is None:
        script_path = SCRIPTS_DIR / "script.json"

    # テーマ分割 & 吹き出しテキスト準備
    title, hook = _split_theme(theme)
    bubbles = _extract_bubble_texts(script_path, theme)
    bubbles = _mask_bubble_texts(bubbles)
    logger.info(f"タイトル: {title}")
    logger.info(f"フック: {hook}")
    logger.info(f"吹き出し: {bubbles}")

    kieai_credits = 0

    # ── NanoBananaPro で全体生成 ──
    prompt = _build_thumbnail_prompt(title, hook, bubbles)
    ai_tmp = THUMBNAIL_DIR / "thumb_ai_tmp.png"
    ai_result = _generate_with_ai(prompt, ai_tmp)

    if ai_result and ai_result.exists():
        kieai_credits = 16
        try:
            img = Image.open(ai_result).convert("RGB")
            img = img.resize((W, H), Image.LANCZOS)
            img.save(output_path, "JPEG", quality=95)
            logger.info(f"サムネイル生成完了（AI）: {output_path}")
        except Exception as e:
            logger.warning(f"AI画像読込失敗: {e}")
            _generate_with_pil(title, hook, bubbles, output_path)
    else:
        _generate_with_pil(title, hook, bubbles, output_path)

    # 一時ファイル削除
    if ai_tmp.exists():
        ai_tmp.unlink(missing_ok=True)

    return {"path": output_path, "kieai_credits": kieai_credits}
