"""
台本生成スクリプト
Gemini APIを使用して2ch/5ch風のスレッド台本をJSON形式で生成
2パス方式：前半（導入〜メイン前半）→後半（メイン後半〜エンディング）で確実に長編を生成

参考データ機能:
- reference_data/transcripts.jsonl から人気チャンネルの台本を読み込み
- スタイル・構成の参考としてプロンプトに含める
"""

import json
import random
import re
import time
from pathlib import Path

import google.generativeai as genai

from config import GEMINI_API_KEY, SCRIPTS_DIR, ROOT_DIR, ensure_directories
from logger import logger

# 参考データディレクトリ
REFERENCE_DATA_DIR = ROOT_DIR / "reference_data"

# Gemini APIの設定
genai.configure(api_key=GEMINI_API_KEY)


def _load_reference_transcripts(max_samples: int = 2) -> list[str]:
    """
    参考チャンネルの字幕データを読み込み、ランダムに数本選んで返す

    Args:
        max_samples: 最大サンプル数

    Returns:
        参考台本テキストのリスト
    """
    transcripts_path = REFERENCE_DATA_DIR / "transcripts.jsonl"
    if not transcripts_path.exists():
        logger.info("参考データなし（reference_data/transcripts.jsonl）")
        return []

    try:
        all_transcripts = []
        with open(transcripts_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    full_text = data.get("full_text", "")
                    if full_text and len(full_text) > 500:  # 短すぎるものは除外
                        all_transcripts.append({
                            "video_id": data.get("video_id", ""),
                            "text": full_text[:3000],  # 長すぎる場合は切り詰め
                        })

        if not all_transcripts:
            return []

        # ランダムに選択
        samples = random.sample(all_transcripts, min(max_samples, len(all_transcripts)))
        logger.info(f"参考データ {len(samples)}本を読み込み")

        return [s["text"] for s in samples]

    except Exception as e:
        logger.warning(f"参考データ読み込みエラー: {e}")
        return []


def _build_reference_section(reference_texts: list[str]) -> str:
    """
    参考台本をプロンプト用のセクションに整形

    Args:
        reference_texts: 参考台本テキストのリスト

    Returns:
        プロンプト用の参考セクション文字列
    """
    if not reference_texts:
        return ""

    sections = []
    for i, text in enumerate(reference_texts, 1):
        sections.append(f"【参考台本{i}】\n{text}\n")

    return f"""
# 参考台本（人気チャンネルのスタイルを学習）
以下は人気2chまとめチャンネルの実際の台本です。
このスタイル・構成・口調を参考にして、同じような雰囲気の台本を作成してください。
ただし、内容はそのままコピーせず、与えられたテーマに沿ったオリジナルの台本を作成すること。

{chr(10).join(sections)}
---
上記の参考台本のスタイルを真似て、以下のテーマで台本を作成してください。
"""

# ===== 共通設定 =====
_COMMON_RULES = """# キャラクター設定（10人のスレ民を満遍なく使うこと）
- "icchi"（イッチ）：スレ主。1回のセリフは長め（40〜100文字）。具体的な数字を多用。
- "res_A"：質問役（「どうやったん？」「具体的に教えて」）+ 有益情報も提供
- "res_B"：共感・応援役（「わかるわ」「ようやっとる」）+ 自分の経験談も語る
- "res_C"：批判・煽り役（「嘘つけ」「金持ち自慢乙」）+ 具体的な反論や別視点を提示
- "res_D"：専門知識役（具体的な数字や制度・知識を提供「○○の場合は〜」「法律的には〜」）
- "res_E"：自分語り（「ワイも同じ経験ある」「ワイの場合は〜」詳しい体験談を語る）
- "res_F"：ツッコミ（「草」「それはないやろ」）+ 他のスレ民に対してもツッコむ
- "res_G"：真面目な議論（「理論的には正しいけど…」具体的な数字で議論）
- "res_H"：初心者目線（「よくわからんのやけど」他のスレ民が教える流れを作る）
- "res_I"：まとめ役（「結局○○が大事ってことやな」話の整理・補足情報追加）
- "res_J"：ユーモア（「ワイには無理で草」）+ たまに有益な雑学も
※同じキャラが3回以上連続で出ないこと。res_A〜res_Jを均等に使うこと。

# 【最重要】スレ民の会話ルール（必ず守ること）
- 【禁止】スレ民がイッチに対して一言だけ反応するパターンの連続は絶対禁止
- 【必須】スレ民同士で会話・議論・情報提供すること（イッチ抜きの連続セリフを必ず入れる）
- 【必須】スレ民が有益な情報を提供すること（具体的な数字、制度の説明、体験談、豆知識）

## スレ民同士の会話パターン（テーマに合わせたオリジナルの会話を作成すること）
【重要】以下は会話パターンの「型」の説明です。例文の内容をそのままコピーせず、テーマに沿った独自の会話を作成してください。

パターン1: 質問→回答→補足（3人のスレ民が会話）
  - res_Hが初心者として質問
  - res_Dが専門知識で回答
  - res_Gが注意点や補足を追加

パターン2: 体験談の共有→分析→展開（4人のスレ民が会話）
  - res_Eが自分の体験談を語る
  - res_Cが数字で分析
  - res_Bが興味を示す
  - res_Dがアドバイス

パターン3: 議論・深掘り（3人のスレ民が議論）
  - res_Gが疑問を投げかける
  - res_Iが解決策を提示
  - res_Cが現実的な視点でツッコむ

- スレ民のセリフで「>>〇〇」のようなアンカー記法は使わないこと
- 5〜6セリフに1回は必ずスレ民同士のやり取り（イッチ抜きで2〜4連続セリフ）を入れること
- スレ民は「草」「マジか」だけの一言反応ではなく、情報を付け加えること

# セリフの長さ目安
- イッチ：40〜100文字（詳しく語る。1つの話題で2〜3回に分けて語ることも可）
- スレ民（反応）：15〜40文字（短いツッコミ、質問、共感など）
- スレ民（情報提供・議論）：40〜80文字（具体的な数字や知識を含む有益な内容）
- ナレーター：30〜60文字

# 制約条件
- イッチのセリフには具体的な数字を多く含めること（年収○万、貯金○万、家賃○万、投資額○万等）
- スレ民も具体的な数字を出すこと（「○○の平均は〜」「○%の人が〜」「○万くらいが相場」等）
- 時系列で語ること（○歳の時、社会人○年目等）
- 【重要】年代は現在（2026年）から1〜2年前の話として語ること。「去年」「一昨年」「2025年」「2024年」などを使用。2023年以前の古い年代は使わないこと。
- 失敗談・挫折のエピソードを必ず含めること
- 口調は2chスラング（「〜やで」「〜ンゴ」「ｗ」「草」「ようやっとる」「マジレス」）を自然に使用
- 「サンガツ」「オッパ」など分かりにくいネットスラングは禁止
- "image_prompt"は重要なシーン（4〜6個）のみ。シンプルな英語で記述
- JSONのみを出力（マークダウンのコードブロック不要）
- 【禁止】スレ本編の途中で「コメント欄で教えてください」「感想を聞かせてください」等の視聴者へのメタ的な呼びかけを入れないこと。これはエンディングのnarrator以外では絶対に使わない。スレ住民はYouTubeのコメント欄の存在を知らない設定。

# 出力形式
JSON配列。各要素は以下の形式：
{{"role": "icchi", "name": "イッチ", "text": "セリフ", "image_prompt": "(任意)"}}
{{"role": "res_A", "name": "名無しさん", "text": "セリフ"}}
{{"role": "narrator", "text": "ナレーション"}}
{{"role": "title_card", "text": "タイトル", "image_prompt": "..."}}
"""

# ===== パート1：導入〜メインストーリー前半 =====
PROMPT_PART1 = """# 命令
あなたは「2ちゃんねる（5ちゃんねる）」の傑作スレッドを作成する放送作家です。
以下のテーマに基づいて、動画台本の【前半部分】をJSON形式で作成してください。
JSONのみを出力し、他の説明文は不要です。
{reference_section}
# テーマ
{theme}

# 前半の構成（【必ず85〜100個】のセリフを出力すること）

## 第1幕：導入（narrator×4 + title_card = 5個）
- narrator: スレッドの紹介「今回ご紹介するスレッドはこちら。「タイトル」」
- narrator: 内容の説明「このスレではイッチが〇〇について語ってくれます」
- narrator: 視聴者へのメッセージ（見どころ紹介）
- narrator: 本編への導線「それでは早速見ていきましょう」
- title_card: タイトル表示

## 第2幕：背景・自己紹介（約30セリフ）
- イッチが詳しい自己紹介（年齢、職業、年収、住居、家族構成など具体的数字）
- スレ民がリアクション（驚き、質問、ツッコミ）
- スレ民同士の会話を入れる（例：res_Hが質問→res_Dが解説）
- テーマの背景となる原体験やきっかけを詳しく語る
- 「なぜそうなったのか」「どういう状況だったのか」をじっくり語る

## 第3幕前半：メインストーリー開始（約55セリフ）
- narrator: 「ここからさらに話が盛り上がります」等の場面転換を1〜2回挟む
- 時系列に沿って具体的なエピソードを詳しく語る（年ごとの変遷、具体的金額）
- 失敗談・挫折エピソードを詳しく語る
- スレ民同士が議論する場面（賛否両論）を含める。具体的数字を出し合う
- スレ民が有益な補足情報を提供（「○○の場合は〜」「制度的には〜」「平均は〜」）
- 5〜6セリフに1回はスレ民だけのやり取りを入れる

【重要】この前半パートでは物語を完結させないでください。
ストーリーの途中（転機や新たな展開が始まるところ）で終わること。
最後にnarrator「ここからイッチの状況が大きく変わります」等の場面転換で締めること。

{common_rules}

# 出力数の確認
【最重要】必ず85〜100個のJSON要素を出力すること。70個以下は絶対に不可。
各幕のセリフ数を守って、必ず合計85個以上を出力すること。"""

# ===== パート2：メインストーリー後半〜エンディング =====
PROMPT_PART2 = """# 命令
あなたは「2ちゃんねる（5ちゃんねる）」の傑作スレッドを作成する放送作家です。
以下の台本の【後半部分】をJSON形式で作成してください。
JSONのみを出力し、他の説明文は不要です。

# テーマ
{theme}

# ここまでのストーリー概要
{story_summary}

# 直前の5つのセリフ（このすぐ後から続けること）
{last_entries}

# 後半の構成（【必ず85〜100個】のセリフを出力すること）

## 第3幕後半：メインストーリー続き（約45セリフ）
- 前半の続きから。転機・大きな変化のエピソードを詳しく語る
- narrator: 場面転換を1〜2回挟む
- スレ民の反応も活発に（議論、共感、批判、質問が混在）
- スレ民同士で議論・情報共有する場面を入れる（例：res_Gが分析→res_Cが反論→res_Iがまとめ）
- 新たな挑戦や工夫を具体的に語る
- 意外な展開やどんでん返しを含める

## 第4幕：教訓・まとめ（約35セリフ）
- narrator: 「いよいよ核心に迫ります」等の場面転換
- イッチが学んだ教訓を具体的にまとめる（3〜5個の教訓をじっくり語る）
- スレ民が補足情報を追加（「○○も大事やで」「○○は注意点やな」）
- スレ民同士で「自分もやってみる」「ワイは○○の方法でやるわ」など議論
- 議論が白熱する場面も含める

## 第5幕：エンディング（約7セリフ）
- イッチの最後の一言
- スレ民の最終反応2〜3個
- narrator: 「今回のスレッドはいかがでしたでしょうか？」
- narrator: テーマに沿ったコメント誘導「あなたの○○体験や工夫があれば、ぜひコメントで教えてください」（テーマに合わせて具体的に。例：投資なら「あなたの投資術」、節約なら「あなたの節約術」、貯金なら「貯金のコツ」など）
- narrator: 「いいねとチャンネル登録もよろしくお願いします。次回もお楽しみに！」
※エンディング以外でコメントや感想を求めるメタ的セリフは禁止
※コメント誘導はエンディングの1回のみ。テーマに関連した具体的な質問形式にすること

{common_rules}

# 出力数の確認
【最重要】必ず85〜100個のJSON要素を出力すること。70個以下は絶対に不可。
各幕のセリフ数を守って、必ず合計85個以上を出力すること。"""


def _extract_json(content: str) -> list:
    """レスポンスからJSONを抽出してパース（修復機能付き）"""
    content = content.strip()

    # マークダウンのコードブロックを削除
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    # 1. そのままパースを試みる
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2. JSON修復を試みる
    repaired = _repair_json(content)
    return json.loads(repaired)


def _repair_json(content: str) -> str:
    """壊れたJSONを修復する"""
    # 末尾のトレーリングカンマを除去
    content = re.sub(r',\s*(\])', r'\1', content)
    content = re.sub(r',\s*(\})', r'\1', content)

    # 配列が閉じていない場合: 最後の完全なオブジェクト `}` まで切って `]` で閉じる
    if content.startswith("[") and not content.rstrip().endswith("]"):
        last_brace = content.rfind("}")
        if last_brace > 0:
            content = content[:last_brace + 1] + "\n]"

    # オブジェクトの途中で切れている場合: 不完全な最後の要素を除去
    try:
        return content if json.loads(content) else content
    except json.JSONDecodeError:
        pass

    # 最後の `},{` を探して、そこまでで閉じる
    last_complete = content.rfind("},")
    if last_complete > 0:
        content = content[:last_complete + 1] + "\n]"
        try:
            json.loads(content)
            return content
        except json.JSONDecodeError:
            pass

    # それでもダメなら元のまま返す（呼び出し元でエラーになる）
    return content


def _summarize_story(entries: list) -> str:
    """台本エントリからストーリー概要を生成"""
    summary_parts = []
    for entry in entries:
        role = entry.get("role", "")
        text = entry.get("text", "")
        if role == "icchi":
            summary_parts.append(f"イッチ: {text}")
        elif role == "narrator" and text:
            summary_parts.append(f"（ナレーション: {text}）")
    # 最大2000文字程度に収める
    summary = "\n".join(summary_parts)
    if len(summary) > 2000:
        summary = summary[:2000] + "..."
    return summary


def _calc_gemini_cost_jpy(
    prompt_tokens: int,
    completion_tokens: int,
    usd_to_jpy: float = 150.0,
) -> float:
    """Gemini 2.0 Flash の推定コスト（円）を算出"""
    # Gemini 2.0 Flash: Input $0.10/1M, Output $0.40/1M
    input_cost = prompt_tokens * 0.10 / 1_000_000
    output_cost = completion_tokens * 0.40 / 1_000_000
    return round((input_cost + output_cost) * usd_to_jpy, 2)


def _get_token_counts(response) -> tuple[int, int, int]:
    """Gemini レスポンスからトークン数を取得"""
    try:
        meta = response.usage_metadata
        prompt_tokens = meta.prompt_token_count or 0
        completion_tokens = meta.candidates_token_count or 0
        total = meta.total_token_count or (prompt_tokens + completion_tokens)
        return prompt_tokens, completion_tokens, total
    except (AttributeError, TypeError):
        return 0, 0, 0


def generate_script(theme: str, output_filename: str = "script.json", use_reference: bool = True) -> dict:
    """
    テーマに基づいて台本を2パスで生成

    Args:
        theme: 動画のテーマ
        output_filename: 出力ファイル名
        use_reference: 参考データを使用するか（デフォルト: True）

    Returns:
        dict: {
            "script": list[dict],    # 台本データ
            "gemini_tokens": int,    # 合計トークン数
            "gemini_cost_jpy": float # 推定コスト（円）
        }
    """
    ensure_directories()

    model = genai.GenerativeModel("gemini-2.0-flash")
    gen_config = genai.types.GenerationConfig(
        temperature=0.9,
        max_output_tokens=16000,
    )

    total_prompt_tokens = 0
    total_completion_tokens = 0

    # ===== 参考データ読み込み =====
    reference_section = ""
    if use_reference:
        reference_texts = _load_reference_transcripts(max_samples=2)
        reference_section = _build_reference_section(reference_texts)

    # ===== パート1: 前半生成 =====
    logger.info(f"テーマ「{theme}」で台本を生成中... (パート1/2: 前半)")

    prompt1 = PROMPT_PART1.format(
        theme=theme,
        common_rules=_COMMON_RULES,
        reference_section=reference_section,
    )

    part1 = None
    for attempt in range(3):
        response1 = model.generate_content(prompt1, generation_config=gen_config)
        p1_prompt, p1_comp, p1_total = _get_token_counts(response1)
        if attempt == 0:
            total_prompt_tokens += p1_prompt
            total_completion_tokens += p1_comp

        try:
            part1 = _extract_json(response1.text)
            break
        except json.JSONDecodeError as e:
            logger.warning(f"パート1 JSONパースエラー (試行{attempt + 1}/3): {e}")
            if attempt == 2:
                logger.error(f"レスポンス内容:\n{response1.text[:500]}")
                raise
            time.sleep(2)

    logger.info(f"パート1完了: {len(part1)}個のエントリ (トークン: {p1_total:,})")

    # ===== パート2: 後半生成 =====
    logger.info(f"台本を生成中... (パート2/2: 後半)")

    # ストーリー概要と直前のエントリを抽出
    story_summary = _summarize_story(part1)
    last_entries = json.dumps(part1[-5:], ensure_ascii=False, indent=2)

    prompt2 = PROMPT_PART2.format(
        theme=theme,
        story_summary=story_summary,
        last_entries=last_entries,
        common_rules=_COMMON_RULES,
    )

    part2 = None
    for attempt in range(3):
        response2 = model.generate_content(prompt2, generation_config=gen_config)
        p2_prompt, p2_comp, p2_total = _get_token_counts(response2)
        if attempt == 0:
            total_prompt_tokens += p2_prompt
            total_completion_tokens += p2_comp

        try:
            part2 = _extract_json(response2.text)
            break
        except json.JSONDecodeError as e:
            logger.warning(f"パート2 JSONパースエラー (試行{attempt + 1}/3): {e}")
            if attempt == 2:
                logger.error(f"レスポンス内容:\n{response2.text[:500]}")
                raise
            time.sleep(2)

    logger.info(f"パート2完了: {len(part2)}個のエントリ (トークン: {p2_total:,})")

    # ===== マージ =====
    script = part1 + part2

    # ファイルに保存
    output_path = SCRIPTS_DIR / output_filename
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    # トークン・コスト集計
    gemini_tokens = total_prompt_tokens + total_completion_tokens
    gemini_cost_jpy = _calc_gemini_cost_jpy(total_prompt_tokens, total_completion_tokens)

    logger.info(f"台本を生成しました: {output_path}")
    logger.info(f"合計シーン数: {len(script)}個 (前半{len(part1)} + 後半{len(part2)})")
    logger.info(f"Geminiトークン: {gemini_tokens:,} (推定コスト: ¥{gemini_cost_jpy})")

    return {
        "script": script,
        "gemini_tokens": gemini_tokens,
        "gemini_cost_jpy": gemini_cost_jpy,
    }


def load_script(filename: str = "script.json") -> dict:
    """既存の台本ファイルを読み込み"""
    script_path = SCRIPTS_DIR / filename
    with open(script_path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("使用法: python 1_script_gen.py <テーマ>")
        print('例: python 1_script_gen.py "20代で投資詐欺にあって借金500万背負った話"')
        sys.exit(1)

    theme = " ".join(sys.argv[1:])
    generate_script(theme)
