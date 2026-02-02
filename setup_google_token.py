"""
Google Drive + Sheets 用 OAuth トークン生成スクリプト
ローカルで実行して google_token.json を生成する
"""

import os

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Drive + Sheets の両方のスコープ
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]


def main():
    print("=" * 60)
    print("Google Drive + Sheets 認証セットアップ")
    print("=" * 60)
    print()

    token_file = "google_token.json"
    client_secrets_file = "client_secrets.json"

    if not os.path.exists(client_secrets_file):
        print(f"[ERROR] {client_secrets_file} が見つかりません")
        return

    # 既存トークン削除
    if os.path.exists(token_file):
        print(f"既存の {token_file} を削除して再認証...")
        os.remove(token_file)

    print("ブラウザが開きます。Googleアカウントでログインしてください。")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
    credentials = flow.run_local_server(port=0)

    with open(token_file, "w") as f:
        f.write(credentials.to_json())

    print()
    print("[OK] 認証成功！")

    # 確認
    print("Drive API 接続確認...")
    build("drive", "v3", credentials=credentials)
    print("[OK] Drive API OK")

    print("Sheets API 接続確認...")
    build("sheets", "v4", credentials=credentials)
    print("[OK] Sheets API OK")

    print()
    print(f"[OK] {token_file} が生成されました")
    print()
    print("次のステップ:")
    print("1. base64エンコード:")
    print(f'   powershell -Command "[Convert]::ToBase64String([IO.File]::ReadAllBytes(\'{token_file}\')) | Set-Content google_token_b64.txt"')
    print()
    print("2. google_token_b64.txt の内容を GitHub Secrets → GOOGLE_TOKEN_JSON_B64 に登録")


if __name__ == "__main__":
    main()
