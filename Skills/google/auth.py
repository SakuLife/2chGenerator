"""
Google 認証ヘルパー
OAuth 2.0 とサービスアカウント両対応
"""

import os
from pathlib import Path
from typing import Sequence

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow


class GoogleAuth:
    """Google OAuth 2.0 認証マネージャー"""

    def __init__(
        self,
        client_secrets_file: str | Path = "client_secrets.json",
        token_dir: str | Path = ".",
    ):
        """
        Args:
            client_secrets_file: Google Cloud Consoleからダウンロードしたクライアントシークレット
            token_dir: トークンファイルを保存するディレクトリ
        """
        self.client_secrets_file = Path(client_secrets_file)
        self.token_dir = Path(token_dir)
        self.token_dir.mkdir(parents=True, exist_ok=True)

    def get_credentials(
        self,
        scopes: Sequence[str],
        token_file: str = "token.json",
        force_refresh: bool = False,
    ) -> Credentials:
        """
        OAuth 2.0 認証情報を取得

        Args:
            scopes: 必要なスコープのリスト
            token_file: トークンファイル名
            force_refresh: 強制的に再認証するか

        Returns:
            認証情報（Credentials）

        Raises:
            FileNotFoundError: クライアントシークレットが見つからない場合
            RuntimeError: CI環境でトークンがない場合
        """
        token_path = self.token_dir / token_file
        credentials = None

        # 既存トークンを読み込み
        if not force_refresh and token_path.exists() and token_path.stat().st_size > 0:
            credentials = Credentials.from_authorized_user_file(str(token_path), scopes)

        # トークンが無効または期限切れの場合
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                # リフレッシュトークンで更新
                credentials.refresh(Request())
            else:
                # 新規認証フロー
                if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
                    raise RuntimeError(
                        f"CI環境では対話的認証ができません。{token_path}を事前に作成してください。"
                    )

                if not self.client_secrets_file.exists():
                    raise FileNotFoundError(
                        f"クライアントシークレットが見つかりません: {self.client_secrets_file}\n"
                        "Google Cloud Console からダウンロードしてください。"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.client_secrets_file), scopes
                )
                credentials = flow.run_local_server(port=0)

            # トークンを保存
            with open(token_path, "w") as f:
                f.write(credentials.to_json())

        return credentials

    def get_api_key_only_credentials(self):
        """
        APIキーのみで認証（YouTube Data API等で公開データ取得時）

        Returns:
            None（developerKeyとしてAPIキーを直接渡す）
        """
        return None

    @staticmethod
    def from_service_account(
        service_account_file: str | Path,
        scopes: Sequence[str],
    ) -> "Credentials":
        """
        サービスアカウントで認証（OAuth審査不要）

        Args:
            service_account_file: サービスアカウントJSONファイルのパス
            scopes: 必要なスコープのリスト

        Returns:
            認証情報（Credentials）

        Raises:
            FileNotFoundError: サービスアカウントファイルが見つからない場合
        """
        sa_path = Path(service_account_file)
        if not sa_path.exists():
            raise FileNotFoundError(
                f"サービスアカウントファイルが見つかりません: {sa_path}\n"
                "Google Cloud Console からダウンロードしてください。"
            )

        credentials = service_account.Credentials.from_service_account_file(
            str(sa_path), scopes=scopes
        )
        return credentials
