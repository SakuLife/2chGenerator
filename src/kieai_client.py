"""
KieAI API クライアント
Nanobanana（画像生成）のAPIを呼び出すクライアント
"""

import json
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

from logger import logger


def request_with_retry(
    method: str,
    url: str,
    headers: dict | None = None,
    json_payload: dict | None = None,
    params: dict | None = None,
    timeout: int = 60,
    max_retries: int = 2,
) -> requests.Response:
    """
    リトライ付きHTTPリクエスト

    Args:
        method: HTTPメソッド（GET, POST等）
        url: リクエストURL
        headers: HTTPヘッダー
        json_payload: JSONボディ
        params: クエリパラメータ
        timeout: タイムアウト秒数
        max_retries: 最大リトライ回数

    Returns:
        レスポンスオブジェクト

    Raises:
        requests.RequestException: リトライ後も失敗した場合
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                json=json_payload,
                params=params,
                timeout=timeout,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            wait_time = 2 + attempt * 2
            logger.warning(f"[Retry] Attempt {attempt + 1} failed, waiting {wait_time}s...")
            time.sleep(wait_time)
    raise last_exc


def download_file(url: str, output_path: Path, timeout: int = 120) -> Path:
    """
    URLからファイルをダウンロード

    Args:
        url: ダウンロードURL
        output_path: 保存先パス
        timeout: タイムアウト秒数

    Returns:
        保存したファイルパス
    """
    response = requests.get(url, timeout=timeout, stream=True)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return output_path


class KieAIClient:
    """KieAI API クライアント（Nanobanana画像生成用）"""

    DEFAULT_API_BASE = "https://api.kieai.net"
    NANOBANANA_ENDPOINT = "/api/v1/jobs/createTask"
    NANOBANANA_QUERY_ENDPOINT = "/api/v1/jobs/recordInfo"

    def __init__(
        self,
        api_key: str,
        api_base: str | None = None,
    ):
        """
        Args:
            api_key: KieAI APIキー
            api_base: APIベースURL（デフォルト: https://api.kieai.net）
        """
        self.api_key = api_key
        self.api_base = api_base or self.DEFAULT_API_BASE

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def generate_nanobanana(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        output_format: str = "png",
        max_wait: int = 600,
        poll_interval: int = 10,
    ) -> str:
        """
        Nanobanana（通常版）で画像を生成する

        特徴:
        - Gemini 2.5 Flash ベース
        - 高速（数秒）
        - 解像度: ~1MP
        - コスト: 2クレジット/枚

        Args:
            prompt: 画像のプロンプト
            aspect_ratio: アスペクト比（1:1, 16:9, 4:3など）
            output_format: 出力形式（png, jpeg）
            max_wait: 最大待機時間（秒）
            poll_interval: ポーリング間隔（秒）

        Returns:
            生成された画像のURL
        """
        url = urljoin(self.api_base, self.NANOBANANA_ENDPOINT)

        input_params = {
            "prompt": prompt,
            "image_size": aspect_ratio,
            "output_format": output_format,
        }

        payload = {
            "model": "google/nano-banana",
            "callBackUrl": "http://localhost:8000/callback",
            "input": input_params,
        }

        response = request_with_retry(
            "POST",
            url,
            headers=self._headers(),
            json_payload=payload,
        )
        data = response.json()

        if data.get("code") != 200:
            raise RuntimeError(f"Nanobanana API error: {data}")

        task_id = data.get("data", {}).get("taskId")
        if not task_id:
            raise RuntimeError(f"No taskId in response: {data}")

        return self._poll_nanobanana_task(task_id, max_wait, poll_interval)

    def _poll_nanobanana_task(
        self, task_id: str, max_wait: int = 600, poll_interval: int = 10
    ) -> str:
        """Nanobananaタスクの完了をポーリング"""
        query_url = urljoin(self.api_base, self.NANOBANANA_QUERY_ENDPOINT)
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = request_with_retry(
                "GET",
                query_url,
                headers=self._headers(),
                params={"taskId": task_id},
            )
            data = response.json()

            if data.get("code") != 200:
                raise RuntimeError(f"Query error: {data}")

            status = data.get("data", {}).get("state")
            logger.info(f"[Nanobanana] Task {task_id} status: {status}")

            if status == "success":
                result_json_str = data.get("data", {}).get("resultJson", "{}")
                try:
                    result_json = json.loads(result_json_str)
                    result_urls = result_json.get("resultUrls", [])
                    if result_urls and len(result_urls) > 0:
                        return result_urls[0]
                except (json.JSONDecodeError, KeyError):
                    pass
                raise RuntimeError(f"No image URL in completed task: {data}")

            if status in ("FAILED", "ERROR", "failed", "error"):
                raise RuntimeError(f"Task failed: {data}")

            time.sleep(poll_interval)

        raise RuntimeError(f"Task {task_id} timed out after {max_wait}s")

    def generate_and_download(
        self,
        prompt: str,
        output_path: Path,
        aspect_ratio: str = "16:9",
    ) -> Path:
        """
        画像を生成してダウンロードする

        Args:
            prompt: 画像のプロンプト
            output_path: 保存先パス
            aspect_ratio: アスペクト比

        Returns:
            ダウンロードしたファイルパス
        """
        image_url = self.generate_nanobanana(prompt, aspect_ratio)
        return download_file(image_url, output_path)
