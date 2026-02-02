"""
冒頭用画像生成スクリプト
KIEAI (Nanobanana) を使用してテーマに合った画像を生成
画像は assets/images/nanobanana にタグ付けして保存・管理
"""

import json
import time
import shutil
import hashlib
import requests
from pathlib import Path
from datetime import datetime

from PIL import Image
import numpy as np

from config import (
    KIEAI_API_KEY,
    SCRIPTS_DIR,
    NANOBANANA_DIR,
    INTRO_IMAGES_DIR,
    IRASUTOYA_STYLE_PREFIX,
    ensure_directories,
)
from logger import logger

# KIEAI API設定
KIEAI_CREATE_TASK_URL = "https://api.kie.ai/api/v1/jobs/createTask"
KIEAI_GET_TASK_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"
KIEAI_MODEL = "google/nano-banana"

# 画像インデックスファイル
INDEX_FILE = "index.json"


def load_image_index() -> dict:
    """画像インデックスを読み込む"""
    index_path = NANOBANANA_DIR / INDEX_FILE
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"images": []}


def save_image_index(index: dict):
    """画像インデックスを保存"""
    index_path = NANOBANANA_DIR / INDEX_FILE
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def find_images_by_tags(tags: list[str], limit: int = 3) -> list[Path]:
    """
    タグに一致する画像を検索

    Args:
        tags: 検索タグリスト
        limit: 最大取得数

    Returns:
        一致する画像のパスリスト
    """
    index = load_image_index()
    matches = []

    for img_info in index.get("images", []):
        img_tags = set(img_info.get("tags", []))
        search_tags = set(tags)

        # タグの一致度を計算
        match_count = len(img_tags & search_tags)
        if match_count > 0:
            img_path = NANOBANANA_DIR / img_info["filename"]
            if img_path.exists():
                matches.append((match_count, img_path))

    # 一致度順にソート
    matches.sort(key=lambda x: x[0], reverse=True)
    return [m[1] for m in matches[:limit]]


def extract_tags_from_theme(theme: str) -> list[str]:
    """テーマからタグを抽出"""
    # キーワードマッピング
    keyword_tags = {
        "貯金": ["saving", "money", "piggy-bank"],
        "投資": ["investment", "stock", "chart"],
        "資産": ["wealth", "money", "coins"],
        "節約": ["frugal", "wallet", "saving"],
        "給料": ["salary", "office", "work"],
        "借金": ["debt", "worry", "empty-wallet"],
        "副業": ["side-job", "laptop", "work"],
        "株": ["stock", "chart", "investment"],
        "不動産": ["real-estate", "house", "property"],
        "FIRE": ["freedom", "beach", "retirement"],
        "老後": ["elderly", "retirement", "pension"],
        "結婚": ["wedding", "couple", "family"],
        "転職": ["career", "business", "change"],
        "起業": ["startup", "entrepreneur", "business"],
        "1000万": ["million", "wealth", "success"],
        "100万": ["money", "saving", "goal"],
    }

    tags = []
    for keyword, tag_list in keyword_tags.items():
        if keyword in theme:
            tags.extend(tag_list)

    # 重複を除去
    return list(set(tags)) if tags else ["money", "finance", "general"]


