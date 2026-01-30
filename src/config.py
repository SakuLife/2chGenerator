"""
設定ファイル
環境変数の読み込みとパスの設定
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# APIキー設定
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
KIEAI_API_KEY = os.getenv("KIEAI_API_KEY")
KIEAI_API_BASE = os.getenv("KIEAI_API_BASE", "https://api.kieai.net")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Gemini API（課金版）

# YouTube / Google API設定
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "client_secrets.json")
GOOGLE_SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")

# プロジェクトのルートディレクトリ
ROOT_DIR = Path(__file__).parent.parent

# ディレクトリパス
ASSETS_DIR = ROOT_DIR / "assets"
GENERATED_DIR = ROOT_DIR / "generated"
SCRIPTS_DIR = GENERATED_DIR / "scripts"
VOICES_DIR = GENERATED_DIR / "voices"
IMAGES_DIR = GENERATED_DIR / "images"
CACHE_DIR = GENERATED_DIR / "cache"
IMAGE_CACHE_DIR = CACHE_DIR / "images"

# アセットパス
BGM_DIR = ASSETS_DIR / "bgm"
ASSET_IMAGES_DIR = ASSETS_DIR / "images"
CHARACTER_IMAGES_DIR = ASSETS_DIR / "images" / "characters"
BACKGROUND_IMAGES_DIR = ASSETS_DIR / "images" / "backgrounds"
ICON_DIR = ASSETS_DIR / "images" / "icon"
NANOBANANA_DIR = ASSETS_DIR / "images" / "nanobanana"  # KIEAI生成画像保存先
INTRO_IMAGES_DIR = GENERATED_DIR / "intro_images"  # 冒頭用生成画像（一時）
FONTS_DIR = ASSETS_DIR / "fonts"

# 冒頭画像設定
INTRO_IMAGE_SCALE = 1.2  # 冒頭画像の表示倍率

# いらすとや風スタイルプレフィックス
IRASUTOYA_STYLE_PREFIX = """
Irasutoya illustration style, simple flat design, cute Japanese
illustration, pastel colors, white background, no outlines,
soft rounded shapes, kawaii characters, minimal details,
deformed style with big head and small body
"""

# デフォルト設定
DEFAULT_VIDEO_SIZE = (1280, 720)
DEFAULT_FPS = 24
DEFAULT_FONT_SIZE = 28  # 字幕用フォントサイズ（7割サイズ）
DEFAULT_BGM_VOLUME = 0.1

# 字幕蓄積設定
MAX_VISIBLE_SUBTITLES = 4  # 同時表示する最大字幕数
SUBTITLE_STACK_MARGIN = 18  # 字幕間のマージン（増加）
SUBTITLE_LEFT_MARGIN = 25  # 左端からのマージン
SUBTITLE_TOP_MARGIN = 144  # 上端からのマージン（画面高さの20%）
SUBTITLE_MAX_CHARS_PER_LINE = 25  # 1行あたりの最大文字数
SHOW_SPEAKER_NAME = False  # 話者名ラベルを表示するか

# テーマ表示設定（本編中：右上に小さく黒）
THEME_FONT_SIZE = 22
THEME_BG_COLOR = (30, 30, 30, 220)  # 黒背景（半透明）
THEME_TEXT_COLOR = (255, 255, 255)  # 白文字
THEME_PADDING = 10
THEME_RIGHT_MARGIN = 15
THEME_TOP_MARGIN = 12

# 冒頭演出設定
INTRO_DURATION = 25.0  # 冒頭の長さ（秒）
INTRO_THEME_FONT_SIZE = 54  # 冒頭テーマのフォントサイズ（大きめ）
INTRO_THEME_BG_COLOR = (50, 100, 180, 230)  # 青背景
INTRO_THEME_TEXT_COLOR = (255, 255, 255)  # 白文字
INTRO_THEME_PADDING = 20
INTRO_NARRATION_BG_COLOR = (40, 40, 40, 220)  # ナレーション背景（暗め）
INTRO_NARRATION_TEXT_COLOR = (255, 255, 255)  # ナレーション文字色

# アイコン設定（左下）
ICON_SIZE = 150  # アイコンサイズ（さらに拡大）
ICON_LEFT_MARGIN = 20
ICON_BOTTOM_MARGIN = 20

# キャラクター配置（右側）
CHARACTER_RIGHT_MARGIN = 30
CHARACTER_BOTTOM_MARGIN = 30
CHARACTER_HEIGHT_RATIO = 0.38  # 画面高さに対する比率（小さめ）

# 背景動画設定
BACKGROUND_VIDEO_OVERLAY_ALPHA = 0.7  # 白オーバーレイの透明度（0.0=透明, 1.0=真っ白）

# 話者別の枠色設定（RGB + 枠線の太さ）
# res_X は循環して色を割り当てる
_RES_COLORS = [
    {"border": (130, 80, 160), "bg": (250, 245, 255, 240)},   # 紫
    {"border": (80, 130, 80), "bg": (245, 255, 245, 240)},    # 緑
    {"border": (80, 80, 80), "bg": (250, 250, 250, 240)},     # グレー
    {"border": (80, 130, 180), "bg": (245, 250, 255, 240)},   # 青
    {"border": (180, 130, 80), "bg": (255, 250, 245, 240)},   # オレンジ
]

SPEAKER_STYLES = {
    "icchi": {
        "name": "イッチ",
        "border_color": (220, 50, 50),      # 赤枠
        "bg_color": (255, 250, 250, 240),   # 薄い赤背景
        "name_bg_color": (220, 50, 50),     # 名前ラベル背景
        "name_text_color": (255, 255, 255), # 名前ラベル文字色
    },
    "narrator": {
        "name": "",
        "border_color": (100, 100, 120),
        "bg_color": (240, 240, 245, 235),  # 明るい背景
        "name_bg_color": (100, 100, 120),
        "name_text_color": (255, 255, 255),
        "text_color": (30, 30, 40),  # 暗い文字
    },
    "title_card": {
        "name": "",
        "border_color": (100, 100, 120),
        "bg_color": (240, 240, 245, 235),  # 明るい背景
        "name_bg_color": (100, 100, 120),
        "name_text_color": (255, 255, 255),
        "text_color": (30, 30, 40),  # 暗い文字
    },
}

def get_speaker_style(role: str) -> dict:
    """話者のスタイルを取得（未定義の場合は循環して割り当て）"""
    if role in SPEAKER_STYLES:
        return SPEAKER_STYLES[role]

    # res_A, res_B, ... の場合は循環
    if role.startswith("res_"):
        letter = role.replace("res_", "")
        if letter.isalpha() and len(letter) == 1:
            idx = ord(letter.upper()) - ord('A')
        else:
            idx = 0
        color = _RES_COLORS[idx % len(_RES_COLORS)]
        return {
            "name": "名無しさん",
            "border_color": color["border"],
            "bg_color": color["bg"],
            "name_bg_color": color["border"],
            "name_text_color": (255, 255, 255),
        }

    # デフォルト（グレー）
    return {
        "name": "",
        "border_color": (80, 80, 80),
        "bg_color": (250, 250, 250, 240),
        "name_bg_color": (80, 80, 80),
        "name_text_color": (255, 255, 255),
    }

# 音声設定（OpenAI TTS）
VOICE_MODEL = "tts-1"
VOICE_MAPPING = {
    "narrator": "shimmer",  # ナレーター
    "icchi": "alloy",       # スレ主
    "res_A": "echo",        # スレ民A
    "res_B": "fable",       # スレ民B
    "res_C": "onyx",        # スレ民C
}

def ensure_directories():
    """必要なディレクトリが存在しない場合は作成"""
    for directory in [SCRIPTS_DIR, VOICES_DIR, IMAGES_DIR, IMAGE_CACHE_DIR,
                      CHARACTER_IMAGES_DIR, BACKGROUND_IMAGES_DIR, ICON_DIR,
                      NANOBANANA_DIR, INTRO_IMAGES_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
