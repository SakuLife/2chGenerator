"""
YouTube Data API v3 クライアント
競合チャンネル分析、動画検索、公開動画の統計取得

※公開データの取得はAPIキーのみでOK（OAuth不要）
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from googleapiclient.discovery import build

from .auth import GoogleAuth


@dataclass
class VideoInfo:
    """動画情報"""

    video_id: str
    title: str
    description: str
    channel_id: str
    channel_title: str
    published_at: datetime
    view_count: int
    like_count: int
    comment_count: int
    duration: str
    tags: list[str]
    thumbnail_url: str

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def engagement_rate(self) -> float:
        """エンゲージメント率（いいね数/再生数）"""
        if self.view_count == 0:
            return 0.0
        return (self.like_count / self.view_count) * 100


@dataclass
class ChannelInfo:
    """チャンネル情報"""

    channel_id: str
    title: str
    description: str
    subscriber_count: int
    view_count: int
    video_count: int
    thumbnail_url: str

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/channel/{self.channel_id}"


class YouTubeDataClient:
    """
    YouTube Data API v3 クライアント

    使い分け:
    - APIキーのみ: 公開動画の検索・統計取得（競合分析）
    - OAuth: 自分の非公開動画情報等
    """

    def __init__(
        self,
        api_key: str | None = None,
        auth: GoogleAuth | None = None,
        client_secrets_file: str = "client_secrets.json",
    ):
        """
        Args:
            api_key: YouTube Data API キー（公開データ取得用）
            auth: GoogleAuth インスタンス（OAuth必要な場合）
            client_secrets_file: クライアントシークレットファイル
        """
        self.api_key = api_key
        self.auth = auth or GoogleAuth(client_secrets_file) if not api_key else None
        self.service = None

    def _ensure_service(self, require_oauth: bool = False):
        """サービスを初期化"""
        if self.service:
            return

        if self.api_key and not require_oauth:
            # APIキーのみで初期化（公開データ用）
            self.service = build("youtube", "v3", developerKey=self.api_key)
        else:
            # OAuth認証
            scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
            credentials = self.auth.get_credentials(scopes, "youtube_token.json")
            self.service = build("youtube", "v3", credentials=credentials)

    def search_videos(
        self,
        query: str,
        max_results: int = 25,
        order: str = "viewCount",
        published_after: datetime | None = None,
        region_code: str = "JP",
    ) -> list[VideoInfo]:
        """
        動画を検索

        Args:
            query: 検索クエリ
            max_results: 最大取得件数
            order: ソート順（viewCount, date, rating, relevance）
            published_after: この日時以降の動画のみ
            region_code: 地域コード

        Returns:
            VideoInfoのリスト
        """
        self._ensure_service()

        search_params = {
            "part": "id,snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results, 50),
            "order": order,
            "regionCode": region_code,
        }

        if published_after:
            search_params["publishedAfter"] = published_after.isoformat() + "Z"

        response = self.service.search().list(**search_params).execute()

        video_ids = [item["id"]["videoId"] for item in response.get("items", [])]

        if not video_ids:
            return []

        return self.get_videos_by_ids(video_ids)

    def get_videos_by_ids(self, video_ids: list[str]) -> list[VideoInfo]:
        """
        動画IDから詳細情報を取得

        Args:
            video_ids: 動画IDのリスト

        Returns:
            VideoInfoのリスト
        """
        self._ensure_service()

        response = (
            self.service.videos()
            .list(
                part="snippet,statistics,contentDetails",
                id=",".join(video_ids[:50]),  # 最大50件
            )
            .execute()
        )

        videos = []
        for item in response.get("items", []):
            snippet = item["snippet"]
            stats = item.get("statistics", {})
            content = item["contentDetails"]

            videos.append(
                VideoInfo(
                    video_id=item["id"],
                    title=snippet["title"],
                    description=snippet["description"],
                    channel_id=snippet["channelId"],
                    channel_title=snippet["channelTitle"],
                    published_at=datetime.fromisoformat(
                        snippet["publishedAt"].replace("Z", "+00:00")
                    ),
                    view_count=int(stats.get("viewCount", 0)),
                    like_count=int(stats.get("likeCount", 0)),
                    comment_count=int(stats.get("commentCount", 0)),
                    duration=content["duration"],
                    tags=snippet.get("tags", []),
                    thumbnail_url=snippet["thumbnails"].get("high", {}).get("url", ""),
                )
            )

        return videos

    def get_channel_videos(
        self,
        channel_id: str,
        max_results: int = 50,
    ) -> list[VideoInfo]:
        """
        チャンネルの動画一覧を取得

        Args:
            channel_id: チャンネルID
            max_results: 最大取得件数

        Returns:
            VideoInfoのリスト
        """
        self._ensure_service()

        videos = []
        next_page_token = None

        while len(videos) < max_results:
            response = (
                self.service.search()
                .list(
                    part="id",
                    channelId=channel_id,
                    type="video",
                    order="date",
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token,
                )
                .execute()
            )

            video_ids = [item["id"]["videoId"] for item in response.get("items", [])]

            if not video_ids:
                break

            videos.extend(self.get_videos_by_ids(video_ids))

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        return videos

    def get_channel_info(self, channel_id: str) -> ChannelInfo:
        """
        チャンネル情報を取得

        Args:
            channel_id: チャンネルID

        Returns:
            ChannelInfo
        """
        self._ensure_service()

        response = (
            self.service.channels()
            .list(part="snippet,statistics", id=channel_id)
            .execute()
        )

        if not response.get("items"):
            raise ValueError(f"チャンネルが見つかりません: {channel_id}")

        item = response["items"][0]
        snippet = item["snippet"]
        stats = item["statistics"]

        return ChannelInfo(
            channel_id=item["id"],
            title=snippet["title"],
            description=snippet["description"],
            subscriber_count=int(stats.get("subscriberCount", 0)),
            view_count=int(stats.get("viewCount", 0)),
            video_count=int(stats.get("videoCount", 0)),
            thumbnail_url=snippet["thumbnails"].get("high", {}).get("url", ""),
        )

    def analyze_competitors(
        self,
        channel_ids: list[str],
        videos_per_channel: int = 20,
    ) -> dict[str, Any]:
        """
        競合チャンネルを分析

        Args:
            channel_ids: 競合チャンネルIDのリスト
            videos_per_channel: チャンネルあたりの動画取得数

        Returns:
            分析結果
        """
        all_videos = []
        channels = []

        for channel_id in channel_ids:
            try:
                channel = self.get_channel_info(channel_id)
                channels.append(channel)

                videos = self.get_channel_videos(channel_id, videos_per_channel)
                all_videos.extend(videos)
            except Exception as e:
                print(f"警告: チャンネル {channel_id} の取得に失敗: {e}")

        # 人気動画（再生数順）
        top_videos = sorted(all_videos, key=lambda v: v.view_count, reverse=True)[:20]

        # タグ集計
        tag_counts: dict[str, int] = {}
        for video in all_videos:
            for tag in video.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        common_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:30]

        # タイトル傾向（キーワード抽出用にタイトル一覧）
        titles = [v.title for v in top_videos]

        return {
            "channels": [
                {
                    "id": c.channel_id,
                    "title": c.title,
                    "subscribers": c.subscriber_count,
                    "total_views": c.view_count,
                    "video_count": c.video_count,
                }
                for c in channels
            ],
            "top_videos": [
                {
                    "title": v.title,
                    "views": v.view_count,
                    "likes": v.like_count,
                    "engagement_rate": v.engagement_rate,
                    "url": v.url,
                    "channel": v.channel_title,
                }
                for v in top_videos
            ],
            "common_tags": [{"tag": tag, "count": count} for tag, count in common_tags],
            "title_samples": titles,
            "total_videos_analyzed": len(all_videos),
        }

    def search_trending_topics(
        self,
        base_query: str,
        variations: list[str] | None = None,
        max_results_per_query: int = 10,
    ) -> list[dict[str, Any]]:
        """
        トレンドトピックを検索

        Args:
            base_query: ベースとなる検索クエリ（例: "2ch まとめ"）
            variations: 追加キーワードのリスト（例: ["貯金", "投資", "FIRE"]）
            max_results_per_query: クエリあたりの取得件数

        Returns:
            トピック分析結果
        """
        variations = variations or []
        queries = [base_query] + [f"{base_query} {v}" for v in variations]

        results = []
        for query in queries:
            videos = self.search_videos(query, max_results_per_query, order="viewCount")

            if videos:
                avg_views = sum(v.view_count for v in videos) / len(videos)
                results.append(
                    {
                        "query": query,
                        "avg_views": avg_views,
                        "top_video": {
                            "title": videos[0].title,
                            "views": videos[0].view_count,
                            "url": videos[0].url,
                        },
                        "sample_titles": [v.title for v in videos[:5]],
                    }
                )

        # 平均再生数でソート
        results.sort(key=lambda x: x["avg_views"], reverse=True)

        return results
