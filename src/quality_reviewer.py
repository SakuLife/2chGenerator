"""
品質レビューモジュール
台本生成後にGeminiで品質チェック＋自動修正を行う自己改善システム
"""

import json
import re
from pathlib import Path

import google.generativeai as genai

from config import GEMINI_API_KEY, SCRIPTS_DIR
from logger import logger

# Gemini APIの設定
genai.configure(api_key=GEMINI_API_KEY)


def review_script(
    theme: str,
    script_data: list[dict],
    max_retries: int = 2,
) -> dict:
    """
    台本の品質をレビューし、問題があれば修正版を返す

    Args:
        theme: 動画テーマ
        script_data: 台本データ（JSONリスト）
        max_retries: 最大修正試行回数

    Returns:
        {
            "script": list[dict],  # 修正済み台本（問題なければ元のまま）
            "issues_found": list[str],  # 検出した問題
            "fixes_applied": list[str],  # 適用した修正
            "quality_score": int,  # 品質スコア (0-100)
        }
    """
    result = {
        "script": script_data,
        "issues_found": [],
        "fixes_applied": [],
        "quality_score": 0,
    }

    # === 1. ローカルチェック（高速・無料） ===
    local_issues = _check_local(theme, script_data)
    result["issues_found"].extend(local_issues)

    # ローカルで自動修正可能なものを修正
    if local_issues:
        script_data, local_fixes = _apply_local_fixes(theme, script_data, local_issues)
        result["script"] = script_data
        result["fixes_applied"].extend(local_fixes)

    # === 2. AIレビュー（Gemini） ===
    ai_result = _review_with_ai(theme, script_data)
    result["quality_score"] = ai_result.get("score", 70)
    ai_issues = ai_result.get("issues", [])
    result["issues_found"].extend(ai_issues)

    # スコアが低い場合はAIに修正させる
    if result["quality_score"] < 60 and max_retries > 0:
        logger.warning(f"品質スコア {result['quality_score']}/100 — AI修正を試行")
        fixed_script = _fix_with_ai(theme, script_data, ai_issues)
        if fixed_script:
            result["script"] = fixed_script
            result["fixes_applied"].append("AI台本修正")
            # 修正後に再スコアリング
            re_review = _review_with_ai(theme, fixed_script)
            result["quality_score"] = re_review.get("score", 70)
            logger.info(f"修正後スコア: {result['quality_score']}/100")

    logger.info(f"品質レビュー完了: スコア={result['quality_score']}/100, "
                f"問題={len(result['issues_found'])}件, "
                f"修正={len(result['fixes_applied'])}件")

    return result


def _check_local(theme: str, script_data: list[dict]) -> list[str]:
    """ローカルルールベースのチェック"""
    issues = []

    # テーマから数値を抽出
    theme_numbers = _extract_numbers_with_units(theme)

    # 台本全文
    all_text = " ".join(s.get("text", "") for s in script_data)

    # --- チェック1: テーマの数値が台本で正しく使われているか ---
    for num_str, value, unit in theme_numbers:
        # テーマの数値が台本内に存在するか
        if num_str not in all_text:
            # 桁違いの数値がないかチェック
            wrong_variants = _get_wrong_number_variants(value, unit)
            for wrong in wrong_variants:
                if wrong in all_text:
                    issues.append(
                        f"数値誤り: テーマ「{num_str}」が台本で「{wrong}」になっている"
                    )
                    break

    # --- チェック2: 極端に短い/長い台本 ---
    line_count = len(script_data)
    if line_count < 150:
        issues.append(f"台本が短すぎる（{line_count}行、推奨170+）")
    elif line_count > 250:
        issues.append(f"台本が長すぎる（{line_count}行、推奨170-220）")

    # --- チェック3: キャラクターバランス ---
    role_counts: dict[str, int] = {}
    for s in script_data:
        role = s.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1

    # icchiが少なすぎ/多すぎ
    icchi_count = role_counts.get("icchi", 0)
    res_total = sum(v for k, v in role_counts.items() if k.startswith("res_"))
    if icchi_count > 0 and res_total > 0:
        ratio = icchi_count / (icchi_count + res_total)
        if ratio > 0.5:
            issues.append(f"イッチの比率が高すぎ（{ratio:.0%}、推奨30-40%）")
        elif ratio < 0.15:
            issues.append(f"イッチの比率が低すぎ（{ratio:.0%}、推奨30-40%）")

    # 使用されていないレスキャラ
    used_res = {k for k in role_counts if k.startswith("res_")}
    expected_res = {f"res_{chr(65+i)}" for i in range(10)}  # res_A ~ res_J
    unused = expected_res - used_res
    if len(unused) >= 5:
        issues.append(f"未使用キャラが多い: {', '.join(sorted(unused))}")

    # --- チェック4: 一言レス連続 ---
    short_streak = 0
    max_short_streak = 0
    for s in script_data:
        text = s.get("text", "")
        if s.get("role", "").startswith("res_") and len(text) < 10:
            short_streak += 1
            max_short_streak = max(max_short_streak, short_streak)
        else:
            short_streak = 0

    if max_short_streak >= 4:
        issues.append(f"一言レスが{max_short_streak}連続（コンテンツが薄い）")

    # --- チェック5: 同じキャラの連続 ---
    prev_role = None
    same_streak = 0
    for s in script_data:
        role = s.get("role", "")
        if role == prev_role and role not in ("narrator", "title_card"):
            same_streak += 1
            if same_streak >= 3:
                issues.append(f"同じキャラ「{role}」が4回以上連続")
                break
        else:
            same_streak = 0
        prev_role = role

    return issues


