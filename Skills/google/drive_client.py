"""
Google Drive クライアント
ファイルのアップロード・ダウンロード操作
"""

from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .auth import GoogleAuth


class DriveClient:
    """Google Drive API クライアント"""

    SCOPES = ["https://www.googleapis.com/auth/drive.file"]

    MIME_TYPES = {
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".json": "application/json",
        ".txt": "text/plain",
        ".pdf": "application/pdf",
    }

    def __init__(
        self,
        folder_id: str | None = None,
        auth: GoogleAuth | None = None,
        client_secrets_file: str | None = None,
        service_account_file: str | None = None,
    ):
        """
        Args:
            folder_id: デフォルトのアップロード先フォルダID
            auth: GoogleAuth インスタンス（省略時は自動作成）
            client_secrets_file: クライアントシークレットファイル（OAuth用）
            service_account_file: サービスアカウントJSONファイル（OAuth審査不要）
        """
        self.folder_id = folder_id
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
                credentials = self.auth.get_credentials(self.SCOPES, "drive_token.json")
            elif self.client_secrets_file:
                self.auth = GoogleAuth(self.client_secrets_file)
                credentials = self.auth.get_credentials(self.SCOPES, "drive_token.json")
            else:
                raise ValueError(
                    "認証情報が必要です。auth, client_secrets_file, "
                    "または service_account_file のいずれかを指定してください。"
                )
            self.service = build("drive", "v3", credentials=credentials)

    def _get_mime_type(self, file_path: Path) -> str:
        """ファイル拡張子からMIMEタイプを取得"""
        return self.MIME_TYPES.get(file_path.suffix.lower(), "application/octet-stream")

    def upload_file(
        self,
        file_path: Path | str,
        file_name: str | None = None,
        folder_id: str | None = None,
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        """
        ファイルをアップロード

        Args:
            file_path: アップロードするファイルパス
            file_name: Drive上でのファイル名（省略時は元のファイル名）
            folder_id: アップロード先フォルダID（省略時はデフォルト）
            mime_type: MIMEタイプ（省略時は自動判定）

        Returns:
            {"id": str, "name": str, "url": str, "size": int}
        """
        self._ensure_service()

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

        file_name = file_name or file_path.name
        target_folder = folder_id or self.folder_id
        mime_type = mime_type or self._get_mime_type(file_path)

        # メタデータ
        file_metadata: dict[str, Any] = {"name": file_name}
        if target_folder:
            file_metadata["parents"] = [target_folder]

        # アップロード
        media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)

        file = (
            self.service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id,name,webViewLink,size",
            )
            .execute()
        )

        return {
            "id": file["id"],
            "name": file["name"],
            "url": file.get("webViewLink", f"https://drive.google.com/file/d/{file['id']}"),
            "size": int(file.get("size", 0)),
        }

    def create_folder(
        self,
        folder_name: str,
        parent_folder_id: str | None = None,
    ) -> str:
        """
        フォルダを作成

        Args:
            folder_name: フォルダ名
            parent_folder_id: 親フォルダID（省略時はルート）

        Returns:
            作成したフォルダのID
        """
        self._ensure_service()

        file_metadata: dict[str, Any] = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }

        if parent_folder_id:
            file_metadata["parents"] = [parent_folder_id]

        folder = (
            self.service.files()
            .create(body=file_metadata, fields="id,name")
            .execute()
        )

        return folder["id"]

    def list_files(
        self,
        folder_id: str | None = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """
        ファイル一覧を取得

        Args:
            folder_id: フォルダID（省略時は全ファイル）
            max_results: 最大取得件数

        Returns:
            ファイルメタデータのリスト
        """
        self._ensure_service()

        query = ""
        if folder_id:
            query = f"'{folder_id}' in parents"

        results = (
            self.service.files()
            .list(
                q=query,
                pageSize=max_results,
                fields="files(id,name,webViewLink,size,createdTime,mimeType)",
            )
            .execute()
        )

        return results.get("files", [])

    def delete_file(self, file_id: str) -> None:
        """
        ファイルを削除

        Args:
            file_id: ファイルID
        """
        self._ensure_service()
        self.service.files().delete(fileId=file_id).execute()

    def get_file_info(self, file_id: str) -> dict[str, Any]:
        """
        ファイル情報を取得

        Args:
            file_id: ファイルID

        Returns:
            ファイルメタデータ
        """
        self._ensure_service()

        return (
            self.service.files()
            .get(
                fileId=file_id,
                fields="id,name,webViewLink,size,createdTime,modifiedTime",
            )
            .execute()
        )

    @staticmethod
    def get_folder_url(folder_id: str) -> str:
        """フォルダURLを取得"""
        return f"https://drive.google.com/drive/folders/{folder_id}"