def generate_intro_images(
    theme: str,
    num_images: int = 3,
    output_dir: Path = None,
    force_regenerate: bool = False,
) -> list[Path]:
    """
    テーマに合った冒頭用画像を準備

    まずnanobananaフォルダから既存画像を検索し、
    足りない場合のみKIEAIで新規生成

    Args:
        theme: テーマテキスト
        num_images: 必要な画像数（1-3）
        output_dir: 出力ディレクトリ
        force_regenerate: 強制的に再生成

    Returns:
        準備された画像パスのリスト
    """
    ensure_directories()
    output_dir = output_dir or INTRO_IMAGES_DIR

    # 既存の冒頭画像を削除
    for old_img in output_dir.glob("intro_*.png"):
        old_img.unlink()

    # テーマからタグを抽出
    tags = extract_tags_from_theme(theme)
    logger.info(f"テーマタグ: {tags}")

    # 画像プールが20枚未満なら必ず新規生成（種類を増やす）
    MIN_POOL_SIZE = 20
    nb_images = list(NANOBANANA_DIR.glob("nb_*.png"))
    pool_size = len(nb_images)

    if pool_size < MIN_POOL_SIZE:
        force_regenerate = True
        logger.info(f"画像プール: {pool_size}/{MIN_POOL_SIZE} → 新規生成モード")

    # 既存画像を検索
    existing_images = []
    if not force_regenerate:
        existing_images = find_images_by_tags(tags, limit=num_images)
        if existing_images:
            logger.info(f"既存画像を発見: {len(existing_images)}枚")

    # 足りない分を生成
    images_to_generate = num_images - len(existing_images)
    generated_images = []

    if images_to_generate > 0 and KIEAI_API_KEY:
        logger.info(f"新規画像を生成: {images_to_generate}枚")
        prompts = generate_image_prompts(theme, images_to_generate)

        for i, prompt in enumerate(prompts):
            try:
                # 一意のファイル名を生成
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
                filename = f"nb_{timestamp}_{prompt_hash}.png"
                save_path = NANOBANANA_DIR / filename

                logger.info(f"画像生成中 [{i+1}/{images_to_generate}]: {prompt[:50]}...")

                success = generate_single_image(prompt, save_path)
                if success:
                    # インデックスに追加
                    index = load_image_index()
                    index["images"].append({
                        "filename": filename,
                        "prompt": prompt,
                        "tags": tags,
                        "created_at": datetime.now().isoformat(),
                    })
                    save_image_index(index)

                    generated_images.append(save_path)
                    logger.info(f"  保存完了: {filename}")

            except Exception as e:
                logger.error(f"  生成失敗: {e}")

    # 画像を冒頭用フォルダにコピー
    all_images = existing_images + generated_images
    result_paths = []

    for i, img_path in enumerate(all_images[:num_images]):
        output_path = output_dir / f"intro_{i+1:02d}.png"
        shutil.copy2(img_path, output_path)
        result_paths.append(output_path)
        logger.info(f"  配置: {img_path.name} -> {output_path.name}")

    logger.info(f"\n冒頭用画像準備完了: {len(result_paths)}枚")
    return result_paths


def generate_image_prompts(theme: str, num_images: int) -> list[str]:
    """テーマから画像プロンプトを生成"""
    # キーワードマッピング
    keyword_to_prompt = {
        "貯金": "piggy bank with coins, saving money, simple illustration",
        "投資": "stock chart going up, investment growth, coins and bills",
        "資産": "pile of gold coins, wealth, money bag",
        "節約": "wallet with yen bills, frugal lifestyle, simple design",
        "給料": "salary envelope, yen bills, office worker",
        "借金": "empty wallet, debt, worried expression",
        "副業": "laptop with money, side business, working from home",
        "株": "stock market chart, candlestick graph, investment",
        "不動産": "house with yen sign, real estate investment",
        "FIRE": "beach vacation, financial freedom, relaxing person",
        "老後": "elderly couple smiling, retirement savings",
        "結婚": "wedding rings, couple saving money together",
        "転職": "businessman with briefcase, career change",
        "起業": "small shop opening, entrepreneur, startup",
    }

    # デフォルトの金融関連プロンプト
    default_prompts = [
        "money coins and yen bills, simple flat illustration, pastel colors",
        "happy businessman success, simple kawaii style illustration",
        "growth chart going up, investment success, simple design",
        "house and car with money, financial goals achieved",
        "piggy bank overflowing with coins, savings success",
    ]

    prompts = []

    # テーマからキーワードを抽出
    for keyword, prompt in keyword_to_prompt.items():
        if keyword in theme and len(prompts) < num_images:
            full_prompt = f"{IRASUTOYA_STYLE_PREFIX}, {prompt}"
            prompts.append(full_prompt)

    # 足りない分はデフォルトから追加
    for default in default_prompts:
        if len(prompts) >= num_images:
            break
        full_prompt = f"{IRASUTOYA_STYLE_PREFIX}, {default}"
        if full_prompt not in prompts:
            prompts.append(full_prompt)

    return prompts[:num_images]


