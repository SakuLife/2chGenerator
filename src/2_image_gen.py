"""
画像生成スクリプト
台本に含まれるimage_promptから画像を生成
- KieAI Nanobanana（いらすとや風）: デフォルト、2クレジット/枚
- OpenAI DALL-E 3: 高品質オプション

キャッシュ機能付きで同じプロンプトの再生成を防ぐ
"""

import json
from pathlib import Path

import requests
from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    KIEAI_API_KEY,
    KIEAI_API_BASE,
    SCRIPTS_DIR,
    IMAGES_DIR,
    ensure_directories,
)
from logger import logger
from image_cache import image_cache
from kieai_client import KieAIClient

# OpenAIクライアント（初期化はAPIキーがある場合のみ）
openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

# KieAIクライアント（初期化はAPIキーがある場合のみ）
kieai_client = None
if KIEAI_API_KEY and KIEAI_API_KEY != "your_kieai_api_key_here":
    kieai_client = KieAIClient(api_key=KIEAI_API_KEY, api_base=KIEAI_API_BASE)


def generate_image_openai(prompt: str, output_path: Path) -> bool:
    """
    OpenAI DALL-E 3で画像生成

    Args:
        prompt: 画像生成プロンプト
        output_path: 保存先パス

    Returns:
        成功したかどうか
    """
    if not openai_client:
        logger.error("  エラー: OPENAI_API_KEYが設定されていません")
        return False

    try:
        logger.info(f"  DALL-E 3で生成中: {prompt[:50]}...")

        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="standard",
            n=1,
        )

        # 画像URLを取得してダウンロード
        image_url = response.data[0].url
        img_data = requests.get(image_url).content

        with open(output_path, "wb") as f:
            f.write(img_data)

        logger.info(f"  保存完了: {output_path.name}")
        return True

    except Exception as e:
        logger.error(f"  エラー: {e}")
        return False


def generate_image_kieai(prompt: str, output_path: Path) -> bool:
    """
    KieAI Nanobananaで画像生成（いらすとや風）

    Args:
        prompt: 画像生成プロンプト
        output_path: 保存先パス

    Returns:
        成功したかどうか
    """
    if not kieai_client:
        logger.error("  エラー: KIEAI_API_KEYが設定されていません")
        return False

    try:
        # いらすとや風にプロンプトを変換
        styled_prompt = image_cache.transform_to_irasutoya_style(prompt)
        logger.info(f"  Nanobanana (いらすとや風) で生成中: {prompt[:50]}...")

        # キャッシュをチェック
        if image_cache.exists(styled_prompt):
            image_cache.get(styled_prompt, output_path)
            return True

        # 新規生成
        kieai_client.generate_and_download(
            prompt=styled_prompt,
            output_path=output_path,
            aspect_ratio="16:9",
        )

        # キャッシュに保存
        image_cache.save(styled_prompt, output_path)

        logger.info(f"  保存完了: {output_path.name}")
        return True

    except Exception as e:
        logger.error(f"  エラー: {e}")
        return False


def generate_images_from_script(
    script_path: Path,
    method: str = "kieai",  # デフォルトをkieaiに変更
) -> dict:
    """
    台本から画像を一括生成

    Args:
        script_path: 台本JSONファイルのパス
        method: 画像生成方法（"kieai" or "openai"）

    Returns:
        {index: image_path} の辞書
    """
    ensure_directories()

    # 台本を読み込み
    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    logger.info(f"台本を読み込みました: {script_path.name}")
    logger.info(f"画像生成方法: {method.upper()}")

    image_map = {}

    for i, scene in enumerate(script):
        # image_promptがある場合のみ生成
        if "image_prompt" not in scene:
            continue

        prompt = scene["image_prompt"]
        output_path = IMAGES_DIR / f"{i:03d}_{scene['role']}.png"

        # 既に存在する場合はスキップ
        if output_path.exists():
            logger.info(f"[{i:03d}] スキップ（既存）: {output_path.name}")
            image_map[i] = str(output_path)
            continue

        # 画像生成
        logger.info(f"[{i:03d}] 生成開始")

        if method == "openai":
            success = generate_image_openai(prompt, output_path)
        elif method == "kieai":
            success = generate_image_kieai(prompt, output_path)
        else:
            logger.error(f"  エラー: 未対応の生成方法 '{method}'")
            continue

        if success:
            image_map[i] = str(output_path)

    logger.info(f"\n画像生成完了: {len(image_map)}枚")

    # 画像マップをJSONで保存（動画編集時に使用）
    image_map_path = IMAGES_DIR / "image_map.json"
    with open(image_map_path, "w", encoding="utf-8") as f:
        json.dump(image_map, f, ensure_ascii=False, indent=2)

    return image_map


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("使用法: python 2_image_gen.py <method>")
        print("  method: kieai (デフォルト) または openai")
        print("例: python 2_image_gen.py kieai")
        sys.exit(1)

    method = sys.argv[1].lower()
    script_path = SCRIPTS_DIR / "script.json"

    if not script_path.exists():
        print(f"エラー: 台本ファイルが見つかりません: {script_path}")
        sys.exit(1)

    generate_images_from_script(script_path, method)
