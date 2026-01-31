"""
VOICEVOX API クライアント
音声合成の実行
"""

import asyncio
import re
import tempfile
from pathlib import Path

import aiohttp
from pydub import AudioSegment


# 英語→カタカナ変換辞書（VOICEVOXが正しく読み上げるため）
ENGLISH_TO_KATAKANA = {
    # ネットスラング・2ch用語
    "www": "わらわら",
    "ww": "わら",
    "w": "",
    "orz": "オルズ",
    "ktkr": "キタコレ",
    "kwsk": "くわしく",
    "ggrks": "ググレカス",
    "DQN": "ドキュン",
    "JK": "ジェーケー",
    "JC": "ジェーシー",
    "JD": "ジェーディー",
    "NG": "エヌジー",
    "OK": "オーケー",
    "NG": "エヌジー",
    # お金・投資関連
    "FIRE": "ファイア",
    "fire": "ファイア",
    "NISA": "ニーサ",
    "nisa": "ニーサ",
    "iDeCo": "イデコ",
    "ideco": "イデコ",
    "FX": "エフエックス",
    "ETF": "イーティーエフ",
    "S&P": "エスアンドピー",
    "GDP": "ジーディーピー",
    # 一般的な英語
    "Google": "グーグル",
    "AI": "エーアイ",
    "YouTube": "ユーチューブ",
    "Twitter": "ツイッター",
    "LINE": "ライン",
    "Amazon": "アマゾン",
    "Apple": "アップル",
    "iPhone": "アイフォン",
    "PC": "ピーシー",
    "IT": "アイティー",
    "SNS": "エスエヌエス",
    "CEO": "シーイーオー",
    "MBA": "エムビーエー",
}

# スピーカーID一覧（よく使うもの）
SPEAKERS = {
    "ずんだもん（ノーマル）": 3,
    "ずんだもん（あまあま）": 1,
    "ずんだもん（ツンツン）": 7,
    "四国めたん（ノーマル）": 2,
    "四国めたん（あまあま）": 0,
    "春日部つむぎ": 8,
    "雨晴はう": 10,
    "波音リツ": 9,
    "玄野武宏": 11,
    "白上虎太郎": 12,
    "青山龍星": 13,
    "冥鳴ひまり": 14,
    "九州そら": 16,
}