def generate_single_image(prompt: str, output_path: Path) -> bool:
    """KIEAI APIで単一画像を生成（タスクベースAPI）"""
    headers = {
        "Authorization": f"Bearer {KIEAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": KIEAI_MODEL,
        "input": {
            "prompt": prompt,
            "output_format": "png",
            "image_size": "1:1",
        },
    }

    try:
        # タスク作成
        response = requests.post(
            KIEAI_CREATE_TASK_URL, headers=headers, json=payload, timeout=30
        )
        response.raise_for_status()
        result = response.json()

        if result.get("code") != 200:
            logger.error(f"タスク作成失敗: {result.get('msg', 'Unknown error')}")
            return False

        task_id = result.get("data", {}).get("taskId")
        if not task_id:
            logger.error("タスクIDが取得できませんでした")
            return False

        logger.info(f"  タスク作成: {task_id}")

        # ポーリング（最大120秒）
        max_wait = 120
        poll_interval = 3
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            status_response = requests.get(
                f"{KIEAI_GET_TASK_URL}?taskId={task_id}",
                headers=headers,
                timeout=10,
            )
            status_response.raise_for_status()
            status_result = status_response.json()

            if status_result.get("code") != 200:
                continue

            task_data = status_result.get("data", {})
            state = task_data.get("state", "")

            if state == "success":
                result_json_str = task_data.get("resultJson", "")
                if isinstance(result_json_str, str) and result_json_str:
                    result_json = json.loads(result_json_str)
                else:
                    result_json = result_json_str or {}

                image_urls = result_json.get("resultUrls", [])

                if image_urls and len(image_urls) > 0:
                    image_url = image_urls[0]
                    img_response = requests.get(image_url, timeout=30)
                    img_response.raise_for_status()
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(img_response.content)

                    # 背景透過処理
                    remove_background(output_path)
                    logger.info("  背景透過処理完了")
                    return True
                else:
                    logger.error("画像URLが見つかりません")
                    return False

            elif state == "fail":
                fail_msg = task_data.get("failMsg", "Unknown error")
                logger.error(f"画像生成失敗: {fail_msg}")
                return False

            logger.info(f"  状態: {state} ({elapsed}秒経過)")

        logger.error("タイムアウト")
        return False

    except requests.exceptions.RequestException as e:
        logger.error(f"APIリクエスト失敗: {e}")
    except Exception as e:
        logger.error(f"画像生成失敗: {e}")

    return False


def remove_background(image_path: Path, threshold: int = 240) -> bool:
    """画像の白背景を透過処理"""
    try:
        img = Image.open(image_path).convert("RGBA")
        data = np.array(img)

        r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]
        white_mask = (r >= threshold) & (g >= threshold) & (b >= threshold)
        data[:, :, 3] = np.where(white_mask, 0, a)

        result = Image.fromarray(data)
        result.save(image_path, "PNG")
        return True

    except Exception as e:
        logger.error(f"背景透過処理失敗: {e}")
        return False


def generate_from_script(script_path: Path = None) -> list[Path]:
    """台本からテーマを読み取って画像を準備"""
    script_path = script_path or (SCRIPTS_DIR / "script.json")

    if not script_path.exists():
        logger.error(f"台本が見つかりません: {script_path}")
        return []

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    # テーマを取得
    theme = ""
    for scene in script:
        if scene.get("role") == "title_card":
            theme = scene.get("text", "")
            break
        elif scene.get("role") == "narrator" and not theme:
            theme = scene.get("text", "")

    if not theme:
        logger.error("テーマが見つかりません")
        return []

    logger.info(f"テーマ: {theme[:50]}...")
    return generate_intro_images(theme)


if __name__ == "__main__":
    paths = generate_from_script()
    for p in paths:
        print(f"生成: {p}")
