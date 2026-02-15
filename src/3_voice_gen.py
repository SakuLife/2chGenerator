"""
音声生成スクリプト
VOICEVOXを使用して台本から音声を生成

音声タイミング同期:
- 各音声の実際の長さを計測
- subtitles.json に start_time, duration を記録
- 動画編集時にこのタイミング情報を使用して字幕と音声を完全同期
"""

import json
import sys
from pathlib import Path

from pydub import AudioSegment

# Skills を使えるようにパスを追加（リポジトリ内 → 共有フォルダの順で探索）
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(1, str(Path(__file__).parent.parent.parent))

from Skills.voicevox import VoicevoxClient, VoicevoxLauncher

from config import (
    GEMINI_API_KEY,
    SCRIPTS_DIR,
    VOICES_DIR,
    ensure_directories,
)
from logger import logger

# Gemini API（読み方チェック用）
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# キャラクター別スピーカーID（VOICEVOX）
VOICEVOX_SPEAKER_MAPPING = {
    "narrator": 3,    # ずんだもん（ノーマル）- ナレーター
    "icchi": 2,       # 四国めたん（ノーマル）- スレ主
    "res_A": 3,       # ずんだもん（紫字幕）
    "res_B": 8,       # 春日部つむぎ（人気キャラ）
    "res_C": 13,      # 青山龍星
    "res_D": 12,      # 白上虎太郎（ふつう）
    "res_E": 46,      # 小夜/SAYO（シンプル）
    "res_F": 3,       # ずんだもん（紫字幕・循環）
    "res_G": 3,       # ずんだもん
    "res_H": 14,      # 冥鳴ひまり（イッチと別キャラ）
    "res_I": 3,       # ずんだもん（青字幕）
    "res_J": 8,       # 春日部つむぎ（人気キャラ）
    "res_K": 3,       # ずんだもん（紫字幕・循環）
    "res_L": 12,      # 白上虎太郎（緑の循環用）
    "res_M": 46,      # 小夜/SAYO（シンプル）
}

# デフォルトスピーカー
DEFAULT_SPEAKER_ID = 3  # ずんだもん

# スピーカー別の話速設定（デフォルト1.0）
VOICEVOX_SPEED_MAPPING = {
    "res_A": 1.15,  # 紫字幕：1.15倍速
    "res_B": 1.2,   # 緑字幕：1.2倍速
    "res_E": 1.15,  # オレンジ字幕：1.15倍速（上げた）
    "res_F": 1.15,  # 紫字幕（循環）：1.15倍速
    "res_G": 1.1,   # グレー字幕：1.1倍速（追加）
    "res_I": 1.1,   # 青字幕：1.1倍速（追加）
    "res_J": 1.2,   # 緑字幕（循環）：1.2倍速
    "res_K": 1.15,  # 紫字幕（循環）：1.15倍速
    "res_M": 1.1,   # オレンジ字幕（循環）：1.1倍速
}
DEFAULT_SPEED = 1.0

# スピーカー別のピッチ設定（デフォルト0.0、-0.15で低く）
VOICEVOX_PITCH_MAPPING = {
    "res_B": -0.10,  # 緑字幕：低め
    "res_I": -0.10,  # 青字幕（地道にコツコツ）：低め
    "res_J": -0.10,  # オレンジ字幕：低め
    "res_G": -0.10,  # 緑字幕（循環）：低め
}
DEFAULT_PITCH = 0.0

# スピーカー別の音量ブースト（dB）- 声が低い/小さいキャラを補正
VOICEVOX_VOLUME_BOOST = {
    "res_C": 4,   # 青山龍星：低音で聞こえにくい
    "res_E": 3,   # 小夜/SAYO：声が小さめ
    "res_F": 3,   # ずんだもん：小さめ
    "res_H": 4,   # 冥鳴ひまり：声が小さい
}
DEFAULT_VOLUME_BOOST = 0