def _apply_local_fixes(
    theme: str,
    script_data: list[dict],
    issues: list[str],
) -> tuple[list[dict], list[str]]:
    """ローカルで自動修正できる問題を修正"""
    fixes = []
    script = [dict(s) for s in script_data]  # ディープコピー

    theme_numbers = _extract_numbers_with_units(theme)

    for issue in issues:
        if "数値誤り" not in issue:
            continue

        # テーマの正しい数値と、台本内の間違い数値を特定
        for num_str, value, unit in theme_numbers:
            wrong_variants = _get_wrong_number_variants(value, unit)
            for wrong in wrong_variants:
                replaced = False
                for s in script:
                    if wrong in s.get("text", ""):
                        s["text"] = s["text"].replace(wrong, num_str)
                        replaced = True
                if replaced:
                    fixes.append(f"「{wrong}」→「{num_str}」に修正")

    return script, fixes


def _extract_numbers_with_units(text: str) -> list[tuple[str, int, str]]:
    """テキストから数値+単位を抽出

    Returns:
        [(表記文字列, 数値, 単位), ...] e.g., [("400万", 400, "万")]
    """
    results = []
    for m in re.finditer(r"(\d+)(万|億|兆|%|円)", text):
        num_str = m.group(0)
        value = int(m.group(1))
        unit = m.group(2)
        results.append((num_str, value, unit))
    return results


def _get_wrong_number_variants(value: int, unit: str) -> list[str]:
    """よくある数値間違いのバリエーションを生成"""
    variants = []
    # 10倍間違い
    variants.append(f"{value * 10}{unit}")
    # 1/10間違い
    if value >= 10 and value % 10 == 0:
        variants.append(f"{value // 10}{unit}")
    # 桁上がり・桁下がり
    if unit == "万":
        # 万→億の間違い
        variants.append(f"{value}億")
        # 100万 → 1000万 等
        if value < 1000:
            variants.append(f"{value}0{unit}")
    return variants


def _review_with_ai(theme: str, script_data: list[dict]) -> dict:
    """GeminiでAIレビュー"""
    model = genai.GenerativeModel("gemini-2.0-flash")

    # 台本を簡略化して送信（トークン節約）
    script_summary = []
    for i, s in enumerate(script_data):
        role = s.get("role", "?")
        text = s.get("text", "")
        script_summary.append(f"[{i}] {role}: {text}")

    script_text = "\n".join(script_summary)

    prompt = f"""あなたはYouTube 2chまとめ動画の品質チェッカーです。
以下の台本を評価し、問題点を指摘してください。

テーマ: {theme}

台本:
{script_text}

以下の観点で0-100点のスコアと問題点を返してください：

【評価基準】
1. 数値の正確性（テーマの数値と台本内の数値に矛盾がないか）
2. 展開の面白さ（視聴者を引きつける構成か、だれる箇所がないか）
3. 情報の有益性（視聴者が「見てよかった」と思える内容があるか）
4. キャラバランス（10人のスレ民が均等に活躍しているか）
5. テンポ（一言だけのレスが連続していないか、冗長な箇所がないか）
6. リアリティ（2chらしい雰囲気が出ているか、不自然な点がないか）

【出力形式（JSON）】
{{"score": 75, "issues": ["問題1", "問題2"], "strengths": ["良い点1"]}}

JSONのみ出力:"""

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=500,
            ),
        )
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        result = json.loads(text)
        logger.info(f"AIレビュー: スコア={result.get('score', '?')}/100")
        if result.get("strengths"):
            logger.info(f"  良い点: {', '.join(result['strengths'][:3])}")
        if result.get("issues"):
            for issue in result["issues"][:5]:
                logger.warning(f"  問題: {issue}")
        return result
    except Exception as e:
        logger.warning(f"AIレビュー失敗: {e}")
        return {"score": 70, "issues": [], "strengths": []}


