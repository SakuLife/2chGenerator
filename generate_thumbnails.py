"""
指定した2動画のサムネイルを台本データから生成するスクリプト
"""

import sys
import json
from pathlib import Path

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import THUMBNAIL_DIR, SCRIPTS_DIR, ensure_directories
from src.thumbnail_gen import (
    _split_theme,
    _mask_bubble_texts,
    _build_thumbnail_prompt,
    _generate_with_ai,
    _generate_with_pil,
    W, H,
    logger,
)
from PIL import Image


def generate_custom_thumbnail(
    theme: str,
    bubble_texts: list[str],
    output_name: str,
) -> dict:
    """
    カスタム吹き出しテキストでサムネイルを生成
    """
    ensure_directories()

    output_path = THUMBNAIL_DIR / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # テーマ分割
    title, hook = _split_theme(theme)

    # 吹き出しテキストをマスク
    bubbles = _mask_bubble_texts(bubble_texts)

    logger.info("=" * 60)
    logger.info(f"サムネイル生成: {output_name}")
    logger.info("=" * 60)
    logger.info(f"タイトル: {title}")
    logger.info(f"フック: {hook}")
    logger.info(f"吹き出し（マスク前）: {bubble_texts}")
    logger.info(f"吹き出し（マスク後）: {bubbles}")

    kieai_credits = 0

    # NanoBananaPro で全体生成
    prompt = _build_thumbnail_prompt(title, hook, bubbles)
    ai_tmp = THUMBNAIL_DIR / f"tmp_{output_name.replace('.jpg', '.png')}"
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


def main():
    """2つの動画のサムネイルを生成"""

    # 動画1: 年収700万 住宅ローン
    theme1 = "【悲報】年収700万の俺、住宅ローン組んだら生活水準ガタ落ちしてワロタ…これマジ？"
    bubbles1 = [
        "頭金500万貯めた",
        "ローン4500万組んだ",
        "固定資産税 年30万",
        "月16万の返済地獄",
        "副業で月10万稼ぐ",
    ]

    result1 = generate_custom_thumbnail(
        theme=theme1,
        bubble_texts=bubbles1,
        output_name="thumbnail_700man_loan.jpg",
    )
    logger.info(f"動画1完了: {result1}")

    print()

    # 動画2: 年収800万 ふるさと納税
    theme2 = "【悲報】年収800万の俺が「ふるさと納税」をガチで研究した結果…まさかの落とし穴に気づいたwww"
    bubbles2 = [
        "控除上限額7万5千円",
        "競馬で50万当てた",
        "一時所得で1万円損",
        "iDeCoで所得控除",
        "年収だけで判断するな",
    ]

    result2 = generate_custom_thumbnail(
        theme=theme2,
        bubble_texts=bubbles2,
        output_name="thumbnail_800man_furusato.jpg",
    )
    logger.info(f"動画2完了: {result2}")

    print()
    logger.info("=" * 60)
    logger.info("全サムネイル生成完了!")
    logger.info("=" * 60)
    logger.info(f"動画1: {result1['path']} (KieAI: {result1['kieai_credits']}クレジット)")
    logger.info(f"動画2: {result2['path']} (KieAI: {result2['kieai_credits']}クレジット)")


if __name__ == "__main__":
    main()
