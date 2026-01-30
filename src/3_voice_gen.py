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

# Skills/voicevox を使えるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Skills.voicevox import VoicevoxClient, VoicevoxLauncher

from config import (
    SCRIPTS_DIR,
    VOICES_DIR,
    ensure_directories,
)
from logger import logger


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
}


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


def generate_voices_from_script(script_path: Path) -> dict:
    """
    台本から音声を一括生成し、タイミング情報をsubtitles.jsonに出力

    Args:
        script_path: 台本JSONファイルのパス

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

        # 音声用テキストを作成（読み方変換）
        voice_text = text
        # 辞書に基づいて変換（長い表記から順に処理）
        for orig, reading in sorted(READING_DICT.items(), key=lambda x: -len(x[0])):
            voice_text = voice_text.replace(orig, reading)
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


if __name__ == "__main__":
    script_path = SCRIPTS_DIR / "script.json"

    if not script_path.exists():
        print(f"エラー: 台本ファイルが見つかりません: {script_path}")
        print("先に 1_script_gen.py を実行してください。")
        exit(1)

    generate_voices_from_script(script_path)
