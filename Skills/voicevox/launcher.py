"""
VOICEVOX 起動ヘルパー
VOICEVOXが起動していない場合に自動起動
"""

import asyncio
import subprocess
import time
from pathlib import Path

import aiohttp


class VoicevoxLauncher:
    """VOICEVOX 起動管理"""

    DEFAULT_EXE_PATH = r"D:\App\VOICEVOX\VOICEVOX.exe"
    DEFAULT_API_URL = "http://localhost:50021"

    def __init__(
        self,
        exe_path: str | None = None,
        api_url: str | None = None,
    ):
        """
        Args:
            exe_path: VOICEVOX.exeのパス
            api_url: API URL
        """
        self.exe_path = Path(exe_path or self.DEFAULT_EXE_PATH)
        self.api_url = api_url or self.DEFAULT_API_URL

    async def is_running(self) -> bool:
        """VOICEVOXが起動中か確認"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/version",
                    timeout=aiohttp.ClientTimeout(total=2)
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    def is_running_sync(self) -> bool:
        """同期版"""
        return asyncio.run(self.is_running())

    def start(self) -> bool:
        """
        VOICEVOXを起動

        Returns:
            True: 起動成功、False: 起動失敗
        """
        if not self.exe_path.exists():
            print(f"VOICEVOX not found: {self.exe_path}")
            return False

        try:
            subprocess.Popen([str(self.exe_path)], shell=True)
            print(f"VOICEVOX started: {self.exe_path}")
            return True
        except Exception as e:
            print(f"Failed to start VOICEVOX: {e}")
            return False

    async def wait_for_ready(
        self,
        max_wait_seconds: int = 180,
        check_interval: float = 5.0,
    ) -> bool:
        """
        VOICEVOXのAPI準備完了を待つ

        Args:
            max_wait_seconds: 最大待機時間（秒）
            check_interval: チェック間隔（秒）

        Returns:
            True: 準備完了、False: タイムアウト
        """
        start_time = time.time()
        print(f"Waiting for VOICEVOX API (max {max_wait_seconds}s)...")

        while (time.time() - start_time) < max_wait_seconds:
            if await self.is_running():
                elapsed = time.time() - start_time
                print(f"VOICEVOX ready! ({elapsed:.1f}s)")
                return True

            elapsed = time.time() - start_time
            print(f"  [{elapsed:.1f}s] Waiting...")
            await asyncio.sleep(check_interval)

        print(f"Timeout: VOICEVOX not ready within {max_wait_seconds}s")
        return False

    def wait_for_ready_sync(
        self,
        max_wait_seconds: int = 180,
        check_interval: float = 5.0,
    ) -> bool:
        """同期版"""
        return asyncio.run(self.wait_for_ready(max_wait_seconds, check_interval))

    async def ensure_running(
        self,
        max_wait_seconds: int = 180,
    ) -> bool:
        """
        VOICEVOXが起動していることを保証（必要なら起動して待機）

        Args:
            max_wait_seconds: 最大待機時間

        Returns:
            True: 準備完了、False: 失敗
        """
        if await self.is_running():
            print("VOICEVOX is already running")
            return True

        print("Starting VOICEVOX...")
        if not self.start():
            return False

        return await self.wait_for_ready(max_wait_seconds)

    def ensure_running_sync(self, max_wait_seconds: int = 180) -> bool:
        """同期版"""
        return asyncio.run(self.ensure_running(max_wait_seconds))
