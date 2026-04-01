"""
パフォーマンス分析モジュール
過去動画の成績を分析し、テーマ選定・台本生成にフィードバックする自己改善システム
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import google.generativeai as genai

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(1, str(Path(__file__).parent.parent.parent))

from Skills.google import SheetsClient, GoogleAuth

from config import (
    GEMINI_API_KEY,
    GOOGLE_SHEETS_ID,
    GOOGLE_SERVICE_ACCOUNT,
    GOOGLE_CLIENT_SECRETS_FILE,
    ROOT_DIR,
    GENERATED_DIR,
)
from logger import logger

genai.configure(api_key=GEMINI_API_KEY)

# フィードバックファイルの保存先
FEEDBACK_PATH = GENERATED_DIR / "performance_feedback.json"


class PerformanceAnalyzer:
    """過去動画のパフォーマンスを分析し改善フィードバックを生成"""

    def __init__(
        self,
        spreadsheet_id: str | None = None,
        service_account_file: str | None = None,
        client_secrets_file: str | None = None,
    ):
        self.spreadsheet_id = spreadsheet_id or GOOGLE_SHEETS_ID
        self.service_account_file = service_account_file or GOOGLE_SERVICE_ACCOUNT
        self.client_secrets_file = client_secrets_file or GOOGLE_CLIENT_SECRETS_FILE
        self.sheets: SheetsClient | None = None

    def _ensure_sheets(self) -> None:
        """Sheetsクライアントを初期化"""
        if self.sheets:
            return
        if not self.spreadsheet_id:
            raise RuntimeError("GOOGLE_SHEETS_IDが未設定")

        if self.service_account_file:
            self.sheets = SheetsClient(
                self.spreadsheet_id,
                service_account_file=self.service_account_file,
            )
        elif self.client_secrets_file and Path(self.client_secrets_file).exists():
            auth = GoogleAuth(self.client_secrets_file, ROOT_DIR)
            self.sheets = SheetsClient(self.spreadsheet_id, auth=auth)
        else:
            raise RuntimeError("Sheets認証情報がありません")

    def get_video_data(self, sheet_name: str = "生成ログ") -> list[dict]:
        """
        スプレッドシートから動画データを取得

        Returns:
            動画データのリスト（再生数あり分のみ）
        """
        self._ensure_sheets()
        values = self.sheets.get_values(f"{sheet_name}!A:R")

        if len(values) <= 1:
            return []

        headers = values[0]
        videos = []

        for row in values[1:]:
            if len(row) < 7:
                continue

            # 再生数がない行はスキップ
            views_str = row[6] if len(row) > 6 else ""
            if not views_str:
                continue

            try:
                views = int(views_str)
            except (ValueError, TypeError):
                continue

            likes = 0
            if len(row) > 7 and row[7]:
                try:
                    likes = int(row[7])
                except (ValueError, TypeError):
                    pass

            comments = 0
            if len(row) > 8 and row[8]:
                try:
                    comments = int(row[8])
                except (ValueError, TypeError):
                    pass

            videos.append({
                "date": row[0] if len(row) > 0 else "",
                "theme": row[1] if len(row) > 1 else "",
                "duration": row[2] if len(row) > 2 else "",
                "views": views,
                "likes": likes,
                "comments": comments,
            })

        return videos

    def analyze(self) -> dict[str, Any]:
        """
        パフォーマンス分析を実行

        Returns:
            {
                "total_videos": int,
                "avg_views": float,
                "top_videos": list[dict],  # 上位5本
                "bottom_videos": list[dict],  # 下位5本
                "insights": list[str],  # AIが生成した改善インサイト
                "theme_guidance": str,  # テーマ選定ガイダンス
                "script_guidance": str,  # 台本生成ガイダンス
            }
        """
        try:
            videos = self.get_video_data()
        except Exception as e:
            logger.warning(f"パフォーマンスデータ取得失敗: {e}")
            return self._load_cached_feedback()

        if len(videos) < 3:
            logger.info("分析に十分なデータがありません（3本以上必要）")
            return {
                "total_videos": len(videos),
                "avg_views": 0,
                "top_videos": [],
                "bottom_videos": [],
                "insights": [],
                "theme_guidance": "",
                "script_guidance": "",
            }

        # 再生数でソート
        sorted_videos = sorted(videos, key=lambda v: v["views"], reverse=True)
        avg_views = sum(v["views"] for v in videos) / len(videos)

        top_videos = sorted_videos[:5]
        bottom_videos = sorted_videos[-5:]

        # AIで分析
        ai_analysis = self._analyze_with_ai(videos, top_videos, bottom_videos, avg_views)

        result = {
            "total_videos": len(videos),
            "avg_views": round(avg_views),
            "top_videos": top_videos,
            "bottom_videos": bottom_videos,
            "insights": ai_analysis.get("insights", []),
            "theme_guidance": ai_analysis.get("theme_guidance", ""),
            "script_guidance": ai_analysis.get("script_guidance", ""),
            "analyzed_at": datetime.now().isoformat(),
        }

        # キャッシュに保存
        self._save_feedback(result)

        return result

    def _analyze_with_ai(
        self,
        all_videos: list[dict],
        top_videos: list[dict],
        bottom_videos: list[dict],
        avg_views: float,
    ) -> dict:
        """AIでパフォーマンスパターンを分析"""
        model = genai.GenerativeModel("gemini-2.0-flash")

        top_text = "\n".join(
            f"  - 「{v['theme']}」再生数:{v['views']:,} いいね:{v['likes']}"
            for v in top_videos
        )
        bottom_text = "\n".join(
            f"  - 「{v['theme']}」再生数:{v['views']:,} いいね:{v['likes']}"
            for v in bottom_videos
        )
        all_themes = "\n".join(
            f"  - 「{v['theme']}」→ {v['views']:,}再生"
            for v in all_videos
        )

        prompt = f"""あなたはYouTubeチャンネルのデータアナリストです。