# 読み方変換辞書（表記 → 読み）
READING_DICT = {
    # 数字・金額
    "1000万": "いっせんまん",
    "100万": "ひゃくまん",
    "10万": "じゅうまん",
    "1万": "いちまん",
    "0円": "ぜろえん",
    "1/3": "さんぶんのいち",
    "1/2": "にぶんのいち",
    "10%": "じゅっぱーせんと",
    # 単位
    "500g": "ごひゃくグラム",
    "100g": "ひゃくグラム",
    "1kg": "いちキロ",
    "10kg": "じゅっキロ",
    # 「何」の読み（なん）
    "何なのか": "なんなのか",
    "何で": "なんで",
    "何が": "なにが",
    "何を": "なにを",
    "何も": "なにも",
    "何か": "なにか",
    "何人": "なんにん",
    "何歳": "なんさい",
    "何年": "なんねん",
    "何万": "なんまん",
    "何円": "なんえん",
    # 英語・ブランド名
    "UberEats": "ウーバーイーツ",
    "Uber Eats": "ウーバーイーツ",
    "Uber": "ウーバー",
    "PayPay": "ペイペイ",
    "Spotify": "スポティファイ",
    "TikTok": "ティックトック",
    "Instagram": "インスタグラム",
    "iPhone": "アイフォン",
    "Apple": "アップル",
    "ChatGPT": "チャットジーピーティー",
    "Wi-Fi": "ワイファイ",
    "WiFi": "ワイファイ",
    "Bitcoin": "ビットコイン",
    "Suica": "スイカ",
    "PASMO": "パスモ",
    "PayPal": "ペイパル",
    "Tesla": "テスラ",
    "Costco": "コストコ",
    "IKEA": "イケア",
    "Starbucks": "スターバックス",
    "McDonald's": "マクドナルド",
    "McDonalds": "マクドナルド",
    "AirPods": "エアーポッズ",
    "Switch": "スイッチ",
    "PS5": "ピーエスファイブ",
    "Zoom": "ズーム",
    "Slack": "スラック",
    "UNIQLO": "ユニクロ",
    "GU": "ジーユー",
    "ZARA": "ザラ",
    "楽天": "らくてん",
    # 英語・略語
    "SIM": "しむ",
    "S&P500": "えすあんどぴーごひゃく",
    "S&P": "えすあんどぴー",
    "FX": "えふえっくす",
    "PC": "ぱそこん",
    "API": "えーぴーあい",
    "URL": "ゆーあーるえる",
    "SNS": "えすえぬえす",
    "YouTube": "ゆーちゅーぶ",
    "Twitter": "ついったー",
    "LINE": "らいん",
    "NISA": "にーさ",
    "iDeCo": "いでこ",
    "Netflix": "ねっとふりっくす",
    "Amazon": "あまぞん",
    "Google": "ぐーぐる",
    "REIT": "リート",
    "J-REIT": "ジェイリート",
    "ETF": "イーティーエフ",
    "FIRE": "ファイア",
    "TOPIX": "トピックス",
    "DIY": "ディーアイワイ",
    "SEO": "エスイーオー",
    "Web": "ウェブ",
    "Progate": "プロゲート",
    "Codecademy": "コードアカデミー",
    "mineo": "マイネオ",
    "GDP": "ジーディーピー",
    # 「金」の読み分け（かね/きん）
    "親の金": "おやのかね",
    "金持ち": "かねもち",
    "お金": "おかね",
    "金がない": "かねがない",
    "金が": "かねが",
    "金を": "かねを",
    "金は": "かねは",
    "金も": "かねも",
    "金の": "かねの",
    "金で": "かねで",
    "頭金": "あたまきん",
    # ネットスラング・俗語
    "ｗｗｗ": "",
    "ｗｗ": "",
    "ｗ": "",
    "www": "",
    "ww": "",
    "w": "",
    "草": "くさ",
    "orz": "おーあーるぜっと",
    "陰キャ": "いんきゃ",
    "陽キャ": "ようきゃ",
    "リア充": "りあじゅう",
    "ガチ": "がち",
    "マジ": "まじ",
    "ワイ": "わい",
    "彼女": "かのじょ",
    # その他
    "一択": "いったく",
    "30代": "さんじゅうだい",
    "20代": "にじゅうだい",
    "40代": "よんじゅうだい",
    "50代": "ごじゅうだい",
    "1K": "わんけー",
    "2LDK": "にーえるでぃーけー",
    "飲み代": "のみだい",
    "食費代": "しょくひだい",
    "交際費": "こうさいひ",
    # 「辛」の読み分け（つらい/からい）
    "辛かった": "つらかった",
    "辛い思い": "つらいおもい",
    "辛いこと": "つらいこと",
    "辛い時": "つらいとき",
    "辛い日々": "つらいひび",
    "辛くて": "つらくて",
    "辛さ": "つらさ",
    "辛抱": "しんぼう",
    # 「行」の読み分け
    "行った": "いった",
    "行って": "いって",
    "行く": "いく",
    "行ける": "いける",
    "行こう": "いこう",
    # 「上」の読み分け
    "上がった": "あがった",
    "上がる": "あがる",
    "上げた": "あげた",
    "上げる": "あげる",
    "上手": "じょうず",
    "以上": "いじょう",
    "年上": "としうえ",
    # 「下」の読み分け
    "下がった": "さがった",
    "下がる": "さがる",
    "下げた": "さげた",
    "下げる": "さげる",
    "以下": "いか",
    "年下": "としした",
    # 「生」の読み分け
    "生活": "せいかつ",
    "生まれ": "うまれ",
    "生きる": "いきる",
    "生涯": "しょうがい",
    "人生": "じんせい",
    # 「重」の読み分け
    "重い": "おもい",
    "重く": "おもく",
    "重要": "じゅうよう",
    "体重": "たいじゅう",
    # 「分」の読み分け
    "自分": "じぶん",
    "半分": "はんぶん",
    "十分": "じゅうぶん",
    "気分": "きぶん",
    "分かる": "わかる",
    "分ける": "わける",
    # 「今」の読み分け
    "今日": "きょう",
    "今年": "ことし",
    "今月": "こんげつ",
    "今週": "こんしゅう",
    "今回": "こんかい",
    "今後": "こんご",
    "今更": "いまさら",
    # 「間」の読み分け
    "時間": "じかん",
    "期間": "きかん",
    "人間": "にんげん",
    "仲間": "なかま",
    "間に合う": "まにあう",
    # 「代」の読み分け
    "世代": "せだい",
    "時代": "じだい",
    "代わり": "かわり",
    "交代": "こうたい",
    # 「入」の読み分け
    "入れる": "いれる",
    "入った": "はいった",
    "入る": "はいる",
    "収入": "しゅうにゅう",
    "入金": "にゅうきん",
    # 「出」の読み分け
    "出る": "でる",
    "出した": "だした",
    "出す": "だす",
    "支出": "ししゅつ",
    "出金": "しゅっきん",
    # 食べ物
    "鶏むね肉": "とりむねにく",
    "鶏もも肉": "とりももにく",
    "鶏肉": "とりにく",
    "牛肉": "ぎゅうにく",
    "豚肉": "ぶたにく",
    # よく誤読される単語
    "借金": "しゃっきん",
    "貯金": "ちょきん",
    "貸金": "かしきん",
    "元金": "がんきん",
    "現金": "げんきん",
    "預金": "よきん",
    "定期預金": "ていきよきん",
    "出資": "しゅっし",
    "融資": "ゆうし",
    "返済": "へんさい",
    "完済": "かんさい",
    "滞納": "たいのう",
    "延滞": "えんたい",
    "破産": "はさん",
    "自己破産": "じこはさん",
    "債務": "さいむ",
    "債権": "さいけん",
    "負債": "ふさい",
    "担保": "たんぽ",
    "抵当": "ていとう",
    "利息": "りそく",
    "利子": "りし",
    "金利": "きんり",
    "年利": "ねんり",
    "複利": "ふくり",
    "単利": "たんり",
}