def _fix_with_ai(
    theme: str,
    script_data: list[dict],
    issues: list[str],
) -> list[dict] | None:
    """AIに台本の問題箇所を修正させる"""
    model = genai.GenerativeModel("gemini-2.0-flash")

    # 問題のある箇所だけ修正（全体再生成は避ける）
    issues_text = "\n".join(f"- {issue}" for issue in issues)

    # 台本を文字列に
    script_json = json.dumps(script_data, ensure_ascii=False, indent=None)

    prompt = f"""以下の2chまとめ動画の台本に問題があります。問題箇所のみを修正してください。
台本の構造（JSON配列の各要素のrole/name/text/image_prompt）は変えないこと。

テーマ: {theme}

【問題点】
{issues_text}

【修正ルール】
- 数値の間違いは正しい数値に修正
- 一言レスの連続は、情報を付け加えて有益にする
- キャラバランスが悪い場合、使われていないキャラのセリフを追加
- テーマに沿った内容であること
- 修正は最小限に（大幅な書き換えは不要）

【台本（JSON）】
{script_json}

修正済みのJSON配列のみを出力してください:"""

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=8000,
            ),
        )
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        fixed = json.loads(text)
        if isinstance(fixed, list) and len(fixed) > 100:
            logger.info(f"AI修正完了: {len(fixed)}行")
            return fixed
        else:
            logger.warning("AI修正結果が不正（短すぎ）")
            return None
    except Exception as e:
        logger.warning(f"AI修正失敗: {e}")
        return None


def review_thumbnail_text(theme: str, title: str, hook: str) -> dict:
    """
    サムネイル用テキストの品質チェック

    Args:
        theme: 元のテーマ
        title: サムネタイトル
        hook: サムネフック文

    Returns:
        {"ok": bool, "title": str, "hook": str, "reason": str}
    """
    issues = []

    # 長さチェック
    if len(title) > 12:
        issues.append(f"タイトルが長すぎ（{len(title)}文字、最大12）")
    if len(hook) > 15:
        issues.append(f"フックが長すぎ（{len(hook)}文字、最大15）")

    # テーマの数値がサムネに含まれるかチェック
    theme_numbers = _extract_numbers_with_units(theme)
    for num_str, value, unit in theme_numbers:
        combined = title + hook
        if num_str not in combined:
            # 桁違いチェック
            wrong_variants = _get_wrong_number_variants(value, unit)
            for wrong in wrong_variants:
                if wrong in combined:
                    issues.append(f"サムネの数値「{wrong}」はテーマ「{num_str}」と不一致")

    if not issues:
        return {"ok": True, "title": title, "hook": hook, "reason": ""}

    # 問題があればAIで再生成
    logger.warning(f"サムネテキスト問題: {issues}")
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""YouTube 2chまとめ動画のサムネイル用テキストを修正してください。

元テーマ: {theme}
現在のタイトル: {title}
現在のフック: {hook}

問題点:
{chr(10).join('- ' + i for i in issues)}

修正ルール:
- テーマの数値を正確に使う
- タイトル: 最大10文字
- フック: 最大12文字
- インパクト重視

出力（JSON）: {{"title": "修正タイトル", "hook": "修正フック"}}
JSONのみ:"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        result = json.loads(text)
        return {
            "ok": False,
            "title": result.get("title", title),
            "hook": result.get("hook", hook),
            "reason": "; ".join(issues),
        }
    except Exception as e:
        logger.warning(f"サムネテキスト修正失敗: {e}")
        return {"ok": False, "title": title, "hook": hook, "reason": str(e)}
