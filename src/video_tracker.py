"""
動画記録・追跡モジュール
生成した動画をスプレッドシートに記録し、再生数を定期取得
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Skills を使えるようにパスを追加（リポジトリ内 → 共有フォルダの順で探索）
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(1, str(Path(__file__).parent.parent.parent))

from Skills.google import SheetsClient, DriveClient, YouTubeDataClient, GoogleAuth

from config import ROOT_DIR, GENERATED_DIR, GOOGLE_SERVICE_ACCOUNT
from logger import logger


DEFAULT_SHEET_NAME = "生成ログ"

SHEET_HEADERS = [
    "生成日時", "テーマ", "動画尺", "総生成時間",
    "ファイル", "YouTube", "再生数", "いいね", "コメント", "Drive",
    "Gemini tokens", "Gemini ¥", "KieAI cr",
    "シーン数", "画像数", "台本(s)", "画像(s)", "音声(s)",
]


class VideoTracker:
    """動画記録・追跡クラス"""

    def __init__(
        self,
        spreadsheet_id: str,
        drive_folder_id: str | None = None,
        youtube_api_key: str | None = None,
        client_secrets_file: str | None = None,
        service_account_file: str | None = None,
    ):
        """
        Args:
            spreadsheet_id: 記録用スプレッドシートID
            drive_folder_id: 動画保存先DriveフォルダID
            youtube_api_key: YouTube API キー（再生数取得用）
            client_secrets_file: OAuthクライアントシークレット
            service_account_file: サービスアカウントJSONファイル（優先使用）
        """
        self.spreadsheet_id = spreadsheet_id
        self.drive_folder_id = drive_folder_id
        self.youtube_api_key = youtube_api_key
        self.client_secrets_file = client_secrets_file
        # サービスアカウントを優先使用
        self.service_account_file = service_account_file or GOOGLE_SERVICE_ACCOUNT

        self.sheets: SheetsClient | None = None
        self.drive: DriveClient | None = None
        self.youtube: YouTubeDataClient | None = None

    def _ensure_sheets(self):
        """Sheetsクライアントを初期化"""
        if not self.sheets:
            if self.service_account_file:
                self.sheets = SheetsClient(
                    self.spreadsheet_id,
                    service_account_file=self.service_account_file
                )
            elif self.client_secrets_file:
                auth = GoogleAuth(self.client_secrets_file, ROOT_DIR)
                self.sheets = SheetsClient(self.spreadsheet_id, auth=auth)
            else:
                raise RuntimeError(
                    "Sheets初期化に必要な認証情報がありません"
                    "（service_account または client_secrets が必要）"
                )

    def _ensure_drive(self):
        """Driveクライアントを初期化"""
        if not self.drive:
            if self.service_account_file:
                self.drive = DriveClient(
                    self.drive_folder_id,
                    service_account_file=self.service_account_file
                )
            elif self.client_secrets_file:
                auth = GoogleAuth(self.client_secrets_file, ROOT_DIR)
                self.drive = DriveClient(self.drive_folder_id, auth=auth)
            else:
                raise RuntimeError(
                    "Drive初期化に必要な認証情報がありません"
                    "（service_account または client_secrets が必要）"
                )

    def _ensure_youtube(self):
        """YouTubeクライアントを初期化"""
        if not self.youtube and self.youtube_api_key:
            self.youtube = YouTubeDataClient(api_key=self.youtube_api_key)

    def _ensure_sheet_exists(self, sheet_name: str) -> None:
        """シートが存在しない場合は作成してヘッダーを追加"""
        self._ensure_sheets()
        service = self.sheets.service

        # スプレッドシートのメタデータを取得
        metadata = service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id,
            fields="sheets.properties.title",
        ).execute()

        existing_names = [
            s["properties"]["title"] for s in metadata.get("sheets", [])
        ]

        if sheet_name in existing_names:
            return

        # シートを新規作成
        logger.info(f"シート '{sheet_name}' を作成中...")
        service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={
                "requests": [
                    {"addSheet": {"properties": {"title": sheet_name}}}
                ]
            },
        ).execute()

        # ヘッダー行を追加
        self.sheets.append_row(SHEET_HEADERS, sheet_name)
        logger.info(f"シート '{sheet_name}' を作成しヘッダーを追加しました")

    def record_video(
        self,
        theme: str,
        video_path: Path,
        video_duration: float,
        generation_time: float,
        youtube_url: str | None = None,
        upload_to_drive: bool = True,
        sheet_name: str = DEFAULT_SHEET_NAME,
        gemini_tokens: int = 0,
        gemini_cost_jpy: float = 0,
        kieai_credits: int = 0,
        scene_count: int = 0,
        image_count: int = 0,
        step_times: dict | None = None,
    ) -> dict[str, Any]:
        """
        生成した動画を記録

        Args:
            theme: 動画テーマ
            video_path: 動画ファイルパス
            video_duration: 動画の長さ（秒）
            generation_time: 生成にかかった時間（秒）
            youtube_url: YouTubeにアップロード済みの場合のURL
            upload_to_drive: Driveにアップロードするか
            sheet_name: 記録先シート名
            gemini_tokens: Gemini API合計トークン数
            gemini_cost_jpy: Gemini推定コスト（円）
            kieai_credits: KieAIクレジット消費数
            scene_count: 台本のシーン数
            image_count: 生成した画像枚数
            step_times: ステップ別所要時間 {"script": float, "image": float, "voice": float}

        Returns:
            記録結果
        """
        if step_times is None:
            step_times = {}

        result = {
            "theme": theme,
            "video_path": str(video_path),
            "drive_url": None,
            "youtube_url": youtube_url,
            "recorded_at": datetime.now().isoformat(),
        }

        # Driveにアップロード
        if upload_to_drive and self.drive_folder_id:
            self._ensure_drive()

            try:
                logger.info(f"Google Driveにアップロード中: {video_path.name}")
                upload_result = self.drive.upload_file(video_path)
                result["drive_url"] = upload_result["url"]
                logger.info(f"アップロード完了: {result['drive_url']}")
            except Exception as e:
                logger.error(f"Driveアップロードエラー: {e}")

        # スプレッドシートに記録
        self._ensure_sheets()

        try:
            self._ensure_sheet_exists(sheet_name)
            # 時間を分:秒形式に変換
            duration_min = int(video_duration // 60)
            duration_sec = int(video_duration % 60)
            gen_min = int(generation_time // 60)
            gen_sec = int(generation_time % 60)

            row_data = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                theme,
                f"{duration_min}:{duration_sec:02d}",
                f"{gen_min}:{gen_sec:02d}",
                str(video_path),
                youtube_url or "",
                "",  # 視聴回数（後で更新）
                "",  # いいね数（後で更新）
                "",  # コメント数（後で更新）
                result["drive_url"] or "",
                gemini_tokens or "",
                f"{gemini_cost_jpy:.2f}" if gemini_cost_jpy else "",
                kieai_credits or "",
                scene_count or "",
                image_count or "",
                int(step_times.get("script", 0)) or "",
                int(step_times.get("image", 0)) or "",
                int(step_times.get("voice", 0)) or "",
            ]

            self.sheets.append_row(row_data, sheet_name)
            logger.info("スプレッドシートに記録しました")

        except Exception as e:
            logger.error(f"スプレッドシート記録エラー: {e}")

        return result

    def update_video_stats(
        self,
        sheet_name: str = DEFAULT_SHEET_NAME,
        youtube_url_column: int = 5,  # F列（0始まり）
        views_column: int = 6,  # G列
        likes_column: int = 7,  # H列
        comments_column: int = 8,  # I列
    ) -> int:
        """
        記録済み動画の統計を更新

        Args:
            sheet_name: シート名
            youtube_url_column: YouTube URL列のインデックス
            views_column: 再生数列のインデックス
            likes_column: いいね数列のインデックス
            comments_column: コメント数列のインデックス

        Returns:
            更新した動画数
        """
        if not self.youtube_api_key:
            logger.warning("YouTube API キーが設定されていないため統計を更新できません")
            return 0

        self._ensure_sheets()
        self._ensure_youtube()

        logger.info("動画統計を更新中...")

        # 全行を取得
        values = self.sheets.get_values(f"{sheet_name}!A:R")

        if len(values) <= 1:
            logger.info("更新する動画がありません")
            return 0

        updates = []
        updated_count = 0

        for row_idx, row in enumerate(values[1:], start=2):  # 2行目から（1はヘッダー）
            if len(row) <= youtube_url_column:
                continue

            youtube_url = row[youtube_url_column] if len(row) > youtube_url_column else ""

            if not youtube_url or "youtube.com" not in youtube_url:
                continue

            # 動画IDを抽出
            video_id = None
            if "v=" in youtube_url:
                video_id = youtube_url.split("v=")[1].split("&")[0]
            elif "youtu.be/" in youtube_url:
                video_id = youtube_url.split("youtu.be/")[1].split("?")[0]

            if not video_id:
                continue

            # 統計を取得
            try:
                videos = self.youtube.get_videos_by_ids([video_id])
                if videos:
                    video = videos[0]

                    # 更新データを追加
                    col_letter_views = chr(ord("A") + views_column)
                    col_letter_likes = chr(ord("A") + likes_column)
                    col_letter_comments = chr(ord("A") + comments_column)

                    updates.append(
                        {
                            "range": f"{sheet_name}!{col_letter_views}{row_idx}",
                            "values": [[video.view_count]],
                        }
                    )
                    updates.append(
                        {
                            "range": f"{sheet_name}!{col_letter_likes}{row_idx}",
                            "values": [[video.like_count]],
                        }
                    )
                    updates.append(
                        {
                            "range": f"{sheet_name}!{col_letter_comments}{row_idx}",
                            "values": [[video.comment_count]],
                        }
                    )

                    updated_count += 1
                    logger.info(f"  {video.title[:30]}... - 再生数: {video.view_count:,}")

            except Exception as e:
                logger.warning(f"動画 {video_id} の統計取得エラー: {e}")

        # バッチ更新
        if updates:
            self.sheets.batch_update(updates)
            logger.info(f"統計更新完了: {updated_count}件")

        return updated_count

    def get_performance_report(
        self,
        sheet_name: str = DEFAULT_SHEET_NAME,
    ) -> dict[str, Any]:
        """
        パフォーマンスレポートを生成

        Args:
            sheet_name: シート名

        Returns:
            レポートデータ
        """
        self._ensure_sheets()

        values = self.sheets.get_values(f"{sheet_name}!A:R")

        if len(values) <= 1:
            return {"total_videos": 0}

        total_videos = len(values) - 1
        total_views = 0
        total_duration = 0
        videos_with_stats = 0

        for row in values[1:]:
            # 動画時間を加算
            if len(row) > 2 and row[2]:
                try:
                    parts = row[2].split(":")
                    if len(parts) == 2:
                        total_duration += int(parts[0]) * 60 + int(parts[1])
                except Exception:
                    pass

            # 再生数を加算
            if len(row) > 6 and row[6]:
                try:
                    total_views += int(row[6])
                    videos_with_stats += 1
                except Exception:
                    pass

        avg_views = total_views / videos_with_stats if videos_with_stats > 0 else 0

        return {
            "total_videos": total_videos,
            "total_duration_seconds": total_duration,
            "total_duration_formatted": f"{total_duration // 60}分{total_duration % 60}秒",
            "total_views": total_views,
            "avg_views_per_video": round(avg_views, 0),
            "videos_with_stats": videos_with_stats,
        }


def main():
    """CLI実行用"""
    import os

    spreadsheet_id = os.getenv("GOOGLE_SHEETS_ID")
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")

    if not spreadsheet_id:
        print("エラー: GOOGLE_SHEETS_ID を設定してください")
        return

    tracker = VideoTracker(
        spreadsheet_id=spreadsheet_id,
        youtube_api_key=youtube_api_key,
    )

    print("=" * 60)
    print("  動画追跡システム")
    print("=" * 60)

    # 統計更新
    if youtube_api_key:
        print("\n動画統計を更新中...")
        updated = tracker.update_video_stats()
        print(f"更新完了: {updated}件")

    # レポート表示
    print("\n【パフォーマンスレポート】")
    report = tracker.get_performance_report()

    print(f"  総動画数: {report['total_videos']}")
    print(f"  総再生時間: {report['total_duration_formatted']}")
    print(f"  総再生回数: {report['total_views']:,}")
    print(f"  平均再生回数: {report['avg_views_per_video']:,.0f}")


if __name__ == "__main__":
    main()