# 助詞「は」→「わ」に変換するパターン（名詞＋は）
PARTICLE_HA_PATTERNS = [
    # 金融関連
    ("給料は", "きゅうりょうわ"),
    ("収入は", "しゅうにゅうわ"),
    ("年収は", "ねんしゅうわ"),
    ("貯金は", "ちょきんわ"),
    ("投資は", "とうしわ"),
    ("資産は", "しさんわ"),
    ("借金は", "しゃっきんわ"),
    ("ローンは", "ローンわ"),
    ("税金は", "ぜいきんわ"),
    ("家賃は", "やちんわ"),
    ("金額は", "きんがくわ"),
    ("残高は", "ざんだかわ"),
    ("利益は", "りえきわ"),
    ("損失は", "そんしつわ"),
    # 数量・割合関連
    ("1割は", "1割わ"),
    ("2割は", "2割わ"),
    ("3割は", "3割わ"),
    ("4割は", "4割わ"),
    ("5割は", "5割わ"),
    ("6割は", "6割わ"),
    ("7割は", "7割わ"),
    ("8割は", "8割わ"),
    ("9割は", "9割わ"),
    ("半分は", "はんぶんわ"),
    ("大半は", "たいはんわ"),
    ("残りは", "のこりわ"),
    ("平均は", "へいきんわ"),
    # 人物関連
    ("俺は", "おれわ"),
    ("私は", "わたしわ"),
    ("僕は", "ぼくわ"),
    ("ワイは", "わいわ"),
    ("嫁は", "よめわ"),
    ("妻は", "つまわ"),
    ("夫は", "おっとわ"),
    ("親は", "おやわ"),
    ("会社は", "かいしゃわ"),
    ("仕事は", "しごとわ"),
    # 一般
    ("それは", "それわ"),
    ("これは", "これわ"),
    ("あれは", "あれわ"),
    ("今は", "いまわ"),
    ("後は", "あとわ"),
    ("他は", "ほかわ"),
    ("結果は", "けっかわ"),
    ("理由は", "りゆうわ"),
    ("問題は", "もんだいわ"),
    ("正解は", "せいかいわ"),
]


