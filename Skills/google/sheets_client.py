"""
Google Sheets クライアント
スプレッドシートの読み書き操作
"""

from datetime import datetime
from typing import Any

from googleapiclient.discovery import build

from .auth import GoogleAuth


class SheetsClient:
    """Google Sheets API クライアント"""

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(
        self,
        spreadsheet_id: str,
        auth: GoogleAuth | None = None,
        client_secrets_file: str | None = None,
        service_account_file: str | None = None,
    ):
        """
        Args:
            spreadsheet_id: スプレッドシートID
            auth: GoogleAuth インスタンス（省略時は自動作成）
            client_secrets_file: クライアントシークレットファイル（OAuth用）
            service_account_file: サービスアカウントJSONファイル（OAuth審査不要）
        """
        self.spreadsheet_id = spreadsheet_id
        self.auth = auth
        self.client_secrets_file = client_secrets_file
        self.service_account_file = service_account_file
        self.service = None

    def _ensure_service(self):
        """サービスを初期化（遅延初期化）"""
        if not self.service:
            # サービスアカウントが指定されていればそれを使用
            if self.service_account_file:
                credentials = GoogleAuth.from_service_account(
                    self.service_account_file, self.SCOPES
                )
            elif self.auth:
                credentials = self.auth.get_credentials(self.SCOPES, "sheets_token.json")
            elif self.client_secrets_file:
                self.auth = GoogleAuth(self.client_secrets_file)
                credentials = self.auth.get_credentials(self.SCOPES, "sheets_token.json")
            else:
                raise ValueError(
                    "認証情報が必要です。auth, client_secrets_file, "
                    "または service_account_file のいずれかを指定してください。"
                )
            self.service = build("sheets", "v4", credentials=credentials)

    def append_row(
        self,
        values: list[Any],
        sheet_name: str = "Sheet1",
        value_input_option: str = "RAW",
    ) -> dict:
        """
        行を追加

        Args:
            values: 追加する値のリスト
            sheet_name: シート名
            value_input_option: RAW or USER_ENTERED

        Returns:
            APIレスポンス
        """
        self._ensure_service()

        range_name = f"{sheet_name}!A:Z"
        body = {"values": [values]}

        result = (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body,
            )
            .execute()
        )

        return result

    def get_values(
        self,
        range_name: str = "Sheet1!A:Z",
    ) -> list[list[Any]]:
        """
        値を取得

        Args:
            range_name: 取得範囲（例: "Sheet1!A1:D10"）

        Returns:
            2次元配列
        """
        self._ensure_service()

        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=range_name)
            .execute()
        )

        return result.get("values", [])

    def update_cell(
        self,
        cell: str,
        value: Any,
        sheet_name: str = "Sheet1",
    ) -> dict:
        """
        セルを更新

        Args:
            cell: セル位置（例: "A1"）
            value: 値
            sheet_name: シート名

        Returns:
            APIレスポンス
        """
        self._ensure_service()

        range_name = f"{sheet_name}!{cell}"
        body = {"values": [[value]]}

        result = (
            self.service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                body=body,
            )
            .execute()
        )

        return result

    def batch_update(
        self,
        updates: list[dict],
    ) -> dict:
        """
        複数セルを一括更新

        Args:
            updates: [{"range": "Sheet1!A1", "values": [[value]]}] 形式のリスト

        Returns:
            APIレスポンス
        """
        self._ensure_service()

        body = {
            "valueInputOption": "RAW",
            "data": updates,
        }

        result = (
            self.service.spreadsheets()
            .values()
            .batchUpdate(spreadsheetId=self.spreadsheet_id, body=body)
            .execute()
        )

        return result

    def find_row_by_column(
        self,
        search_value: str,
        column_index: int = 0,
        sheet_name: str = "Sheet1",
    ) -> int | None:
        """
        列の値で行を検索

        Args:
            search_value: 検索する値
            column_index: 検索する列のインデックス（0始まり）
            sheet_name: シート名

        Returns:
            行番号（1始まり）、見つからない場合はNone
        """
        values = self.get_values(f"{sheet_name}!A:Z")

        for i, row in enumerate(values):
            if len(row) > column_index and row[column_index] == search_value:
                return i + 1  # 1-indexed

        return None

    def log_with_timestamp(
        self,
        values: list[Any],
        sheet_name: str = "Sheet1",
        timestamp_format: str = "%Y-%m-%d %H:%M:%S",
    ) -> dict:
        """
        タイムスタンプ付きでログを追加

        Args:
            values: 追加する値のリスト（タイムスタンプは自動追加）
            sheet_name: シート名
            timestamp_format: タイムスタンプのフォーマット

        Returns:
            APIレスポンス
        """
        timestamp = datetime.now().strftime(timestamp_format)
        row = [timestamp] + values
        return self.append_row(row, sheet_name)
