"""
UTF-8対応ロガー
Windows環境でも日本語が文字化けしないロガー設定
常時ファイルログ出力対応
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# ログ出力先ディレクトリ
LOGS_DIR = Path(__file__).parent.parent / "generated" / "logs"


def _get_utf8_stream():
    """
    stdoutをUTF-8モードで開き直す（Windows consoleでの文字化け対策）
    失敗した場合は元のstdoutを返す
    """
    try:
        return open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1, closefd=False)
    except Exception:
        return sys.stdout


def setup_logger(
    name: str = "2ch_video_gen",
    log_file: Path | None = None,
    debug: bool = False,
    enable_file_log: bool = True,
) -> logging.Logger:
    """
    UTF-8対応ロガーをセットアップ

    Args:
        name: ロガー名
        log_file: ログファイルパス（指定なしの場合は自動生成）
        debug: デバッグモードを有効にするか
        enable_file_log: ファイルログを有効にするか

    Returns:
        設定済みのロガーインスタンス
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # 重複ハンドラー防止
    if logger.handlers:
        return logger

    # コンソールハンドラー（UTF-8ストリーム使用）
    console_stream = _get_utf8_stream()
    console_handler = logging.StreamHandler(console_stream)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)

    # フォーマッター
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ファイルハンドラー（常時有効）
    if enable_file_log:
        if log_file is None:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = LOGS_DIR / f"run_{timestamp}.log"

        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.log_file_path = log_file  # ログファイルパスを保持

    return logger


# デフォルトロガーインスタンス（常時ファイルログ有効）
logger = setup_logger()