class VoicevoxClient:
    """VOICEVOX API クライアント"""

    DEFAULT_API_URL = "http://localhost:50021"
    DEFAULT_SPEAKER_ID = 3  # ずんだもん（ノーマル）

    def __init__(
        self,
        api_url: str | None = None,
        speaker_id: int | None = None,
    ):
        """
        Args:
            api_url: VOICEVOX API URL（デフォルト: http://localhost:50021）
            speaker_id: デフォルトのスピーカーID（デフォルト: 3 = ずんだもん）
        """
        self.api_url = api_url or self.DEFAULT_API_URL
        self.speaker_id = speaker_id or self.DEFAULT_SPEAKER_ID

    async def check_connection(self) -> bool:
        """
        VOICEVOX APIが起動しているか確認

        Returns:
            True: 接続可能、False: 接続不可
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/version",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        version = await response.text()
                        print(f"VOICEVOX API version: {version}")
                        return True
        except Exception:
            pass
        return False

    def check_connection_sync(self) -> bool:
        """同期版の接続確認"""
        return asyncio.run(self.check_connection())

    async def synthesize(
        self,
        text: str,
        output_path: Path,
        speaker_id: int | None = None,
    ) -> Path:
        """
        テキストを音声に変換

        Args:
            text: 読み上げテキスト
            output_path: 出力ファイルパス（.wav）
            speaker_id: スピーカーID（省略時はデフォルト）

        Returns:
            出力ファイルパス

        Raises:
            RuntimeError: 音声合成失敗時
        """
        speaker_id = speaker_id or self.speaker_id
        text = self._convert_english_to_katakana(text)

        audio_data = await self._synthesize_chunk(text, speaker_id)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_data)

        return output_path

    def synthesize_sync(
        self,
        text: str,
        output_path: Path,
        speaker_id: int | None = None,
    ) -> Path:
        """同期版の音声合成"""
        return asyncio.run(self.synthesize(text, output_path, speaker_id))

    async def synthesize_with_subtitles(
        self,
        subtitles: list[dict],
        output_path: Path,
        speaker_id: int | None = None,
        speaker_mapping: dict[str, int] | None = None,
    ) -> tuple[Path, list[dict]]:
        """
        字幕リストから音声を生成し、実測タイミングを返す

        Args:
            subtitles: 字幕データのリスト [{"role": "...", "text": "..."}]
            output_path: 出力ファイルパス（.wav）
            speaker_id: デフォルトスピーカーID
            speaker_mapping: 役割→スピーカーIDのマッピング

        Returns:
            (出力パス, タイミング更新済み字幕リスト)
        """
        speaker_id = speaker_id or self.speaker_id
        speaker_mapping = speaker_mapping or {}

        audio_chunks = []
        total = len(subtitles)

        for i, subtitle in enumerate(subtitles):
            text = subtitle.get("text", "").strip()
            role = subtitle.get("role", "")

            if not text or role == "title_card":
                continue

            # 役割に応じたスピーカーを選択
            spk = speaker_mapping.get(role, speaker_id)

            print(f"[{i+1}/{total}] 音声生成中: {text[:30]}...")
            audio_data = await self._synthesize_chunk(text, spk)
            audio_chunks.append((i, audio_data))

            await asyncio.sleep(0.05)  # API負荷軽減

        # 音声結合とタイミング計測
        combined = AudioSegment.empty()
        updated_subtitles = []
        current_time = 0.0

        for idx, audio_data in audio_chunks:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = Path(tmp.name)

            try:
                segment = AudioSegment.from_wav(str(tmp_path))
                duration_sec = len(segment) / 1000.0

                combined += segment

                subtitle = subtitles[idx].copy()
                subtitle["start_time"] = current_time
                subtitle["duration"] = duration_sec
                updated_subtitles.append(subtitle)

                current_time += duration_sec
            finally:
                tmp_path.unlink(missing_ok=True)

        # title_cardは3秒固定で追加
        for i, subtitle in enumerate(subtitles):
            if subtitle.get("role") == "title_card":
                sub = subtitle.copy()
                # title_cardの位置を探して挿入
                insert_pos = 0
                for j, us in enumerate(updated_subtitles):
                    if us.get("index", j) > i:
                        break
                    insert_pos = j + 1
                sub["start_time"] = 0.0 if insert_pos == 0 else updated_subtitles[insert_pos-1].get("start_time", 0) + updated_subtitles[insert_pos-1].get("duration", 0)
                sub["duration"] = 3.0
                # 実際には先頭に挿入しない（動画編集側で処理）

        # 音量を少し上げる
        combined = combined.apply_gain(1.5)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined.export(str(output_path), format="wav")

        total_duration = len(combined) / 1000.0
        print(f"音声生成完了: {total_duration:.1f}秒")

        return output_path, updated_subtitles

    def synthesize_with_subtitles_sync(
        self,
        subtitles: list[dict],
        output_path: Path,
        speaker_id: int | None = None,
        speaker_mapping: dict[str, int] | None = None,
    ) -> tuple[Path, list[dict]]:
        """同期版"""
        return asyncio.run(
            self.synthesize_with_subtitles(subtitles, output_path, speaker_id, speaker_mapping)
        )

    async def _synthesize_chunk(self, text: str, speaker_id: int) -> bytes:
        """単一テキストの音声合成"""
        text = self._convert_english_to_katakana(text)

        async with aiohttp.ClientSession() as session:
            # Step 1: audio_query
            async with session.post(
                f"{self.api_url}/audio_query",
                params={"text": text, "speaker": speaker_id}
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise RuntimeError(f"audio_query failed: {response.status} - {error}")
                query_data = await response.json()

            # Step 2: synthesis
            async with session.post(
                f"{self.api_url}/synthesis",
                params={"speaker": speaker_id},
                json=query_data
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise RuntimeError(f"synthesis failed: {response.status} - {error}")
                return await response.read()

    def _convert_english_to_katakana(self, text: str) -> str:
        """英語をカタカナに変換"""
        result = text

        for eng, kana in sorted(
            ENGLISH_TO_KATAKANA.items(),
            key=lambda x: len(x[0]),
            reverse=True
        ):
            result = result.replace(eng, kana)

        return result

    async def get_speakers(self) -> list[dict]:
        """利用可能なスピーカー一覧を取得"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/speakers") as response:
                if response.status != 200:
                    raise RuntimeError(f"Failed to get speakers: {response.status}")
                return await response.json()

    def get_speakers_sync(self) -> list[dict]:
        """同期版"""
        return asyncio.run(self.get_speakers())
