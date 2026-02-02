"""
テーマ提案モジュール
YouTube競合分析 + 自チャンネル分析 + LLMによるテーマ生成
過去テーマとの重複排除機能付き
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import google.generativeai as genai

# Skills を使えるようにパスを追加（リポジトリ内 → 共有フォルダの順で探索）
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(1, str(Path(__file__).parent.parent.parent))

from Skills.google import YouTubeDataClient, YouTubeAnalyticsClient, GoogleAuth
from Skills.google import SheetsClient

from config import YOUTUBE_API_KEY, GEMINI_API_KEY, ROOT_DIR
from logger import logger

# Gemini APIの設定
genai.configure(api_key=GEMINI_API_KEY)


class ThemeSuggester:
    """テーマ提案クラス"""

    # 2chまとめ系の競合チャンネル（例）
    DEFAULT_COMPETITOR_CHANNELS = [
        # ここに競合チャンネルIDを追加
        # "UCxxxxxxx",
    ]

    # 検索キーワード
    SEARCH_VARIATIONS = [
        "貯金",
        "投資",
        "FIRE",
        "年収",
        "副業",
        "借金",
        "資産形成",
        "節約",
        "老後",
        "住宅ローン",
    ]

    def __init__(
        self,
        youtube_api_key: str | None = None,
        client_secrets_file: str | None = None,
        spreadsheet_id: str | None = None,
    ):
        """
        Args:
            youtube_api_key: YouTube Data API キー（競合分析用）
            client_secrets_file: OAuthクライアントシークレット（自チャンネル分析用）
            spreadsheet_id: 記録用スプレッドシートID（重複排除用）
        """
        self.youtube_api_key = youtube_api_key
        self.client_secrets_file = client_secrets_file or str(
            ROOT_DIR / "client_secrets.json"
        )
        self.spreadsheet_id = spreadsheet_id

        self.youtube_data: YouTubeDataClient | None = None
        self.youtube_analytics: YouTubeAnalyticsClient | None = None

    def _ensure_youtube_data(self):
        """YouTube Data APIクライアントを初期化"""
        if not self.youtube_data and self.youtube_api_key:
            self.youtube_data = YouTubeDataClient(api_key=self.youtube_api_key)

    def _ensure_youtube_analytics(self):
        """YouTube Analyticsクライアントを初期化"""
        if not self.youtube_analytics and Path(self.client_secrets_file).exists():
            auth = GoogleAuth(self.client_secrets_file, ROOT_DIR)
            self.youtube_analytics = YouTubeAnalyticsClient(auth=auth)

    def analyze_competitors(
        self,
        channel_ids: list[str] | None = None,
    ) -> dict | None:
        """
        競合チャンネルを分析

        Args:
            channel_ids: 分析対象のチャンネルID（省略時はデフォルト）

        Returns:
            分析結果
        """
        if not self.youtube_api_key:
            logger.warning("YouTube API キーが設定されていません")
            return None

        self._ensure_youtube_data()

        channel_ids = channel_ids or self.DEFAULT_COMPETITOR_CHANNELS

        if not channel_ids:
            logger.warning("競合チャンネルIDが設定されていません")
            return None

        logger.info(f"競合チャンネル分析中: {len(channel_ids)}チャンネル")

        return self.youtube_data.analyze_competitors(channel_ids)

    def search_trending(self, base_query: str = "2ch まとめ お金") -> list[dict]:
        """
        トレンドトピックを検索

        Args:
            base_query: 基本検索クエリ

        Returns:
            トレンド分析結果
        """
        if not self.youtube_api_key:
            logger.warning("YouTube API キーが設定されていません")
            return []

        self._ensure_youtube_data()

        logger.info(f"トレンド検索中: {base_query}")

        return self.youtube_data.search_trending_topics(
            base_query=base_query,
            variations=self.SEARCH_VARIATIONS,
            max_results_per_query=10,
        )

    def analyze_my_channel(self) -> dict | None:
        """
        自チャンネルを分析

        Returns:
            分析結果
        """
        if not Path(self.client_secrets_file).exists():
            logger.warning(f"クライアントシークレットが見つかりません: {self.client_secrets_file}")
            return None

        self._ensure_youtube_analytics()

        logger.info("自チャンネル分析中...")

        try:
            return self.youtube_analytics.analyze_performance(top_n=15)
        except Exception as e:
            logger.error(f"自チャンネル分析エラー: {e}")
            return None

    def get_past_themes(self, days: int = 30) -> list[str]:
        """
        スプレッドシートから過去N日間のテーマを取得

        Args:
            days: 遡る日数（デフォルト30日）

        Returns:
            テーマ文字列のリスト
        """
        if not self.spreadsheet_id:
            return []

        try:
            auth = GoogleAuth(self.client_secrets_file, ROOT_DIR)
            sheets = SheetsClient(self.spreadsheet_id, auth=auth)
            from video_tracker import DEFAULT_SHEET_NAME
            values = sheets.get_values(f"{DEFAULT_SHEET_NAME}!A:B")

            if len(values) <= 1:
                return []

            cutoff = datetime.now() - timedelta(days=days)
            past_themes = []

            for row in values[1:]:  # ヘッダー行をスキップ
                if len(row) < 2:
                    continue
                try:
                    row_date = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                    if row_date >= cutoff:
                        past_themes.append(row[1])
                except (ValueError, IndexError):
                    continue

            logger.info(f"過去{days}日間のテーマ: {len(past_themes)}件")
            return past_themes

        except Exception as e:
            logger.warning(f"過去テーマ取得エラー（続行）: {e}")
            return []

    @staticmethod
    def _is_similar(theme1: str, theme2: str, threshold: float = 0.6) -> bool:
        """
        2つのテーマが類似しているか判定（2-gram重複率ベース）

        Args:
            theme1: テーマ1
            theme2: テーマ2
            threshold: 類似と判定する重複率の閾値

        Returns:
            類似している場合True
        """
        if len(theme1) < 2 or len(theme2) < 2:
            return False
        set1 = set(theme1[i:i + 2] for i in range(len(theme1) - 1))
        set2 = set(theme2[i:i + 2] for i in range(len(theme2) - 1))
        overlap = len(set1 & set2) / min(len(set1), len(set2))
        return overlap >= threshold

    def generate_themes_with_llm(
        self,
        competitor_data: dict | None = None,
        my_channel_data: dict | None = None,
        trending_data: list[dict] | None = None,
        past_themes: list[str] | None = None,
        count: int = 10,
    ) -> list[str]:
        """
        LLM（Gemini）でテーマを生成

        Args:
            competitor_data: 競合分析データ
            my_channel_data: 自チャンネル分析データ
            trending_data: トレンドデータ
            past_themes: 過去に使用したテーマ（重複排除用）
            count: 生成するテーマ数

        Returns:
            テーマのリスト
        """
        # コンテキストを構築
        context_parts = []

        if competitor_data:
            top_titles = [v["title"] for v in competitor_data.get("top_videos", [])[:10]]
            context_parts.append(f"【競合の人気動画タイトル】\n" + "\n".join(top_titles))

            common_tags = [t["tag"] for t in competitor_data.get("common_tags", [])[:10]]
            context_parts.append(f"【よく使われるタグ】\n" + ", ".join(common_tags))

        if my_channel_data:
            my_top = [v["title"] for v in my_channel_data.get("top_videos", [])[:5]]
            context_parts.append(f"【自チャンネルの人気動画】\n" + "\n".join(my_top))

        if trending_data:
            trend_titles = []
            for t in trending_data[:5]:
                trend_titles.append(f"- {t['query']}: {t['top_video']['title']}")
            context_parts.append(f"【トレンド検索結果】\n" + "\n".join(trend_titles))

        # 過去テーマを除外リストとして追加
        if past_themes:
            context_parts.append(
                "【過去30日以内に使用済みのテーマ（これらと似た内容は避けること）】\n"
                + "\n".join(past_themes)
            )

        context = "\n\n".join(context_parts) if context_parts else "データなし"

        prompt = f"""あなたは2ch/5chまとめ系YouTubeチャンネルの企画担当です。