2ch/5chまとめ系のお金チャンネルの動画パフォーマンスを分析してください。

【全動画データ】（新しい順）
{all_themes}

【上位動画（好成績）】
{top_text}

【下位動画（低成績）】
{bottom_text}

平均再生数: {avg_views:,.0f}

以下を分析してJSON形式で出力してください：

1. insights: 成功パターンと失敗パターンの具体的な分析（5つ以内）
2. theme_guidance: 次に作るべきテーマの方向性（具体的に。数値例やキーワードを含める）
3. script_guidance: 台本で改善すべき点（具体的に。構成、テンポ、情報量など）

【出力JSON】
{{
  "insights": ["分析1", "分析2", ...],
  "theme_guidance": "テーマ選定のガイダンス（200字以内）",
  "script_guidance": "台本改善のガイダンス（200字以内）"
}}

JSONのみ出力:"""

        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=1000,
                ),
            )
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            result = json.loads(text)
            logger.info("パフォーマンス分析完了:")
            for insight in result.get("insights", [])[:3]:
                logger.info(f"  💡 {insight}")
            return result
        except Exception as e:
            logger.warning(f"AI分析失敗: {e}")
            return {}

    def _save_feedback(self, data: dict) -> None:
        """フィードバックをファイルに保存"""
        FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"フィードバック保存: {FEEDBACK_PATH}")

    def _load_cached_feedback(self) -> dict:
        """キャッシュされたフィードバックを読み込み"""
        if FEEDBACK_PATH.exists():
            try:
                with open(FEEDBACK_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info("キャッシュ済みフィードバックを使用")
                return data
            except Exception:
                pass
        return {
            "total_videos": 0,
            "avg_views": 0,
            "top_videos": [],
            "bottom_videos": [],
            "insights": [],
            "theme_guidance": "",
            "script_guidance": "",
        }

    def get_feedback_for_theme_suggestion(self) -> str:
        """
        テーマ提案用のフィードバック文字列を返す

        Returns:
            テーマ選定に活用できるガイダンス文字列
        """
        feedback = self._load_cached_feedback()
        if not feedback.get("theme_guidance"):
            return ""

        parts = []
        if feedback.get("insights"):
            parts.append("【過去動画の分析結果】")
            for insight in feedback["insights"][:3]:
                parts.append(f"- {insight}")

        if feedback.get("theme_guidance"):
            parts.append(f"\n【テーマ選定ガイダンス】\n{feedback['theme_guidance']}")

        if feedback.get("top_videos"):
            parts.append("\n【好成績テーマ例】")
            for v in feedback["top_videos"][:3]:
                parts.append(f"- 「{v['theme']}」{v['views']:,}再生")

        if feedback.get("bottom_videos"):
            parts.append("\n【低成績テーマ（避けるべきパターン）】")
            for v in feedback["bottom_videos"][:3]:
                parts.append(f"- 「{v['theme']}」{v['views']:,}再生")

        return "\n".join(parts)

    def get_feedback_for_script_gen(self) -> str:
        """
        台本生成用のフィードバック文字列を返す

        Returns:
            台本生成に活用できるガイダンス文字列
        """
        feedback = self._load_cached_feedback()
        if not feedback.get("script_guidance"):
            return ""

        return f"""# 過去動画の改善フィードバック（自動分析結果）
{feedback['script_guidance']}

※このフィードバックは過去{feedback.get('total_videos', 0)}本の再生数データに基づく自動分析です。"""
