# 2ch動画生成システム セットアップガイド

このガイドでは、システムのインストールから初回動画生成までを**初心者でもわかるように**解説します。

---

## 📋 目次

1. [必要なもの](#必要なもの)
2. [事前準備（重要）](#事前準備重要)
3. [インストール手順](#インストール手順)
   - [Windows版](#windows版)
   - [Mac版](#mac版)
4. [初回セットアップ](#初回セットアップ)
5. [動画を作ってみる](#動画を作ってみる)
6. [トラブルシューティング](#トラブルシューティング)
7. [よくある質問](#よくある質問)

---

## 必要なもの

### 1. パソコンの動作環境

- **OS**: Windows 10/11 または macOS 10.15以降
- **メモリ**: 8GB以上推奨
- **ストレージ**: 5GB以上の空き容量
- **インターネット**: 高速回線推奨

### 2. OpenAI APIアカウント（必須）

動画生成には**OpenAI API**が必要です。

- **料金**: 1動画あたり約$2.5〜$3（約350〜420円）
- **最小チャージ**: $5から利用可能
- **取得方法**: [事前準備](#事前準備重要)を参照

---

## 事前準備（重要）

### OpenAI APIキーの取得

動画生成には**OpenAI API**が必須です。以下の手順で取得してください。

#### ステップ1: OpenAIアカウント作成

1. https://platform.openai.com/ にアクセス
2. 「Sign up」をクリックして新規登録
3. メールアドレスまたはGoogleアカウントで登録
4. メール認証を完了

#### ステップ2: 支払い方法の設定

1. ログイン後、右上のアカウントメニューから「Billing」をクリック
2. 「Add payment method」でクレジットカードを登録
3. 最低$5をチャージ（推奨: $10〜$20）

#### ステップ3: APIキーの発行

1. 左メニューから「API keys」をクリック
2. 「Create new secret key」をクリック
3. 名前（例: 2ch-video-generator）を入力
4. **表示されたAPIキーをコピー**（後で使います）
   - 形式: `sk-proj-xxxxxxxxxxxxxxxxxx`
   - ⚠️ **このキーは二度と表示されません。必ず保存してください**

> 💡 **重要**: APIキーは他人に見せないでください。悪用される可能性があります。

---

## インストール手順

### Windows版

#### 1. Pythonのインストール

1. https://www.python.org/downloads/ にアクセス
2. 「Download Python 3.12.x」をクリック
3. ダウンロードしたインストーラーを実行
4. ⚠️ **重要**: 「Add Python to PATH」に**必ずチェック**を入れる
5. 「Install Now」をクリック
6. インストール完了後、コマンドプロンプトで確認：

```cmd
python --version
```

出力例: `Python 3.12.0`

#### 2. FFmpegのインストール

##### 方法A: Chocolatey経由（推奨）

```cmd
# 1. PowerShellを管理者権限で開く
# 2. Chocolateyをインストール
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 3. FFmpegをインストール
choco install ffmpeg -y
```

##### 方法B: 手動インストール

1. https://www.gyan.dev/ffmpeg/builds/ にアクセス
2. 「ffmpeg-release-essentials.zip」をダウンロード
3. 解凍して `C:\ffmpeg` に配置
4. 環境変数PATHに `C:\ffmpeg\bin` を追加

#### 3. システムファイルの配置

1. 受け取ったZIPファイルを解凍
2. `2ch-video-generator` フォルダを任意の場所に配置
   - 推奨: `C:\Users\[ユーザー名]\Documents\2ch-video-generator`

#### 4. コマンドプロンプトで移動

```cmd
cd C:\Users\[ユーザー名]\Documents\2ch-video-generator
```

---

### Mac版

#### 1. Homebrewのインストール

ターミナルを開いて以下を実行：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### 2. Python 3のインストール

```bash
brew install python@3.12
```

確認：

```bash
python3 --version
```

出力例: `Python 3.12.0`

#### 3. FFmpegのインストール

```bash
brew install ffmpeg
```

確認：

```bash
ffmpeg -version
```

#### 4. システムファイルの配置

1. 受け取ったZIPファイルを解凍
2. `2ch-video-generator` フォルダを任意の場所に配置
   - 推奨: `~/Documents/2ch-video-generator`

#### 5. ターミナルで移動

```bash
cd ~/Documents/2ch-video-generator
```

---

## 初回セットアップ

### ステップ1: 自動セットアップの実行

システムフォルダに移動後、以下を実行：

#### Windows:
```cmd
python setup.py
```

#### Mac/Linux:
```bash
python3 setup.py
```

このスクリプトが以下を自動で行います：
- ✅ Python・FFmpegのチェック
- ✅ 必要なパッケージのインストール
- ✅ サンプルファイルの作成

> ⏱️ 初回は5〜10分かかる場合があります

### ステップ2: APIキーの設定

#### Windows:
```cmd
# .env.example を .env にコピー
copy .env.example .env

# メモ帳で開く
notepad .env
```

#### Mac:
```bash
# .env.example を .env にコピー
cp .env.example .env

# テキストエディタで開く
open -e .env
```

#### .envファイルを編集

以下の行を見つけて、APIキーを貼り付けます：

```env
# 変更前
OPENAI_API_KEY=your_openai_api_key_here

# 変更後（実際のキーを入力）
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxx
```

**保存して閉じてください。**

### ステップ3: BGMとフォントの追加（オプション）

#### BGMを追加（推奨）

1. フリーBGMをダウンロード:
   - [DOVA-SYNDROME](https://dova-s.jp/) - 人気
   - [魔王魂](https://maou.audio/)

2. ダウンロードした `.mp3` ファイルを以下に配置:
   ```
   2ch-video-generator/assets/bgm/
   ```

#### 日本語フォントを追加（オプション）

1. [Noto Sans JP](https://fonts.google.com/noto/specimen/Noto+Sans+JP) をダウンロード
2. `NotoSansJP-Bold.ttf` を以下に配置:
   ```
   2ch-video-generator/assets/fonts/
   ```

---

## 動画を作ってみる

### テスト動画の生成

#### Windows:
```cmd
python main.py --theme "30代で貯金1000万貯めた話" --auto
```

#### Mac:
```bash
python3 main.py --theme "30代で貯金1000万貯めた話" --auto
```

### 生成の流れ

```
============================================================
  2ch/5ch まとめ動画自動生成システム
============================================================

Step 1/4: 台本生成中...
→ GPT-4が2ch風のスレッドを作成

Step 2/4: 画像生成中...
→ DALL-E 3が通帳や資産画面を生成

Step 3/4: 音声生成中...
→ OpenAI TTSが複数の声で読み上げ

Step 4/4: 動画生成中...
→ MoviePyで映像と音声を結合

✅ 動画生成完了！
出力先: generated/output_video.mp4
```

### 完成動画の確認

```
2ch-video-generator/generated/output_video.mp4
```

ダブルクリックで再生できます！

---

## トラブルシューティング

### エラー1: `python: command not found`

**原因**: Pythonがインストールされていないか、PATHが通っていない

**解決策**:
- Windows: インストール時に「Add Python to PATH」にチェックを入れ忘れた可能性
  → Pythonを再インストール
- Mac: `python3` を使用してください

### エラー2: `ffmpeg: command not found`

**原因**: FFmpegがインストールされていない

**解決策**:
- Windows: [方法A](#方法achocolatey経由推奨) を再度実行
- Mac: `brew install ffmpeg` を実行

### エラー3: `OpenAI API key not found`

**原因**: APIキーが設定されていない

**解決策**:
1. `.env` ファイルが存在するか確認
2. `OPENAI_API_KEY=` の後に正しいキーが入っているか確認
3. キーの前後に余分なスペースがないか確認

### エラー4: `Rate limit exceeded`

**原因**: OpenAI APIのレート制限

**解決策**:
- 5〜10分待ってから再実行
- OpenAIアカウントの利用枠を確認（有料プランへのアップグレード検討）

### エラー5: 画像生成に失敗する

**原因**: DALL-E 3のコンテンツポリシー違反

**解決策**:
- 台本を確認し、不適切な内容がないか確認
- テーマを変更して再生成

### エラー6: 動画が真っ黒

**原因**: 背景画像がない、またはフォントエラー

**解決策**:
```bash
# サンプルアセットを再生成
python create_sample_assets.py
```

---

## よくある質問

### Q1. 動画生成にどれくらい時間がかかりますか？

**A**: 1本あたり**5〜15分**程度です。
- 台本生成: 30秒〜1分
- 画像生成: 1〜3分（枚数による）
- 音声生成: 2〜5分
- 動画編集: 2〜5分

### Q2. 料金はいくらかかりますか？

**A**: 1動画あたり**約$2.5〜$3**（約350〜420円）
- 台本生成: ~$0.02
- 音声生成: ~$0.30
- 画像生成: ~$0.40/枚（5枚で$2）

### Q3. オフラインで使えますか？

**A**: いいえ。OpenAI APIに接続するため、インターネット接続が必須です。

### Q4. 商用利用できますか？

**A**: OpenAIの利用規約に従う限り可能です。
- YouTubeへのアップロード: ⭕ OK
- 収益化: ⭕ OK
- ただし、OpenAIのポリシーを必ず確認してください

### Q5. 生成された台本を編集できますか？

**A**: はい。以下の手順で可能です：

```bash
# 1. 台本のみ生成
python main.py --theme "テーマ" --script-only

# 2. generated/scripts/script.json を編集

# 3. 編集後、動画を生成
python main.py --generate-video
```

### Q6. 声を変更できますか？

**A**: はい。`src/config.py` の `VOICE_MAPPING` を編集してください。

利用可能な声:
- `alloy` - 中性的
- `echo` - 男性的
- `fable` - 女性的
- `onyx` - 低い男性声
- `nova` - 若い女性声
- `shimmer` - 優しい女性声

### Q7. 動画サイズを変更できますか？

**A**: はい。`src/config.py` の `DEFAULT_VIDEO_SIZE` を編集：

```python
# フルHD
DEFAULT_VIDEO_SIZE = (1920, 1080)

# 4K
DEFAULT_VIDEO_SIZE = (3840, 2160)
```

### Q8. 複数の動画を一度に作れますか？

**A**: 現在は1本ずつですが、スクリプトを編集することで可能です。

### Q9. エラーが出て動作しません

**A**: 以下を確認してください：
1. Python 3.8以上がインストールされているか
2. FFmpegがインストールされているか
3. `.env` ファイルにAPIキーが正しく設定されているか
4. インターネット接続が正常か

それでも解決しない場合は、エラーメッセージを記録してサポートに連絡してください。

### Q10. Windowsとマックどちらが良いですか？

**A**: 動作に差はありません。お使いのOSで問題ありません。

---

## コマンド早見表

### 全自動生成
```bash
python main.py --theme "テーマ" --auto
```

### 台本のみ生成
```bash
python main.py --theme "テーマ" --script-only
```

### 既存台本から動画生成
```bash
python main.py --generate-video
```

### 画像生成方法を指定
```bash
# OpenAI DALL-E 3
python main.py --theme "テーマ" --image-method openai --auto

# KIEAI API
python main.py --theme "テーマ" --image-method kieai --auto
```

### BGMなしで生成
```bash
python main.py --theme "テーマ" --auto --no-bgm
```

---

## サポート

### ドキュメント

- **詳細マニュアル**: `README.md`
- **クイックスタート**: `QUICKSTART.md`
- **このガイド**: `INSTALLATION_GUIDE.md`

### 問い合わせ

技術的な問題やご質問は、以下の方法でお問い合わせください：

- **メール**: support@example.com
- **Discord**: [招待リンク]
- **営業時間**: 平日 10:00〜18:00（土日祝休み）

---

## アップデート情報

システムのアップデートは、メールまたはDiscordで通知されます。

新しいバージョンが利用可能になった場合:
1. 新しいZIPファイルをダウンロード
2. `.env` ファイルをバックアップ
3. 新しいファイルで上書き
4. `.env` ファイルを元に戻す

---

## まとめ

これで2ch動画生成システムが使えるようになりました！

**基本的な流れ**:
1. ✅ Python・FFmpegをインストール
2. ✅ `setup.py` を実行
3. ✅ `.env` にAPIキーを設定
4. ✅ `python main.py --theme "テーマ" --auto` で動画生成

**わからないことがあれば、いつでもサポートにお問い合わせください！**

良い動画作成を！ 🎬
