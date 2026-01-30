# 2ch/5ch まとめ動画 自動生成システム

YouTubeで人気の「2ch/5chまとめ動画」を全自動で生成するシステムです。
Cursorでのチャット対話型開発に最適化されています。

## 特徴

- **完全自動化**: テーマを入力するだけで、台本→画像→音声→動画を自動生成
- **音声と字幕の完全同期**: MoviePyを使用し、音声の長さに基づいて映像を調整
- **高品質な音声**: OpenAI TTS（複数の声色）を使用
- **柔軟な画像生成**: OpenAI DALL-E 3 または KIEAI API に対応
- **2ch風のリアルなスレッド**: GPT-4によるネットスラング満載の台本生成

## システム構成

```
2ch-video-generator/
├── assets/                 # 静的アセット
│   ├── bgm/               # BGM用の音楽ファイル (.mp3)
│   ├── images/            # 背景画像など
│   └── fonts/             # フォントファイル
├── generated/             # 生成ファイル (自動作成)
│   ├── scripts/           # 台本 (JSON)
│   ├── voices/            # 音声ファイル (.mp3)
│   ├── images/            # 生成された画像 (.png)
│   └── *.mp4              # 最終動画
├── src/                   # ソースコード
│   ├── config.py          # 設定
│   ├── 1_script_gen.py    # 台本生成
│   ├── 2_image_gen.py     # 画像生成
│   ├── 3_voice_gen.py     # 音声生成
│   └── 4_video_edit.py    # 動画編集
├── main.py                # メイン実行ファイル
├── requirements.txt       # Python依存パッケージ
├── .env.example           # 環境変数のサンプル
└── README.md              # このファイル
```

## セットアップ

### 1. 必要なソフトウェア

- Python 3.8 以上
- FFmpeg (MoviePyが使用)

#### FFmpegのインストール

**Windows:**
```bash
# Chocolateyを使う場合
choco install ffmpeg

# または公式サイトからダウンロード
# https://ffmpeg.org/download.html
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt update
sudo apt install ffmpeg
```

### 2. 依存パッケージのインストール

```bash
cd 2ch-video-generator
pip install -r requirements.txt
```

### 3. 環境変数の設定

`.env.example` を `.env` にコピーして、APIキーを設定します。

```bash
cp .env.example .env
```

`.env` ファイルを編集:

```env
# OpenAI API Key (必須: 音声生成と台本生成に使用)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxx

# KIEAI API Key (オプション: 画像生成に使用する場合)
KIEAI_API_KEY=your_kieai_api_key_here
KIEAI_API_URL=https://api.kieai.xyz/generate
```

### 4. アセットの準備

#### 背景画像 (推奨)

`assets/images/background.png` に背景画像を配置してください。
なければ黒背景が使用されます。

推奨サイズ: 1280x720 または 1920x1080

#### BGM (オプション)

`assets/bgm/` フォルダに `.mp3` 形式のBGMを配置してください。
複数ある場合は、最初に見つかったファイルが使用されます。

おすすめフリーBGM:
- [DOVA-SYNDROME](https://dova-s.jp/)
- [魔王魂](https://maou.audio/)

#### フォント (オプション)

日本語字幕を美しく表示するため、フォントファイルを配置できます。

```bash
# 例: Noto Sans JP をダウンロード
# https://fonts.google.com/noto/specimen/Noto+Sans+JP

# ダウンロードしたフォントを配置
# assets/fonts/NotoSansJP-Bold.ttf
```

## 使い方

### 基本的な使い方（全自動生成）

```bash
python main.py --theme "30代で貯金1000万貯めた話" --auto
```

これだけで、台本→画像→音声→動画が自動生成されます！

### オプション

#### 台本のみ生成

```bash
python main.py --theme "株で100万円溶かした話" --script-only
```

生成された台本は `generated/scripts/script.json` に保存されます。
内容を確認・編集してから、次のステップに進むことができます。

#### 既存の台本から動画を生成

```bash
python main.py --generate-video
```

#### 画像生成方法を選択

```bash
# OpenAI DALL-E 3 を使用（デフォルト）
python main.py --theme "FIREを目指す20代の日常" --image-method openai --auto

# KIEAI API を使用
python main.py --theme "億り人になった投資家の話" --image-method kieai --auto
```

#### BGMなしで生成

```bash
python main.py --theme "節約生活の極意" --auto --no-bgm
```

### 個別スクリプトの実行

各ステップを個別に実行することも可能です。

```bash
# 台本生成
cd src
python 1_script_gen.py "テーマ"

# 画像生成
python 2_image_gen.py openai

# 音声生成
python 3_voice_gen.py

# 動画生成
python 4_video_edit.py
```

## Cursorでの使い方

Cursorのチャット機能を使って、対話的に開発・調整できます。

### 例1: 台本の修正

```
あなた: @1_script_gen.py 次の動画のテーマは「20代で投資詐欺にあって借金500万背負った話」で作って。
        面白おかしく、最後は救いがある感じで。

Claude: （台本を生成）

あなた: 借用書の画像のプロンプトをもう少し汚い紙にして。

Claude: （JSONを修正）
```

### 例2: 全自動生成

```
あなた: python main.py --theme "30代独身、貯金ゼロの絶望的な生活" --auto を実行して

Claude: （実行して結果を報告）
```

## トラブルシューティング

### MoviePyでエラーが出る

```
ImageMagickが見つかりません
```

→ ImageMagickをインストールしてください。

```bash
# Windows (Chocolatey)
choco install imagemagick

# macOS
brew install imagemagick

# Linux
sudo apt install imagemagick
```

### フォントエラー

```
Could not find font
```

→ フォントファイルを配置するか、`src/4_video_edit.py` の `font=None` にしてデフォルトフォントを使用してください。

### OpenAI API のレート制限

大量の音声・画像を生成すると、APIのレート制限に引っかかる場合があります。
その場合は、少し時間をおいて再実行してください。

## カスタマイズ

### 音声の声色を変更

`src/config.py` の `VOICE_MAPPING` を編集:

```python
VOICE_MAPPING = {
    "narrator": "shimmer",  # ナレーター
    "icchi": "alloy",       # スレ主
    "res_A": "echo",        # スレ民A
    "res_B": "fable",       # スレ民B
    "res_C": "onyx",        # スレ民C
}
```

利用可能な声: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

### 動画サイズの変更

`src/config.py` の `DEFAULT_VIDEO_SIZE` を編集:

```python
DEFAULT_VIDEO_SIZE = (1920, 1080)  # フルHD
```

### BGM音量の調整

`src/config.py` の `DEFAULT_BGM_VOLUME` を編集:

```python
DEFAULT_BGM_VOLUME = 0.05  # 小さく
```

## コスト目安

### OpenAI API

- **台本生成**: ~$0.02 / 動画
- **音声生成**: ~$0.30 / 動画（20シーンの場合）
- **画像生成 (DALL-E 3)**: ~$0.40 / 画像

1本の動画（5枚の画像を含む）で約 **$2.5〜$3** 程度です。

## ライセンス

MIT License

## 参考リンク

- [OpenAI API Documentation](https://platform.openai.com/docs/)
- [MoviePy Documentation](https://zulko.github.io/moviepy/)
- [DOVA-SYNDROME (フリーBGM)](https://dova-s.jp/)

## 貢献

プルリクエスト歓迎！

## お問い合わせ

問題が発生した場合は、Issueを作成してください。
