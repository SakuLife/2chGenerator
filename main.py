"""
2ch/5ch まとめ動画自動生成システム
メインエントリーポイント
"""

import argparse
import importlib.util
import sys
import time
from pathlib import Path

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import (
    SCRIPTS_DIR,
    GENERATED_DIR,
    YOUTUBE_API_KEY,
    GOOGLE_SHEETS_ID,
    GOOGLE_SERVICE_ACCOUNT,
    GOOGLE_CLIENT_SECRETS_FILE,
    ensure_directories,
)
from src.logger import logger, setup_logger

# 数字で始まるモジュール名を直接インポート
src_dir = Path(__file__).parent / "src"


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, src_dir / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script_gen = load_module("script_gen", "1_script_gen.py")
image_gen = load_module("image_gen", "2_image_gen.py")
voice_gen = load_module("voice_gen", "3_voice_gen.py")
video_edit = load_module("video_edit", "4_video_edit.py")


def main():
    parser = argparse.ArgumentParser(
        description="2ch/5ch まとめ動画自動生成システム",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 全自動生成（台本→画像→音声→動画）
  python main.py --theme "30代で貯金1000万貯めた話" --auto

  # テーマ提案を受けてから生成
  python main.py --suggest-themes
  python main.py --theme "提案されたテーマ" --auto

  # 台本のみ生成
  python main.py --theme "株で100万円溶かした話" --script-only

  # 既存の台本から動画を生成
  python main.py --generate-video

  # 動画統計を更新
  python main.py --update-stats
        """,
    )

    parser.add_argument(
        "--theme", type=str, help="動画のテーマ（例：「30代で貯金1000万貯めた話」）"
    )

    parser.add_argument(
        "--auto", action="store_true", help="全自動モード（台本→画像→音声→動画を一括生成）"
    )

    parser.add_argument("--script-only", action="store_true", help="台本のみ生成")

    parser.add_argument(
        "--image-method",
        type=str,
        choices=["kieai", "openai"],
        default="kieai",
        help="画像生成方法（デフォルト: kieai）",
    )

    parser.add_argument(
        "--generate-video", action="store_true", help="既存の台本・音声・画像から動画を生成"
    )

    parser.add_argument("--no-bgm", action="store_true", help="BGMなしで動画を生成")

    parser.add_argument(
        "--no-images", action="store_true", help="画像生成をスキップ（画像なしで動画を生成）"
    )

    parser.add_argument("--debug", action="store_true", help="デバッグモードを有効にする")

    # 新機能
    parser.add_argument(
        "--suggest-themes",
        action="store_true",
        help="YouTube分析に基づいてテーマを提案",
    )

    parser.add_argument(
        "--update-stats",
        action="store_true",
        help="記録済み動画の再生数を更新",
    )

    parser.add_argument(
        "--record",
        action="store_true",
        help="生成完了後にスプレッドシートに記録",
    )

    parser.add_argument(
        "--upload",
        action="store_true",
        help="生成後にYouTubeへアップロード（18:00 JST予約投稿）",
    )

    parser.add_argument(
        "--upload-now",
        action="store_true",
        help="生成後にYouTubeへ即時公開アップロード",
    )

    parser.add_argument(
        "--publish-hour",
        type=int,
        choices=[6, 18],
        help="予約投稿時刻（JST）: 6 or 18",
    )

    args = parser.parse_args()

    # ロガーを再設定（デバッグモード対応）
    if args.debug:
        log_file = GENERATED_DIR / "logs" / "video_gen.log"
        setup_logger(debug=True, log_file=log_file)

    # ディレクトリを確認
    ensure_directories()

    logger.info("=" * 60)
    logger.info("  2ch/5ch まとめ動画自動生成システム")
    logger.info("=" * 60)

    # テーマ提案モード
    if args.suggest_themes:
        from src.theme_suggester import ThemeSuggester

        logger.info("[モード] テーマ提案")

        suggester = ThemeSuggester(
            youtube_api_key=YOUTUBE_API_KEY,
            spreadsheet_id=GOOGLE_SHEETS_ID,
        )

        themes = suggester.suggest_themes(
            use_competitor_analysis=bool(YOUTUBE_API_KEY),
            use_my_channel=True,
            use_trending=bool(YOUTUBE_API_KEY),
            count=10,
        )

        logger.info("\n【提案テーマ】")
        for i, theme in enumerate(themes, 1):
            logger.info(f"  {i}. {theme}")

        logger.info("\n使用例:")
        if themes:
            logger.info(f'  python main.py --theme "{themes[0]}" --auto')

        return

    # 統計更新モード
    if args.update_stats:
        if not GOOGLE_SHEETS_ID:
            logger.error("エラー: GOOGLE_SHEETS_ID を設定してください")
            sys.exit(1)

        from src.video_tracker import VideoTracker

        logger.info("[モード] 統計更新")

        tracker = VideoTracker(
            spreadsheet_id=GOOGLE_SHEETS_ID,
            youtube_api_key=YOUTUBE_API_KEY,
        )

        updated = tracker.update_video_stats()
        logger.info(f"更新完了: {updated}件")

        # レポート表示
        report = tracker.get_performance_report()
        logger.info("\n【パフォーマンスレポート】")
        logger.info(f"  総動画数: {report['total_videos']}")
        logger.info(f"  総再生回数: {report.get('total_views', 0):,}")
        logger.info(f"  平均再生回数: {report.get('avg_views_per_video', 0):,.0f}")

        return

    # 動画生成のみモード
    if args.generate_video:
        logger.info("[モード] 動画生成のみ")
        script_path = SCRIPTS_DIR / "script.json"

        if not script_path.exists():
            logger.error(f"エラー: 台本ファイルが見つかりません: {script_path}")
            logger.error("先に台本を生成してください。")
            sys.exit(1)

        logger.info("Step 4/4: 動画生成中...")
        video_edit.create_video_from_script(script_path, use_bgm=not args.no_bgm)
        return

    # 台本のみモード
    if args.script_only:
        if not args.theme:
            logger.error("エラー: --theme を指定してください")
            sys.exit(1)

        logger.info(f"[モード] 台本生成のみ")
        logger.info(f"テーマ: {args.theme}")

        logger.info("Step 1/1: 台本生成中...")
        script_gen.generate_script(args.theme)
        logger.info("台本生成完了！")
        return

    # 全自動モード
    if args.auto:
        if not args.theme:
            logger.error("エラー: --theme を指定してください")
            sys.exit(1)

        start_time = time.time()
        step_times = {}
        gemini_tokens = 0
        gemini_cost_jpy = 0.0
        kieai_credits = 0
        scene_count = 0
        image_count = 0

        logger.info(f"[モード] 全自動生成")
        logger.info(f"テーマ: {args.theme}")
        if args.no_images:
            logger.info(f"画像生成: スキップ（画像なし）")
        else:
            logger.info(f"画像生成: {args.image_method.upper()}")

        # Step 1: 台本生成
        logger.info("=" * 60)
        logger.info("Step 1/4: 台本生成中...")
        logger.info("=" * 60)
        t0 = time.time()
        script_result = script_gen.generate_script(args.theme)
        step_times["script"] = time.time() - t0

        # generate_script() は dict を返す
        script_data = script_result["script"]
        gemini_tokens += script_result.get("gemini_tokens", 0)
        gemini_cost_jpy += script_result.get("gemini_cost_jpy", 0)
        scene_count = len(script_data)
        script_path = SCRIPTS_DIR / "script.json"

        # Step 2: 画像生成（スキップ可能）
        if not args.no_images:
            logger.info("=" * 60)
            logger.info("Step 2/4: 画像生成中...")
            logger.info("=" * 60)
            t0 = time.time()
            image_result = image_gen.generate_images_from_script(
                script_path, method=args.image_method
            )
            step_times["image"] = time.time() - t0
            image_count = image_result.get("image_count", 0)
            kieai_credits += image_result.get("kieai_credits", 0)
        else:
            logger.info("=" * 60)
            logger.info("Step 2/4: 画像生成をスキップしました")
            logger.info("=" * 60)

        # Step 3: 音声生成
        logger.info("=" * 60)
        logger.info("Step 3/4: 音声生成中...")
        logger.info("=" * 60)
        t0 = time.time()
        voice_gen.generate_voices_from_script(script_path)
        step_times["voice"] = time.time() - t0

        # Step 4: 動画生成
        logger.info("=" * 60)
        logger.info("Step 4/4: 動画生成中...")
        logger.info("=" * 60)
        output_path = video_edit.create_video_from_script(
            script_path, use_bgm=not args.no_bgm
        )

        generation_time = time.time() - start_time

        logger.info("=" * 60)
        logger.info("  全自動生成完了！")
        logger.info("=" * 60)
        logger.info(f"動画ファイル: {output_path}")
        logger.info(f"生成時間: {generation_time / 60:.1f}分")
        logger.info(f"Geminiトークン: {gemini_tokens:,} (¥{gemini_cost_jpy:.2f})")
        logger.info(f"KieAIクレジット: {kieai_credits}")

        # サムネイル生成（毎回実行）
        thumbnail_path = None
        logger.info("=" * 60)
        logger.info("  サムネイル生成中...")
        logger.info("=" * 60)
        try:
            from src.thumbnail_gen import generate_thumbnail

            thumb_result = generate_thumbnail(args.theme, script_path=script_path)
            thumbnail_path = thumb_result["path"]
            kieai_credits += thumb_result.get("kieai_credits", 0)
            logger.info(f"サムネイル: {thumbnail_path}")
        except Exception as e:
            logger.warning(f"サムネイル生成スキップ: {e}")

        # YouTubeアップロード
        youtube_url = None
        if args.upload or args.upload_now:
            from src.youtube_uploader import upload_to_youtube

            logger.info("=" * 60)
            logger.info("  YouTubeアップロード中...")
            logger.info("=" * 60)

            try:
                yt_result = upload_to_youtube(
                    video_path=output_path,
                    theme=args.theme,
                    script_path=script_path,
                    scheduled=not args.upload_now,
                    thumbnail_path=thumbnail_path,
                    publish_hour=args.publish_hour,
                )
                youtube_url = yt_result["url"]
                logger.info(f"YouTube: {youtube_url} ({yt_result['status']})")
            except Exception as e:
                logger.error(f"YouTubeアップロードエラー: {e}")

        # 記録オプション
        if args.record and GOOGLE_SHEETS_ID:
            from src.video_tracker import VideoTracker

            logger.info("\nスプレッドシートに記録中...")

            tracker = VideoTracker(
                spreadsheet_id=GOOGLE_SHEETS_ID,
                youtube_api_key=YOUTUBE_API_KEY,
                client_secrets_file=GOOGLE_CLIENT_SECRETS_FILE,
            )

            # 動画の長さを取得（subtitles.jsonから）
            import json

            subtitles_path = GENERATED_DIR / "voices" / "subtitles.json"
            video_duration = 0
            if subtitles_path.exists():
                with open(subtitles_path, "r", encoding="utf-8") as f:
                    subtitles_data = json.load(f)
                    video_duration = subtitles_data.get("total_duration", 0)

            tracker.record_video(
                theme=args.theme,
                video_path=output_path,
                video_duration=video_duration,
                generation_time=generation_time,
                youtube_url=youtube_url,
                gemini_tokens=gemini_tokens,
                gemini_cost_jpy=gemini_cost_jpy,
                kieai_credits=kieai_credits,
                scene_count=scene_count,
                image_count=image_count,
                step_times=step_times,
            )

            logger.info("記録完了！")

        return

    # 引数なし：ヘルプ表示
    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    main()
