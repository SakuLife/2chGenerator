# クイックスタートガイド

5分で動画を作成！

## ステップ1: セットアップ

```bash
# 1. 依存パッケージをインストール
python setup.py

# 2. .env ファイルを作成
copy .env.example .env  # Windows
cp .env.example .env    # Mac/Linux

# 3. .env を編集してOpenAI APIキーを設定
# OPENAI_API_KEY=sk-proj-xxxxxxxxxx
```

## ステップ2: 動画生成

```bash
# テーマを指定して全自動生成
python main.py --theme "30代で貯金1000万貯めた話" --auto
```

これだけ！

## 生成される動画の場所

```
generated/output_video.mp4
```

## よくある質問

### Q. FFmpegがないと言われる

A. FFmpegをインストールしてください。

```bash
# Windows (Chocolateyが必要)
choco install ffmpeg

# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg
```

### Q. OpenAI APIキーの取得方法は？

A. https://platform.openai.com/api-keys にアクセスして、新しいAPIキーを作成してください。

### Q. コストはどれくらい？

A. 1本の動画（画像5枚含む）で約$2.5〜$3です。
- 台本生成: ~$0.02
- 音声生成: ~$0.30
- 画像生成: ~$0.40/枚

### Q. 生成された台本を編集したい

A. まず台本のみ生成：

```bash
python main.py --theme "テーマ" --script-only
```

`generated/scripts/script.json` を編集後、動画生成：

```bash
python main.py --generate-video
```

### Q. BGMを追加したい

A. `assets/bgm/` フォルダに `.mp3` ファイルを配置してください。

おすすめ: [DOVA-SYNDROME](https://dova-s.jp/)

## Cursorでの使い方

Cursorのチャットで以下のように指示するだけ！

```
「30代独身、貯金ゼロの絶望的な生活」というテーマで2ch風の動画を作って
```

Claude Codeが自動的にコマンドを実行して動画を生成します。

## 次のステップ

詳しい使い方は [README.md](README.md) を参照してください。