def convert_particle_ha(text: str) -> str:
    """助詞「は」を「わ」に変換（VOICEVOXの読み改善用）"""
    for pattern, replacement in PARTICLE_HA_PATTERNS:
        text = text.replace(pattern, replacement)
    return text


def normalize_fullwidth_numbers(text: str) -> str:
    """全角数字を半角に変換（読み方変換の前処理）"""
    fullwidth = "０１２３４５６７８９"
    halfwidth = "0123456789"
    trans_table = str.maketrans(fullwidth, halfwidth)
    return text.translate(trans_table)


def convert_large_numbers(text: str) -> str:
    """
    大きな数字（万、億、兆単位）を読み仮名に変換

    例: 5000万 → ごせんまん, 3億 → さんおく
    """
    import re

    # 数字の読み方マッピング
    digit_readings = {
        "0": "", "1": "いっ", "2": "に", "3": "さん", "4": "よん",
        "5": "ご", "6": "ろく", "7": "なな", "8": "はっ", "9": "きゅう",
    }
    # 千の位の特殊読み
    digit_sen = {
        "0": "", "1": "せん", "2": "にせん", "3": "さんぜん", "4": "よんせん",
        "5": "ごせん", "6": "ろくせん", "7": "ななせん", "8": "はっせん", "9": "きゅうせん",
    }
    # 百の位の特殊読み
    digit_hyaku = {
        "0": "", "1": "ひゃく", "2": "にひゃく", "3": "さんびゃく", "4": "よんひゃく",
        "5": "ごひゃく", "6": "ろっぴゃく", "7": "ななひゃく", "8": "はっぴゃく", "9": "きゅうひゃく",
    }
    # 十の位
    digit_juu = {
        "0": "", "1": "じゅう", "2": "にじゅう", "3": "さんじゅう", "4": "よんじゅう",
        "5": "ごじゅう", "6": "ろくじゅう", "7": "ななじゅう", "8": "はちじゅう", "9": "きゅうじゅう",
    }
    # 一の位（単位の前）
    digit_ichi = {
        "0": "", "1": "いち", "2": "に", "3": "さん", "4": "よん",
        "5": "ご", "6": "ろく", "7": "なな", "8": "はち", "9": "きゅう",
    }

    def number_to_reading(num_str: str, unit: str) -> str:
        """4桁以下の数字を読みに変換"""
        num_str = num_str.lstrip("0")
        if not num_str:
            return ""

        num_str = num_str.zfill(4)  # 4桁に揃える
        sen, hyaku, juu, ichi = num_str

        reading = ""
        reading += digit_sen.get(sen, "")
        reading += digit_hyaku.get(hyaku, "")
        reading += digit_juu.get(juu, "")
        # 一の位は単位がある場合のみ読む
        if ichi != "0":
            reading += digit_ichi.get(ichi, "")

        return reading + unit if reading else ""

    # 億、万の順で処理（大きい単位から）
    # パターン: 数字+億, 数字+万
    def replace_unit(match):
        num = match.group(1)
        unit = match.group(2)
        unit_reading = {"億": "おく", "万": "まん", "兆": "ちょう"}.get(unit, unit)
        reading = number_to_reading(num, unit_reading)
        return reading if reading else match.group(0)

    # 億・万・兆を含む数字を変換
    text = re.sub(r"(\d{1,4})(億|万|兆)", replace_unit, text)

    return text


