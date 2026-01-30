"""
YouTube アップロードモジュール
台本JSONから動画メタデータを生成し、YouTubeに予約投稿する
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Skills を使えるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Skills.google import YouTubeUploadClient, GoogleAuth

from config import (
    ROOT_DIR,
    GENERATED_DIR,
    SCRIPTS_DIR,
    YOUTUBE_CATEGORY_ID,
    YOUTUBE_DEFAULT_TAGS,
    YOUTUBE_PUBLISH_HOUR_JST,
    GOOGLE_CLIENT_SECRETS_FILE,
)
from logger import logger


# JST タイムゾーン
JST = timezone(timedelta(hours=9))


def _load_script_data(script_path: Path) -> dict:
    """台本JSONを読み込む"""
    with open(script_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_video_title(script_data: dict) -> str:
    """
    台本データからYouTubeタイトルを生成

    Args:
        script_data: 台本JSONデータ

    Returns:
        動画タイトル（最大100文字）
    """
    theme = script_data.get("theme", "2chまとめ")

    # テーマをそのままタイトルに使用（2ch風）
    title = f"【2ch】{theme}【ゆっくり】"

    # 100文字以内に収める
    if len(title) > 100:
        title = title[:97] + "..."

    return title


def generate_video_description(script_data: dict) -> str:
    """
    台本データからYouTube説明文を生成

    Args:
        script_data: 台本JSONデータ

    Returns:
        動画説明文
    """
    theme = script_data.get("theme", "")

    lines = [
        f"▼ テーマ: {theme}",
        "",
        "2ch/5chの名スレをまとめた動画です。",
        "面白いと思ったらチャンネル登録・高評価お願いします！",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "#2ch #2chまとめ #5ch #ゆっくり #名スレ",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "※この動画は2ch/5chのスレッドを元に再構成したものです。",
        "※登場人物は架空であり、実在の人物・団体とは関係ありません。",
    ]

    return "\n".join(lines)


def generate_tags(script_data: dict) -> list[str]:
    """
    台本データからタグを生成

    Args:
        script_data: 台本JSONデータ

    Returns:
        タグのリスト
    """
    tags = list(YOUTUBE_DEFAULT_TAGS)

    # テーマからキーワードを追加
    theme = script_data.get("theme", "")
    if theme:
        tags.append(theme)

    return tags


def get_next_publish_time(hour_jst: int = None) -> datetime:
    """
    次の予約投稿時刻を取得（JST → UTC変換済み）

    Args:
        hour_jst: 公開時刻（JST、時）。省略時はconfig値を使用

    Returns:
        公開日時（UTC）
    """
    if hour_jst is None:
        hour_jst = YOUTUBE_PUBLISH_HOUR_JST

    now_jst = datetime.now(JST)

    # 当日の指定時刻
    publish_jst = now_jst.replace(
        hour=hour_jst, minute=0, second=0, microsecond=0
    )

    # 既に過ぎている場合は翌日
    if publish_jst <= now_jst + timedelta(minutes=15):
        publish_jst += timedelta(days=1)

    # UTCに変換
    return publish_jst.astimezone(timezone.utc)


def upload_to_youtube(
    video_path: Path,
    script_path: Path | None = None,
    publish_at: datetime | None = None,
    scheduled: bool = True,
    thumbnail_path: Path | None = None,
    client_secrets_file: str | None = None,
) -> dict[str, Any]:
    """
    動画をYouTubeにアップロード

    Args:
        video_path: 動画ファイルのパス
        script_path: 台本JSONファイルのパス（メタデータ生成用）
        publish_at: 予約投稿日時（省略時は当日18:00 JST）
        scheduled: 予約投稿するか（Falseで即時公開）
        thumbnail_path: サムネイル画像のパス
        client_secrets_file: OAuthクライアントシークレット

    Returns:
        {"video_id": str, "url": str, "status": str}
    """
    # 台本データを読み込み
    if script_path is None:
        script_path = SCRIPTS_DIR / "script.json"

    if script_path.exists():
        script_data = _load_script_data(script_path)
    else:
        logger.warning(f"台本ファイルが見つかりません: {script_path}")
        script_data = {"theme": "2chまとめ"}

    # メタデータ生成
    title = generate_video_title(script_data)
    description = generate_video_description(script_data)
    tags = generate_tags(script_data)

    logger.info(f"タイトル: {title}")
    logger.info(f"タグ: {', '.join(tags[:5])}...")

    # 予約投稿時刻
    if scheduled and publish_at is None:
        publish_at = get_next_publish_time()
        publish_jst = publish_at.astimezone(JST)
        logger.info(f"予約投稿: {publish_jst.strftime('%Y/%m/%d %H:%M')} JST")
    elif not scheduled:
        publish_at = None

    # YouTubeクライアント初期化
    secrets_file = client_secrets_file or str(GOOGLE_CLIENT_SECRETS_FILE)
    auth = GoogleAuth(secrets_file, ROOT_DIR)
    client = YouTubeUploadClient(auth=auth)

    # アップロード実行
    result = client.upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        category_id=YOUTUBE_CATEGORY_ID,
        publish_at=publish_at,
        thumbnail_path=thumbnail_path,
    )

    logger.info(f"YouTube URL: {result['url']}")
    logger.info(f"ステータス: {result['status']}")

    return result
