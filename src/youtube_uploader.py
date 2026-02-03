"""
YouTube アップロードモジュール
台本JSONから動画メタデータを生成し、YouTubeに予約投稿する
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Skills を使えるようにパスを追加（リポジトリ内 → 共有フォルダの順で探索）
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(1, str(Path(__file__).parent.parent.parent))

from Skills.google import YouTubeUploadClient, GoogleAuth

from config import (
    ROOT_DIR,
    GENERATED_DIR,
    SCRIPTS_DIR,
    YOUTUBE_CATEGORY_ID,
    YOUTUBE_DEFAULT_TAGS,
    YOUTUBE_PUBLISH_HOURS_JST,
    YOUTUBE_CHANNEL_URL,
    GOOGLE_CLIENT_SECRETS_FILE,
    GOOGLE_SHEETS_ID,
    GOOGLE_SERVICE_ACCOUNT,
)
from logger import logger


# JST タイムゾーン
JST = timezone(timedelta(hours=9))


def _extract_theme(script_path: Path) -> str:
    """台本JSONからテーマを抽出（リスト/辞書両対応）"""
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 辞書形式: {"theme": "...", "scenes": [...]}
        if isinstance(data, dict):
            return data.get("theme", "")

        # リスト形式: [{"role": "narrator", "text": "..."}, ...]
        # 最初のナレーターのテキストからテーマを推測
        if isinstance(data, list) and data:
            for scene in data:
                if scene.get("role") == "title_card":
                    return scene.get("text", "")
    except Exception as e:
        logger.warning(f"台本読み込みエラー: {e}")

    return ""


def generate_video_title(theme: str) -> str:
    """
    テーマからYouTubeタイトルを生成

    形式: {テーマ}【2chお金スレ】
    テーマに既に【衝撃】【悲報】等がある場合はそのまま残す

    Args:
        theme: 動画テーマ

    Returns:
        動画タイトル（最大100文字）
    """
    if not theme:
        theme = "2chまとめ"

    # テーマに既に【2ch...】系タグがあれば末尾タグを省略
    if "【2ch" in theme or "【２ch" in theme:
        title = theme
    else:
        title = f"{theme}【2chお金スレ】"

    # 100文字以内に収める
    if len(title) > 100:
        title = title[:97] + "..."

    return title


def _fetch_related_videos() -> list[dict]:
    """
    スプレッドシートから過去動画を取得し、ランダムに1〜3本を返す
    毎回異なる組み合わせになるよう重複回避
    """
    if not GOOGLE_SHEETS_ID:
        return []

    try:
        from Skills.google import SheetsClient
        import random

        if GOOGLE_SERVICE_ACCOUNT:
            sheets = SheetsClient(
                GOOGLE_SHEETS_ID,
                service_account_file=GOOGLE_SERVICE_ACCOUNT,
            )
        else:
            return []

        # B列(テーマ) 〜 F列(YouTube URL) を取得
        values = sheets.get_values("生成ログ!B:F")
        if not values or len(values) <= 1:
            return []

        # YouTube URLがある動画だけ収集
        all_videos = []
        for row in values[1:]:
            if len(row) >= 5 and row[4] and "youtube.com" in row[4]:
                all_videos.append({
                    "theme": row[0],
                    "url": row[4],
                })

        if not all_videos:
            return []

        # 1〜3本をランダムに選択（重複なし）
        pick_count = min(random.randint(1, 3), len(all_videos))
        return random.sample(all_videos, pick_count)

    except Exception as e:
        logger.warning(f"関連動画取得エラー: {e}")
        return []


def generate_video_description(theme: str) -> str:
    """
    テーマからYouTube説明文を生成
    スプレッドシートから過去動画リンクを取得して関連動画セクションに追加

    Args:
        theme: 動画テーマ

    Returns:
        動画説明文
    """
    lines = [
        "2chお金スレ、投資や貯金、節約など身近な内容を動画にまとめました。",
        "コメントもお待ちしてます",
        "",
    ]

    # スプレッドシートから過去動画リンクを取得
    related = _fetch_related_videos()
    if related:
        lines.append("▼おすすめの関連動画はこちら")
        for video in related:
            title = generate_video_title(video["theme"])
            lines.append(f"{title}")
            lines.append(f"{video['url']}")
        lines.append("")

    lines.extend([
        "▼チャンネル登録はこちら",
        YOUTUBE_CHANNEL_URL,
        "",
        "#2ch #お金 #投資 #新NISA #積立NISA #FIRE",
        "#貯金 #節約 #有益スレ #2ch有益スレ #有益",
        "#2chお金スレ #2chお金 #お金スレ #面白いスレ",
        "#2ch面白いスレ #ゆっくり #2ちゃんねる #ゆっくり解説",
    ])

    return "\n".join(lines)


def generate_tags(theme: str) -> list[str]:
    """
    テーマからタグを生成

    Args:
        theme: 動画テーマ

    Returns:
        タグのリスト
    """
    tags = list(YOUTUBE_DEFAULT_TAGS)

    if theme:
        tags.append(theme)

    return tags


def get_next_publish_time(hour_jst: int | None = None) -> datetime:
    """
    次の予約投稿時刻を取得（JST → UTC変換済み）

    現在時刻に応じて最も近い投稿時刻を自動選択:
    - 午前（0:00〜11:59）→ 6:00 JST
    - 午後（12:00〜23:59）→ 18:00 JST

    Args:
        hour_jst: 公開時刻（JST、時）。省略時は自動選択

    Returns:
        公開日時（UTC）
    """
    now_jst = datetime.now(JST)

    if hour_jst is None:
        # 現在の時間帯に応じて次の投稿時刻を選択
        hours = sorted(YOUTUBE_PUBLISH_HOURS_JST)
        hour_jst = hours[0]  # デフォルトは最初の時刻
        for h in hours:
            candidate = now_jst.replace(
                hour=h, minute=0, second=0, microsecond=0
            )
            if candidate > now_jst + timedelta(minutes=15):
                hour_jst = h
                break
        else:
            # 全て過ぎている場合は翌日の最初の時刻
            hour_jst = hours[0]

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
    theme: str | None = None,
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
        theme: 動画テーマ（優先使用）
        script_path: 台本JSONファイルのパス（テーマ未指定時に参照）
        publish_at: 予約投稿日時（省略時は当日18:00 JST）
        scheduled: 予約投稿するか（Falseで即時公開）
        thumbnail_path: サムネイル画像のパス
        client_secrets_file: OAuthクライアントシークレット

    Returns:
        {"video_id": str, "url": str, "status": str}
    """
    # テーマ決定（引数 → 台本JSON → デフォルト）
    if not theme:
        if script_path is None:
            script_path = SCRIPTS_DIR / "script.json"
        if script_path.exists():
            theme = _extract_theme(script_path)
    if not theme:
        theme = "2chまとめ"

    # メタデータ生成
    title = generate_video_title(theme)
    description = generate_video_description(theme)
    tags = generate_tags(theme)

    logger.info(f"タイトル: {title}")
    logger.info(f"タグ: {', '.join(tags[:5])}...")

    # 予約投稿時刻
    if scheduled and publish_at is None:
        publish_at = get_next_publish_time()
        publish_jst = publish_at.astimezone(JST)
        logger.info(f"予約投稿: {publish_jst.strftime('%Y/%m/%d %H:%M')} JST")
    elif not scheduled:
        publish_at = None

    # YouTubeクライアント初期化（環境変数優先）
    client = YouTubeUploadClient(client_secrets_file=client_secrets_file)

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