def get_audio_duration(audio_path: Path) -> float:
    """
    pydubで音声ファイルの実際の長さを計測

    Args:
        audio_path: 音声ファイルのパス

    Returns:
        音声の長さ（秒）
    """
    audio = AudioSegment.from_file(str(audio_path))
    return len(audio) / 1000.0  # ミリ秒→秒


def normalize_audio_volume(audio_path: Path, target_dBFS: float = -20.0) -> None:
    """
    音声ファイルの音量を正規化（全キャラ均一化）

    Args:
        audio_path: 音声ファイルのパス
        target_dBFS: 目標音量レベル（dBFS）
    """
    audio = AudioSegment.from_file(str(audio_path))
    if audio.dBFS == float('-inf'):
        return  # 無音ファイルはスキップ
    change_in_dBFS = target_dBFS - audio.dBFS
    normalized = audio.apply_gain(change_in_dBFS)
    normalized.export(str(audio_path), format="wav")


def adjust_audio_speed(audio_path: Path, speed: float) -> None:
    """
    音声ファイルの再生速度を変更（ピッチ維持）

    Args:
        audio_path: 音声ファイルのパス
        speed: 速度倍率（1.2 = 1.2倍速）
    """
    if speed == 1.0:
        return

    audio = AudioSegment.from_file(str(audio_path))

    # フレームレートを変更して速度調整（ピッチも変わる簡易版）
    # より高品質にするならrubberband等を使う
    new_frame_rate = int(audio.frame_rate * speed)
    audio_fast = audio._spawn(audio.raw_data, overrides={
        "frame_rate": new_frame_rate
    }).set_frame_rate(audio.frame_rate)

    audio_fast.export(str(audio_path), format="wav")