以下のデータを参考に、「お金・資産形成」に関する動画テーマを{count}個提案してください。

{context}

# 条件
- 視聴者が思わずクリックしたくなるようなテーマ
- 2chスレ風のタイトル（「〜した結果www」「〜なんだが」等）
- 極端で感情を揺さぶる内容（大成功/大失敗、金持ち/貧乏）
- 30代〜40代のサラリーマンが共感できるテーマ
- 過去に使用済みのテーマとは異なる切り口・内容にすること

# 出力形式
テーマを1行1個で出力してください。番号や記号は不要です。

例:
30代で貯金1000万達成したから方法教えるわ
株で全財産溶かした俺の末路www
年収300万でFIRE目指してる奴いる？
"""

        logger.info("Gemini APIでテーマ生成中...")

        model = genai.GenerativeModel("gemini-2.0-flash")

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.9,
                max_output_tokens=1000,
            ),
        )

        content = response.text.strip()
        themes = [line.strip() for line in content.split("\n") if line.strip()]

        logger.info(f"テーマ生成完了: {len(themes)}個")

        return themes

    def suggest_themes(
        self,
        use_competitor_analysis: bool = True,
        use_my_channel: bool = True,
        use_trending: bool = True,
        count: int = 10,
    ) -> list[str]:
        """
        テーマを提案（メイン関数）

        過去30日以内に使用したテーマとの重複を排除する。

        Args:
            use_competitor_analysis: 競合分析を使用するか
            use_my_channel: 自チャンネル分析を使用するか
            use_trending: トレンド検索を使用するか
            count: 生成するテーマ数

        Returns:
            提案テーマのリスト
        """
        competitor_data = None
        my_channel_data = None
        trending_data = None

        if use_competitor_analysis:
            competitor_data = self.analyze_competitors()

        if use_my_channel:
            my_channel_data = self.analyze_my_channel()

        if use_trending:
            trending_data = self.search_trending()

        # 過去テーマを取得（重複排除用）
        past_themes = self.get_past_themes(days=30)

        # 多めに生成して重複を除外できるようにする
        generate_count = count + len(past_themes) if past_themes else count

        themes = self.generate_themes_with_llm(
            competitor_data=competitor_data,
            my_channel_data=my_channel_data,
            trending_data=trending_data,
            past_themes=past_themes,
            count=generate_count,
        )

        # 過去テーマとの類似度フィルタ
        if past_themes:
            filtered = []
            for theme in themes:
                if not any(self._is_similar(theme, past) for past in past_themes):
                    filtered.append(theme)
                else:
                    logger.info(f"  除外（類似テーマあり）: {theme}")

            if filtered:
                themes = filtered
                logger.info(f"重複排除後: {len(themes)}個")
            else:
                logger.warning("全テーマが類似判定。フィルタなしで返却")

        return themes[:count]


def main():
    """CLI実行用"""
    import os

    youtube_api_key = os.getenv("YOUTUBE_API_KEY")

    suggester = ThemeSuggester(
        youtube_api_key=youtube_api_key,
    )

    print("=" * 60)
    print("  テーマ提案システム")
    print("=" * 60)

    # テーマ生成
    themes = suggester.suggest_themes(
        use_competitor_analysis=bool(youtube_api_key),
        use_my_channel=True,
        use_trending=bool(youtube_api_key),
        count=10,
    )

    print("\n【提案テーマ】")
    for i, theme in enumerate(themes, 1):
        print(f"  {i}. {theme}")

    # 結果を保存
    output_path = ROOT_DIR / "generated" / "suggested_themes.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"themes": themes}, f, ensure_ascii=False, indent=2)

    print(f"\n保存先: {output_path}")


if __name__ == "__main__":
    main()
