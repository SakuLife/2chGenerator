"""
読み方チェッカー
Gemini APIを使って台本の読み方を確認・修正
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import GEMINI_API_KEY, SCRIPTS_DIR

# Gemini APIクライアント
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


def check_readings_with_gemini(texts: list[str]) -> dict:
    """
    Geminiを使って読み方が特殊な単語を抽出

    Args:
        texts: チェックするテキストのリスト

    Returns:
        {単語: 読み方} の辞書
    """
    if not GEMINI_AVAILABLE:
        print("google-generativeai がインストールされていません")
        return {}

    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY が設定されていません")
        return {}

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    combined_text = "\n".join(texts)

    prompt = f"""以下のテキストから、音声読み上げソフト（VOICEVOX等）が正しく読めない可能性のある単語を抽出してください。

対象：
- ネットスラング（陰キャ、ワロタ、草など）
- 略語（FX、SNS、NISAなど）
- 数字を含む表現（1000万円、30代など）
- 当て字や特殊な読み方をする単語
- 英語・カタカナ語の混在

出力形式（JSON）：
{{"単語1": "ひらがな読み1", "単語2": "ひらがな読み2"}}

読み方は全てひらがなで。読み上げ不要な単語（ｗｗｗ等）は空文字""にしてください。

テキスト：
{combined_text}

JSONのみを出力してください。"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        # JSON部分を抽出
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        return json.loads(text)

    except Exception as e:
        print(f"Gemini API エラー: {e}")
        return {}


def check_script_readings(script_path: Path = None) -> dict:
    """
    台本ファイルの読み方をチェック

    Args:
        script_path: 台本ファイルパス（省略時はデフォルト）

    Returns:
        推奨される読み方辞書
    """
    if script_path is None:
        script_path = SCRIPTS_DIR / "script.json"

    if not script_path.exists():
        print(f"台本が見つかりません: {script_path}")
        return {}

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    texts = [scene.get("text", "") for scene in script if scene.get("text")]

    print(f"台本をチェック中... ({len(texts)}件のテキスト)")
    readings = check_readings_with_gemini(texts)

    if readings:
        print("\n=== 検出された特殊読み ===")
        for word, reading in readings.items():
            if reading:
                print(f"  {word} → {reading}")
            else:
                print(f"  {word} → (読み上げなし)")

    return readings


def update_reading_dict(new_readings: dict, auto_apply: bool = False):
    """
    3_voice_gen.py の READING_DICT を更新

    Args:
        new_readings: 追加する読み方辞書
        auto_apply: True の場合、確認なしで適用
    """
    voice_gen_path = Path(__file__).parent.parent / "3_voice_gen.py"

    if not voice_gen_path.exists():
        print("3_voice_gen.py が見つかりません")
        return

    with open(voice_gen_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 既存のREADING_DICTから登録済みの単語を抽出
    import re
    existing_words = set(re.findall(r'"([^"]+)":\s*"', content))

    # 新規のみ抽出
    new_only = {k: v for k, v in new_readings.items() if k not in existing_words}

    if not new_only:
        print("新規追加する読み方はありません")
        return

    print("\n=== 新規追加候補 ===")
    for word, reading in new_only.items():
        print(f"  {word} → {reading}")

    if not auto_apply:
        confirm = input("\nこれらを READING_DICT に追加しますか？ [y/N]: ").strip().lower()
        if confirm != "y":
            print("キャンセルしました")
            return

    # READING_DICT の末尾に追加
    # "}" の直前に挿入
    insert_lines = []
    for word, reading in new_only.items():
        insert_lines.append(f'    "{word}": "{reading}",')

    insert_text = "\n".join(insert_lines) + "\n"

    # READING_DICT = { ... } の最後の } を見つけて挿入
    # 簡易的な方法：最後の "}" の前に挿入
    dict_end = content.find("}\n\n\ndef get_audio_duration")
    if dict_end == -1:
        print("READING_DICT の終端が見つかりません")
        return

    new_content = content[:dict_end] + insert_text + content[dict_end:]

    with open(voice_gen_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"\n{len(new_only)}件の読み方を追加しました")


if __name__ == "__main__":
    readings = check_script_readings()

    if readings:
        update_reading_dict(readings)