def generate_voices_from_script(script_path: Path, use_ai_fix: bool = True) -> dict:
    """
    台本から音声を一括生成し、タイミング情報をsubtitles.jsonに出力

    Args:
        script_path: 台本JSONファイルのパス
        use_ai_fix: AIで読み方を自動修正するか

    Returns:
        {index: voice_path} の辞書
    """
    ensure_directories()

    # VOICEVOXの起動確認
    launcher = VoicevoxLauncher()
    if not launcher.ensure_running_sync(max_wait_seconds=180):
        raise RuntimeError("VOICEVOXを起動できませんでした。手動で起動してください。")

    client = VoicevoxClient()

    # 台本を読み込み
    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    logger.info(f"台本を読み込みました: {script_path.name}")
    logger.info(f"シーン数: {len(script)}個")

    # AI修正用: 事前に全テキストを変換してAI修正
    ai_fixed_texts = {}
    if use_ai_fix and GEMINI_AVAILABLE and GEMINI_API_KEY:
        logger.info("🤖 AI読み方チェック中...")
        texts_to_fix = []
        indices_to_fix = []

        for i, scene in enumerate(script):
            role = scene.get("role", "narrator")
            text = scene.get("text", "")
            voice_path = VOICES_DIR / f"{i:03d}_{role}.wav"

            # 新規生成が必要なものだけ
            if text and role != "title_card" and not voice_path.exists():
                # 基本変換を適用
                voice_text = text
                voice_text = normalize_fullwidth_numbers(voice_text)
                voice_text = convert_large_numbers(voice_text)
                voice_text = apply_reading_dict(voice_text)
                voice_text = convert_particle_ha(voice_text)
                voice_text = voice_text.strip()

                if voice_text:
                    texts_to_fix.append(voice_text)
                    indices_to_fix.append(i)

        if texts_to_fix:
            logger.info(f"  {len(texts_to_fix)}件のテキストをAIチェック")
            fixed_texts = batch_fix_readings_with_ai(texts_to_fix)
            for idx, fixed in zip(indices_to_fix, fixed_texts):
                ai_fixed_texts[idx] = fixed
                # 変更があればログ出力
                original = texts_to_fix[indices_to_fix.index(idx)]
                if original != fixed:
                    logger.info(f"  [{idx:03d}] AI修正: {original[:20]}... → {fixed[:20]}...")
            logger.info("✅ AIチェック完了")

    voice_map = {}
    subtitles = []  # 字幕タイミング情報
    current_time = 0.0  # 累積時間

    # セリフ間の自然な間（秒）- 話者が変わる際の間を再現
    INTER_SCENE_GAP = 0.4

    for i, scene in enumerate(script):
        role = scene.get("role", "narrator")
        text = scene.get("text", "")
        name = scene.get("name", "")

        # 字幕データの基本構造
        subtitle_entry = {
            "index": i,
            "role": role,
            "name": name,
            "text": text,
            "start_time": current_time,
            "duration": 0.0,  # 後で更新
        }

        # title_cardは音声なし
        if role == "title_card":
            logger.info(f"[{i:03d}] スキップ（タイトルカード）")
            # タイトルカードは1.5秒＋間（字幕表示を途切れさせない）
            subtitle_entry["duration"] = 1.5 + INTER_SCENE_GAP
            current_time += 1.5 + INTER_SCENE_GAP
            subtitles.append(subtitle_entry)
            continue

        if not text:
            logger.info(f"[{i:03d}] スキップ（テキストなし）")
            continue

        voice_path = VOICES_DIR / f"{i:03d}_{role}.wav"

        # 既に存在する場合は長さを計測してスキップ
        if voice_path.exists():
            duration = get_audio_duration(voice_path)
            logger.info(f"[{i:03d}] スキップ（既存）: {voice_path.name} ({duration:.2f}秒)")
            voice_map[i] = str(voice_path)
            subtitle_entry["duration"] = duration + INTER_SCENE_GAP
            current_time += duration + INTER_SCENE_GAP
            subtitles.append(subtitle_entry)
            continue

        # 音声用テキストを作成（AI修正済みがあればそれを使用）
        if i in ai_fixed_texts:
            voice_text = ai_fixed_texts[i]
        else:
            voice_text = text
            # 1. 全角数字→半角数字
            voice_text = normalize_fullwidth_numbers(voice_text)
            # 2. 大きな数字を読み仮名に変換（5000万→ごせんまん）
            voice_text = convert_large_numbers(voice_text)
            # 3. 辞書に基づいて変換
            voice_text = apply_reading_dict(voice_text)
            # 4. 助詞「は」→「わ」変換
            voice_text = convert_particle_ha(voice_text)
            voice_text = voice_text.strip()

        if not voice_text:
            logger.info(f"[{i:03d}] スキップ（音声テキストなし）")
            subtitle_entry["duration"] = 1.5 + INTER_SCENE_GAP
            current_time += 1.5 + INTER_SCENE_GAP
            subtitles.append(subtitle_entry)
            continue

        # 音声生成
        logger.info(f"[{i:03d}] 生成中: {voice_text[:30]}...")

        try:
            # キャラクターに応じたスピーカーを選択
            speaker_id = VOICEVOX_SPEAKER_MAPPING.get(role, DEFAULT_SPEAKER_ID)

            generated_path = client.synthesize_sync(
                text=voice_text,  # 「ｗ」除去済みテキスト
                output_path=voice_path,
                speaker_id=speaker_id,
            )

            # 話速調整（必要な場合）
            speed = VOICEVOX_SPEED_MAPPING.get(role, DEFAULT_SPEED)
            if speed != 1.0:
                adjust_audio_speed(generated_path, speed)
                logger.info(f"  話速調整: {speed}倍")

            # 音量正規化（キャラクター間の音量差を均一化）+ 個別ブースト
            volume_boost = VOICEVOX_VOLUME_BOOST.get(role, DEFAULT_VOLUME_BOOST)
            normalize_audio_volume(generated_path, target_dBFS=-20.0 + volume_boost)

            voice_map[i] = str(generated_path)

            # 実際の長さを計測
            duration = get_audio_duration(generated_path)
            logger.info(f"  保存完了: {generated_path.name} ({duration:.2f}秒)")

            subtitle_entry["duration"] = duration + INTER_SCENE_GAP
            current_time += duration + INTER_SCENE_GAP
            subtitles.append(subtitle_entry)

        except Exception as e:
            logger.error(f"  生成失敗: {e}")
            continue

    logger.info(f"\n音声生成完了: {len(voice_map)}個")
    logger.info(f"総再生時間: {current_time:.2f}秒")

    # 音声マップをJSONで保存（動画編集時に使用）
    voice_map_path = VOICES_DIR / "voice_map.json"
    with open(voice_map_path, "w", encoding="utf-8") as f:
        json.dump(voice_map, f, ensure_ascii=False, indent=2)

    # 字幕タイミング情報をJSONで保存
    subtitles_path = VOICES_DIR / "subtitles.json"
    with open(subtitles_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total_duration": current_time,
                "subtitles": subtitles,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info(f"字幕タイミング情報を保存: {subtitles_path.name}")

    return voice_map


def _reading_sort_key(item):
    """READING_DICTのソートキー（長い順、同じ長さなら漢字のみ優先）"""
    orig = item[0]
    length = -len(orig)
    has_kana = any('\u3040' <= c <= '\u30ff' for c in orig)
    return (length, has_kana)


def apply_reading_dict(text: str) -> str:
    """
    テキストにREADING_DICTを適用

    Args:
        text: 変換前のテキスト

    Returns:
        変換後のテキスト
    """
    for orig, reading in sorted(READING_DICT.items(), key=_reading_sort_key):
        text = text.replace(orig, reading)
    return text


def preview_text_conversion(text: str) -> str:
    """
    テキストの読み方変換結果をプレビュー（単一テキスト用）

    Args:
        text: 変換前のテキスト

    Returns:
        変換後のテキスト
    """
    voice_text = text
    voice_text = normalize_fullwidth_numbers(voice_text)
    voice_text = convert_large_numbers(voice_text)
    voice_text = apply_reading_dict(voice_text)
    voice_text = convert_particle_ha(voice_text)
    return voice_text.strip()


def preview_script_readings(script_path: Path) -> list[dict]:
    """
    台本の全テキストの読み方変換結果をプレビュー

    Args:
        script_path: 台本JSONファイルのパス

    Returns:
        変換結果のリスト [{index, original, converted, has_change}]
    """
    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    results = []
    for i, scene in enumerate(script):
        text = scene.get("text", "")
        if not text:
            continue

        converted = preview_text_conversion(text)
        has_change = text != converted

        results.append({
            "index": i,
            "role": scene.get("role", ""),
            "original": text,
            "converted": converted,
            "has_change": has_change,
        })

    return results


def fix_reading_with_ai(text: str) -> str:
    """
    AIを使って読み方を自動修正

    Args:
        text: 変換後のテキスト

    Returns:
        修正後のテキスト（ひらがな化された箇所を含む）
    """
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return text

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""以下のテキストを音声合成ソフト（VOICEVOX）で正しく読めるように修正してください。

修正ルール：
1. 英語の単語・ブランド名は必ずカタカナに変換（例: UberEats→ウーバーイーツ, Netflix→ネットフリックス, iPhone→アイフォン）
2. 英語の略語はカタカナで読みを書く（例: NISA→ニーサ, ETF→イーティーエフ）
3. 誤読されそうな漢字はひらがなに変換（例: 借金→しゃっきん）
4. 大きな数字は読み仮名に変換（例: 5000万→ごせんまん）
5. 正しく読める部分はそのまま残す（過剰にひらがな化しない）
6. 意味・語順を変えない。句読点や記号はそのまま

入力テキスト：
{text}

修正後のテキストのみを出力してください。説明は不要です。"""

    try:
        response = model.generate_content(prompt)
        fixed = response.text.strip()
        # 余計な引用符やマークダウンを除去
        fixed = fixed.strip('"\'`')
        if fixed.startswith("```"):
            fixed = fixed.split("\n", 1)[-1].rsplit("```", 1)[0]
        return fixed
    except Exception as e:
        logger.warning(f"AI修正失敗、元テキストを使用: {e}")
        return text


def batch_fix_readings_with_ai(texts: list[str]) -> list[str]:
    """
    複数テキストをまとめてAI修正（API呼び出し削減）

    Args:
        texts: 変換後のテキストリスト

    Returns:
        修正後のテキストリスト
    """
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return texts

    if not texts:
        return texts

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    # 番号付きで結合
    numbered = "\n".join(f"[{i}] {t}" for i, t in enumerate(texts))

    prompt = f"""以下のテキストを音声合成ソフト（VOICEVOX）で正しく読めるように修正してください。

修正ルール：
1. 英語の単語・ブランド名は必ずカタカナに変換（例: UberEats→ウーバーイーツ, Netflix→ネットフリックス, Amazon→アマゾン, iPhone→アイフォン）
2. 英語の略語はカタカナで読みを書く（例: NISA→ニーサ, ETF→イーティーエフ, AI→エーアイ, SNS→エスエヌエス）
3. 誤読されそうな漢字はひらがなに変換（例: 借金→しゃっきん, 何人→なんにん）
4. 大きな数字は読み仮名に変換（例: 5000万→ごせんまん, 3億→さんおく）
5. 正しく読める部分はそのまま残す（過剰にひらがな化しない）
6. 意味・語順を変えない。句読点や記号はそのまま
7. 各行の番号[N]は維持

入力：
{numbered}

出力形式：番号付きで修正後テキストのみを出力。説明不要。"""

    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()

        # パース
        fixed_texts = list(texts)  # コピー
        for line in result_text.split("\n"):
            line = line.strip()
            if line.startswith("[") and "]" in line:
                try:
                    idx_str = line[1:line.index("]")]
                    idx = int(idx_str)
                    content = line[line.index("]") + 1:].strip()
                    if 0 <= idx < len(fixed_texts):
                        fixed_texts[idx] = content
                except (ValueError, IndexError):
                    continue

        return fixed_texts

    except Exception as e:
        logger.warning(f"AI一括修正失敗: {e}")
        return texts


def run_preview_mode(script_path: Path) -> bool:
    """
    プレビューモード: 読み方変換を確認して続行するか選択

    Args:
        script_path: 台本JSONファイルのパス

    Returns:
        True=続行, False=中止
    """
    print("\n" + "=" * 60)
    print("📖 読み方プレビューモード")
    print("=" * 60)

    results = preview_script_readings(script_path)
    changes = [r for r in results if r["has_change"]]

    if not changes:
        print("\n✅ 変換が必要なテキストはありません")
        return True

    print(f"\n🔄 {len(changes)}件のテキストが変換されます:\n")

    for r in changes:
        print(f"[{r['index']:03d}] {r['role']}")
        print(f"  元: {r['original'][:60]}{'...' if len(r['original']) > 60 else ''}")
        print(f"  →: {r['converted'][:60]}{'...' if len(r['converted']) > 60 else ''}")
        print()

    print("=" * 60)
    while True:
        choice = input("\n続行しますか？ [y=続行 / n=中止 / d=詳細表示]: ").strip().lower()
        if choice == "y":
            return True
        elif choice == "n":
            print("中止しました")
            return False
        elif choice == "d":
            print("\n" + "=" * 60)
            print("📋 全変換詳細")
            print("=" * 60 + "\n")
            for r in changes:
                print(f"[{r['index']:03d}] {r['role']}")
                print(f"  元: {r['original']}")
                print(f"  →: {r['converted']}")
                print("-" * 40)
        else:
            print("y, n, d のいずれかを入力してください")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="音声生成スクリプト")
    parser.add_argument("--no-ai-fix", action="store_true", help="AI読み方修正を無効化（デフォルトは有効）")
    parser.add_argument("--preview", action="store_true", help="プレビューモード（変換結果を確認）")
    parser.add_argument("--preview-only", action="store_true", help="プレビューのみ（音声生成しない）")
    parser.add_argument("--test", type=str, help="テスト用: 単一テキストの変換を確認")
    parser.add_argument("--test-ai", type=str, help="テスト用: AI修正の確認")
    args = parser.parse_args()

    script_path = SCRIPTS_DIR / "script.json"

    # テストモード: 単一テキストの変換確認
    if args.test:
        print(f"元: {args.test}")
        print(f"→: {preview_text_conversion(args.test)}")
        exit(0)

    # テストモード: AI修正の確認
    if args.test_ai:
        print(f"元: {args.test_ai}")
        converted = preview_text_conversion(args.test_ai)
        print(f"辞書変換: {converted}")
        fixed = fix_reading_with_ai(converted)
        print(f"AI修正: {fixed}")
        exit(0)

    # プレビューのみモード
    if args.preview_only:
        run_preview_mode(script_path)
        exit(0)

    # プレビューモード（確認後に生成）
    if args.preview:
        if not run_preview_mode(script_path):
            exit(0)

    # 音声生成（デフォルトでAI修正有効、--no-ai-fix で無効化）
    generate_voices_from_script(script_path, use_ai_fix=not args.no_ai_fix)
