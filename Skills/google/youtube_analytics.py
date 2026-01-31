"""
YouTube Analytics クライアント
自チャンネルの詳細分析（OAuth必須）
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from googleapiclient.discovery import build

from .auth import GoogleAuth
from .youtube_data import VideoInfo, YouTubeDataClient


@dataclass
class ChannelAnalytics:
    """チャンネル分析結果"""

    channel_id: str
    channel_title: str
    subscriber_count: int
    total_views: int
    video_count: int
    videos: list[VideoInfo]

    @property
    def avg_views_per_video(self) -> float:
        if self.video_count == 0:
            return 0.0
        return self.total_views / self.video_count

    def get_top_videos(self, limit: int = 10) -> list[VideoInfo]:
        """再生数上位の動画を取得"""
        return sorted(self.videos, key=lambda v: v.view_count, reverse=True)[:limit]

    def get_recent_videos(self, limit: int = 10) -> list[VideoInfo]:
        """最新の動画を取得"""
        return sorted(self.videos, key=lambda v: v.published_at, reverse=True)[:limit]


class YouTubeAnalyticsClient:
    """
    自チャンネル分析用クライアント（OAuth必須）

    YouTube Data APIを使って自チャンネルの動画統計を取得・分析
    """

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
    ]

    def __init__(
        self,
        auth: GoogleAuth | None = None,
        client_secrets_file: str = "client_secrets.json",
    ):
        """
        Args:
            auth: GoogleAuth インスタンス
            client_secrets_file: クライアントシークレットファイル
        """
        self.auth = auth or GoogleAuth(client_secrets_file)
        self.youtube_service = None
        self.data_client: YouTubeDataClient | None = None

    def _ensure_service(self):
        """サービスを初期化"""
        if not self.youtube_service:
            credentials = self.auth.get_credentials(self.SCOPES, "youtube_analytics_token.json")
            self.youtube_service = build("youtube", "v3", credentials=credentials)
            # Data APIクライアントも初期化（OAuth認証済み）
            self.data_client = YouTubeDataClient(auth=self.auth)
            self.data_client.service = self.youtube_service

    def get_my_channel_id(self) -> str:
        """自分のチャンネルIDを取得"""
        self._ensure_service()

        response = (
            self.youtube_service.channels().list(part="id,snippet", mine=True).execute()
        )

        if not response.get("items"):
            raise RuntimeError("認証ユーザーのチャンネルが見つかりません")

        return response["items"][0]["id"]

    def get_channel_analytics(
        self,
        max_videos: int = 50,
    ) -> ChannelAnalytics:
        """
        自チャンネルの分析データを取得

        Args:
            max_videos: 取得する動画の最大数

        Returns:
            ChannelAnalytics
        """
        self._ensure_service()

        channel_id = self.get_my_channel_id()

        # チャンネル情報取得
        channel_response = (
            self.youtube_service.channels()
            .list(part="snippet,statistics", id=channel_id)
            .execute()
        )

        channel_data = channel_response["items"][0]
        snippet = channel_data["snippet"]
        stats = channel_data["statistics"]

        # 動画一覧取得
        videos = self.data_client.get_channel_videos(channel_id, max_videos)

        return ChannelAnalytics(
            channel_id=channel_id,
            channel_title=snippet["title"],
            subscriber_count=int(stats.get("subscriberCount", 0)),
            total_views=int(stats.get("viewCount", 0)),
            video_count=int(stats.get("videoCount", 0)),
            videos=videos,
        )

    def analyze_performance(
        self,
        top_n: int = 10,
    ) -> dict[str, Any]:
        """
        パフォーマンス分析を実行

        Args:
            top_n: 上位動画の数

        Returns:
            分析結果
        """
        analytics = self.get_channel_analytics(max_videos=100)
        top_videos = analytics.get_top_videos(top_n)

        # 統計計算
        if top_videos:
            avg_views = sum(v.view_count for v in top_videos) / len(top_videos)
            avg_likes = sum(v.like_count for v in top_videos) / len(top_videos)
            avg_engagement = sum(v.engagement_rate for v in top_videos) / len(top_videos)
        else:
            avg_views = avg_likes = avg_engagement = 0

        # タグ集計
        tag_counts: dict[str, int] = {}
        for video in top_videos:
            for tag in video.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        common_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:15]

        # タイトルキーワード（上位動画のタイトル）
        title_samples = [v.title for v in top_videos]

        return {
            "channel": {
                "id": analytics.channel_id,
                "title": analytics.channel_title,
                "subscribers": analytics.subscriber_count,
                "total_views": analytics.total_views,
                "video_count": analytics.video_count,
                "avg_views_per_video": analytics.avg_views_per_video,
            },
            "top_videos": [
                {
                    "title": v.title,
                    "views": v.view_count,
                    "likes": v.like_count,
                    "engagement_rate": round(v.engagement_rate, 2),
                    "url": v.url,
                    "published": v.published_at.isoformat(),
                }
                for v in top_videos
            ],
            "statistics": {
                "avg_views_top_n": round(avg_views, 0),
                "avg_likes_top_n": round(avg_likes, 0),
                "avg_engagement_rate": round(avg_engagement, 2),
            },
            "common_tags": [{"tag": tag, "count": count} for tag, count in common_tags],
            "title_samples": title_samples,
        }

    def get_video_stats_by_url(self, video_url: str) -> VideoInfo | None:
        """
        動画URLから統計を取得

        Args:
            video_url: YouTube動画URL

        Returns:
            VideoInfo または None
        """
        # URLからIDを抽出
        video_id = None
        if "v=" in video_url:
            video_id = video_url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[1].split("?")[0]

        if not video_id:
            return None

        self._ensure_service()
        videos = self.data_client.get_videos_by_ids([video_id])

        return videos[0] if videos else None

    def suggest_themes_from_performance(
        self,
        top_n: int = 10,
    ) -> list[str]:
        """
        パフォーマンスに基づいてテーマを提案

        上位動画のタイトル・タグから傾向を抽出

        Args:
            top_n: 分析する上位動画数

        Returns:
            提案テーマのリスト
        """
        analysis = self.analyze_performance(top_n)

        # タイトルからキーワードを抽出（簡易版）
        keywords = set()
        for title in analysis["title_samples"]:
            # 数字を含む部分を抽出（「100万円」「30代」等）
            import re

            numbers = re.findall(r"\d+[万円歳代%]+", title)
            keywords.update(numbers)

        # 共通タグも追加
        for tag_info in analysis["common_tags"][:5]:
            keywords.add(tag_info["tag"])

        return list(keywords)
