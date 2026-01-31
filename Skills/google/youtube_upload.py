"""
YouTube アップロードクライアント
動画のアップロード・予約投稿・サムネイル設定
"""

import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from .auth import GoogleAuth

logger = logging.getLogger(__name__)


class YouTubeUploadClient:
    """YouTube 動画アップロードクライアント"""

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.force-ssl",
    ]

    def __init__(
        self,
        auth: GoogleAuth | None = None,
        client_secrets_file: str | None = None,
    ):
        """
        Args:
            auth: GoogleAuth インスタンス（省略時は自動作成）
            client_secrets_file: クライアントシークレットファイル（OAuth用）
        """
        self.auth = auth
        self.client_secrets_file = client_secrets_file
        self.service = None

    def _ensure_service(self):
        """YouTube APIサービスを初期化（遅延初期化）"""
        if self.service:
            return

        # GitHub Actions環境: 環境変数からリフレッシュトークンで認証
        yt_client_id = os.environ.get("YT_CLIENT_ID")
        yt_client_secret = os.environ.get("YT_CLIENT_SECRET")
        yt_refresh_token = os.environ.get("YT_REFRESH_TOKEN")

        if yt_client_id and yt_client_secret and yt_refresh_token:
            logger.info("GitHub Actions環境: 環境変数から認証")
            credentials = Credentials(
                None,
                refresh_token=yt_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=yt_client_id,
                client_secret=yt_client_secret,
                scopes=self.SCOPES,
            )
            credentials.refresh(Request())
            self.service = build("youtube", "v3", credentials=credentials)
            return

        # ローカル環境: GoogleAuth で認証
        if self.auth:
            credentials = self.auth.get_credentials(
                self.SCOPES, "youtube_upload_token.json"
            )
        elif self.client_secrets_file:
            self.auth = GoogleAuth(self.client_secrets_file)
            credentials = self.auth.get_credentials(
                self.SCOPES, "youtube_upload_token.json"
            )
        else:
            raise ValueError(
                "認証情報が必要です。auth, client_secrets_file, "
                "または環境変数（YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN）を設定してください。"
            )

        self.service = build("youtube", "v3", credentials=credentials)

    def upload_video(
        self,
        video_path: Path | str,
        title: str,
        description: str,
        tags: list[str] | None = None,
        category_id: str = "22",
        publish_at: datetime | None = None,
        thumbnail_path: Path | str | None = None,
        made_for_kids: bool = False,
    ) -> dict[str, Any]:
        """
        動画をYouTubeにアップロード

        Args:
            video_path: 動画ファイルのパス
            title: 動画タイトル
            description: 動画説明文
            tags: タグのリスト
            category_id: YouTube カテゴリID（22=People & Blogs）
            publish_at: 予約投稿日時（datetime, UTC推奨）
            thumbnail_path: カスタムサムネイルのパス
            made_for_kids: 子供向けコンテンツか

        Returns:
            {"video_id": str, "url": str, "status": str}
        """
        self._ensure_service()

        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

        file_size = video_path.stat().st_size
        logger.info(f"アップロード開始: '{title}' ({file_size:,} bytes)")

        # リクエストボディ
        body: dict[str, Any] = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": {
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }

        # 予約投稿の設定
        if publish_at:
            # UTCに変換
            if publish_at.tzinfo is None:
                publish_at_utc = publish_at.replace(tzinfo=timezone.utc)
            else:
                publish_at_utc = publish_at.astimezone(timezone.utc)

            # 最低15分先であることを確認
            now_utc = datetime.now(timezone.utc)
            time_diff = (publish_at_utc - now_utc).total_seconds()
            if time_diff < 15 * 60:
                logger.warning(
                    f"予約時刻が近すぎます（{time_diff / 60:.1f}分後）。即時公開に変更します。"
                )
                body["status"]["privacyStatus"] = "public"
            else:
                # RFC 3339 フォーマット
                publish_at_iso = publish_at_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                body["status"]["privacyStatus"] = "private"
                body["status"]["publishAt"] = publish_at_iso
                logger.info(f"予約投稿設定: {publish_at_iso} ({time_diff / 3600:.1f}時間後)")
        else:
            body["status"]["privacyStatus"] = "public"

        # レジューマブルアップロード
        media = MediaFileUpload(
            str(video_path),
            chunksize=-1,
            resumable=True,
            mimetype="video/mp4",
        )

        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        # チャンクアップロード（リトライ付き）
        response = None
        retry_count = 0
        max_retries = 3

        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    if progress % 10 == 0:
                        logger.info(f"アップロード進捗: {progress}%")
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    raise RuntimeError(f"アップロード失敗（{max_retries}回リトライ後）: {e}")
                logger.warning(f"アップロード一時エラー（リトライ {retry_count}/{max_retries}）: {e}")
                time.sleep(5 * retry_count)

        video_id = response["id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        logger.info(f"アップロード完了: {video_url}")

        # サムネイルアップロード
        if thumbnail_path:
            self.upload_thumbnail(video_id, thumbnail_path)

        status_text = "予約投稿" if publish_at and "publishAt" in body["status"] else "公開"
        return {
            "video_id": video_id,
            "url": video_url,
            "status": status_text,
        }

    def upload_thumbnail(
        self,
        video_id: str,
        thumbnail_path: Path | str,
    ) -> bool:
        """
        カスタムサムネイルをアップロード

        Args:
            video_id: 動画ID
            thumbnail_path: サムネイル画像のパス

        Returns:
            成功したか
        """
        self._ensure_service()

        thumbnail_path = Path(thumbnail_path)
        if not thumbnail_path.exists():
            logger.warning(f"サムネイルが見つかりません: {thumbnail_path}")
            return False

        try:
            media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
            self.service.thumbnails().set(
                videoId=video_id, media_body=media
            ).execute()
            logger.info(f"サムネイルアップロード完了: {video_id}")
            return True
        except Exception as e:
            logger.error(f"サムネイルアップロードエラー: {e}")
            return False
