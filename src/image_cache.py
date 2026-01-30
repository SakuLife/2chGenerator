"""
画像キャッシュモジュール
SHA256ハッシュベースで画像をキャッシュし、同じプロンプトの再生成を防ぐ
"""

import hashlib
import shutil
from pathlib import Path

from config import IMAGE_CACHE_DIR, IRASUTOYA_STYLE_PREFIX
from logger import logger


class ImageCache:
    """SHA256ハッシュベースの画像キャッシュ"""

    def __init__(self, cache_dir: Path | None = None):
        """
        Args:
            cache_dir: キャッシュディレクトリ（デフォルト: generated/cache/images）
        """
        self.cache_dir = cache_dir or IMAGE_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, text: str) -> str:
        """テキストのSHA256ハッシュを計算（先頭16文字）"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def transform_to_irasutoya_style(self, prompt: str) -> str:
        """
        プロンプトをいらすとや風に変換

        Args:
            prompt: 元のプロンプト

        Returns:
            いらすとや風スタイルプレフィックス付きプロンプト
        """
        # 改行を除去してスタイルプレフィックスを整形
        style_prefix = " ".join(IRASUTOYA_STYLE_PREFIX.split())
        return f"{style_prefix}, {prompt}"

    def get_cache_path(self, prompt: str) -> Path:
        """
        プロンプトに対応するキャッシュファイルパスを取得

        Args:
            prompt: 画像のプロンプト

        Returns:
            キャッシュファイルパス
        """
        hash_value = self._compute_hash(prompt)
        return self.cache_dir / f"{hash_value}.png"

    def exists(self, prompt: str) -> bool:
        """
        キャッシュが存在するか確認

        Args:
            prompt: 画像のプロンプト

        Returns:
            キャッシュが存在するかどうか
        """
        return self.get_cache_path(prompt).exists()

    def get(self, prompt: str, output_path: Path) -> bool:
        """
        キャッシュから画像を取得（コピー）

        Args:
            prompt: 画像のプロンプト
            output_path: コピー先パス

        Returns:
            キャッシュが存在してコピーできたかどうか
        """
        cache_path = self.get_cache_path(prompt)

        if cache_path.exists():
            shutil.copy2(cache_path, output_path)
            logger.info(f"[Cache] ヒット: {cache_path.name} -> {output_path.name}")
            return True

        return False

    def save(self, prompt: str, source_path: Path) -> Path:
        """
        画像をキャッシュに保存

        Args:
            prompt: 画像のプロンプト
            source_path: 保存元の画像パス

        Returns:
            キャッシュファイルパス
        """
        cache_path = self.get_cache_path(prompt)
        shutil.copy2(source_path, cache_path)
        logger.info(f"[Cache] 保存: {source_path.name} -> {cache_path.name}")
        return cache_path

    def get_or_generate(
        self,
        prompt: str,
        output_path: Path,
        generate_fn: callable,
    ) -> Path:
        """
        キャッシュから取得、なければ生成してキャッシュに保存

        Args:
            prompt: 画像のプロンプト
            output_path: 出力先パス
            generate_fn: 画像生成関数 (prompt, output_path) -> Path

        Returns:
            画像ファイルパス
        """
        # キャッシュチェック
        if self.get(prompt, output_path):
            return output_path

        # 生成
        logger.info(f"[Cache] ミス: 新規生成開始")
        generate_fn(prompt, output_path)

        # キャッシュに保存
        self.save(prompt, output_path)

        return output_path


# デフォルトインスタンス
image_cache = ImageCache()
