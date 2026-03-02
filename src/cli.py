"""
CLI Entry Point

Main command-line interface for the channel network.
All operations are accessible via: python -m src.cli <command>
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_env():
    """Load environment variables from .env file."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        import os
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


def cmd_daily(args):
    """Run daily pipeline for all channels."""
    from src.ops.daily import DailyRunner
    runner = DailyRunner()
    runner.run_daily(dry_run=args.dry_run)


def cmd_ingest(args):
    """Ingest from a specific source."""
    from src.core.config import ConfigLoader
    from src.core.models import Source, SourceType
    from src.core.registry import PluginRegistry

    config = ConfigLoader()

    source = Source(
        id=args.source_id or "cli-source",
        source_type=SourceType(args.type),
        url=args.url,
    )

    ingester = PluginRegistry.create("ingester", args.type)
    items = ingester.fetch_latest(source, max_items=args.count)

    for item in items:
        print(f"\n{'─' * 40}")
        print(f"📄 {item.title}")
        print(f"🔗 {item.url}")
        if item.published_at:
            print(f"📅 {item.published_at.strftime('%Y-%m-%d')}")
        print(f"📏 {len(item.content)} characters")
        if args.show_content:
            print(f"\n{item.content[:500]}...")


def cmd_prepare(args):
    """Prepare sources for agent composition."""
    from src.compose.prepare import SourcePreparer
    preparer = SourcePreparer()
    brief_path = preparer.prepare(args.channel, max_sources=args.count)
    print(f"\n  📋 Brief ready for agent composition: {brief_path}")
    print(f"  💡 Read the brief, compose the piece, save to:")
    print(f"     data/output/{args.channel}/{brief_path.parent.name}/draft.md")


def cmd_verify(args):
    """Verify composed content against guidelines."""
    from pathlib import Path
    from src.verify.checker import ContentChecker
    from src.verify.stats import ContentStats

    path = Path(args.path)
    if not path.exists():
        print(f"❌ File not found: {path}")
        return

    content = path.read_text()
    channel = args.channel or path.parent.parent.name

    # Run quality checks
    checker = ContentChecker()
    report = checker.check(content, channel)
    checker.print_report(report)

    # Run statistics
    stats_obj = ContentStats()
    stats = stats_obj.analyze(content, channel)
    stats_obj.print_stats(stats)

    # Record stats for tracking
    stats_obj.record(stats)


def cmd_publish(args):
    """Publish a completed piece to its channel."""
    import uuid
    from pathlib import Path
    from src.core.config import ConfigLoader
    from src.core.models import ContentPiece, Platform
    from src.core.registry import PluginRegistry

    config = ConfigLoader()
    channel_config = config.load_channel(args.channel)
    publisher_name = channel_config["publish"]["plugin"]
    publisher = PluginRegistry.create("publisher", publisher_name)

    if not publisher.validate_credentials():
        print(f"❌ {publisher_name} credentials not configured")
        print(f"   Set up your credentials in .env")
        return

    video_path = getattr(args, "video", None)
    audio_path = getattr(args, "audio", None)

    if not video_path and not audio_path:
        print(f"❌ Provide --video or --audio path")
        return

    media_path = Path(video_path or audio_path)
    if not media_path.exists():
        print(f"❌ File not found: {media_path}")
        return

    # Auto-detect title/subtitle from draft.md in same directory
    draft_path = media_path.parent / "draft.md"
    title = "Untitled"
    subtitle = ""
    if draft_path.exists():
        for line in draft_path.read_text().split("\n")[:10]:
            line = line.strip()
            if line.startswith("# ") and not line.startswith("## "):
                title = line[2:].strip()
            elif title != "Untitled" and line and not line.startswith("#"):
                subtitle = line.strip("*").strip()
                break

    print(f"\n{'═' * 60}")
    print(f"  📤 Publishing to {channel_config['name']}")
    print(f"{'═' * 60}")
    print(f"  📹 Video: {media_path} ({media_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  📝 Title: {title}")
    print(f"  📄 Subtitle: {subtitle}")

    # Crop bottom 10% + trim last 3 seconds (removes NotebookLM watermark + outro)
    if video_path:
        import subprocess
        cropped_path = media_path.parent / "video_cropped.mp4"
        if not cropped_path.exists():
            # Get video duration
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(media_path)],
                capture_output=True, text=True,
            )
            duration = float(probe.stdout.strip())
            trimmed_duration = max(duration - 3.0, 1.0)

            print(f"  ✂️  Cropping bottom 10% + trimming last 3s ({duration:.1f}s → {trimmed_duration:.1f}s)...")
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(media_path),
                 "-t", str(trimmed_duration),
                 "-vf", "crop=in_w:in_h*0.90:0:0,scale=1280:720",
                 "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                 "-c:a", "copy", str(cropped_path)],
                capture_output=True,
            )
            if cropped_path.exists():
                # Replace original with processed version
                media_path.unlink()
                cropped_path.rename(media_path)
                print(f"  ✅ Processed: {media_path} ({media_path.stat().st_size / 1024 / 1024:.1f} MB)")
            else:
                print(f"  ⚠️  Processing failed, using original")

    # Auto-extract thumbnail from video with ffmpeg (5s in, past fade-in)
    thumbnail_path = media_path.parent / "thumbnail.jpg"
    if video_path and not thumbnail_path.exists():
        import subprocess
        print(f"  🖼️  Extracting thumbnail at 5s...")
        subprocess.run(
            ["ffmpeg", "-ss", "5", "-i", str(media_path),
             "-vframes", "1", "-update", "1", "-q:v", "2",
             str(thumbnail_path)],
            capture_output=True,
        )
        if thumbnail_path.exists():
            print(f"  ✅ Thumbnail: {thumbnail_path}")
        else:
            print(f"  ⚠️  Thumbnail extraction failed")

    # Load draft content for description generation
    draft_content = ""
    if draft_path.exists():
        draft_content = draft_path.read_text()

    # Load source items from the sources directory
    from src.core.models import SourceItem
    source_items = []
    sources_dir = Path("data/sources") / args.channel
    if sources_dir.exists():
        # Get the most recent date directory
        date_dirs = sorted(sources_dir.iterdir(), reverse=True)
        if date_dirs:
            for sf in sorted(date_dirs[0].glob("source_*.md")):
                src_text = sf.read_text()
                src_title = src_text.split("\n")[0].lstrip("# ").strip()
                src_url = ""
                for sline in src_text.split("\n"):
                    if sline.startswith("**URL:**"):
                        src_url = sline.replace("**URL:**", "").strip()
                    elif sline.startswith("**Source:**"):
                        src_id = sline.replace("**Source:**", "").strip()
                source_items.append(SourceItem(
                    title=src_title, url=src_url, source_id=src_id,
                    content="",
                ))

    piece = ContentPiece(
        id=str(uuid.uuid4()),
        channel_slug=args.channel,
        title=title,
        subtitle=subtitle,
        draft_content=draft_content,
        video_path=str(video_path) if video_path else None,
        audio_path=str(audio_path) if audio_path else None,
        image_path=str(thumbnail_path) if thumbnail_path.exists() else None,
        source_items=source_items,
    )

    record = publisher.publish(piece)
    if record:
        print(f"  ✅ Published: {record.publish_url}")
    else:
        print(f"  ❌ Publishing failed")


def cmd_channels(args):
    """List all configured channels."""
    from src.core.config import ConfigLoader
    config = ConfigLoader()
    channels = config.load_all_channels()

    print(f"\n{'═' * 70}")
    print(f"  LLUMINATE NETWORK — {len(channels)} Channels")
    print(f"{'═' * 70}\n")

    for slug, ch in channels.items():
        platform = ch.get("platform", "?").upper()
        format_plugin = ch.get("format", {}).get("plugin", "?")
        sources = ch.get("sources", {}).get("primary", [])
        source_names = [s.get("id", "?") for s in sources]

        print(f"  📺 {ch['name']}")
        print(f"     Slug: {slug}")
        print(f"     Platform: {platform} | Format: {format_plugin}")
        print(f"     Sources: {', '.join(source_names)}")
        print()


def cmd_status(args):
    """Show pipeline status for all channels."""
    from src.core.config import ConfigLoader
    from src.core.database import Database

    config = ConfigLoader()
    db = Database()
    channels = config.load_all_channels()

    print(f"\n{'═' * 60}")
    print(f"  PIPELINE STATUS")
    print(f"{'═' * 60}\n")

    for slug, ch in channels.items():
        today_count = db.get_channel_publish_count(slug)
        pending = db.get_pending_pieces(slug)

        status = "✅" if today_count > 0 else ("⏳" if pending else "⬜")
        print(f"  {status} {ch['name']}: {today_count} published today, {len(pending)} pending")


def cmd_engage(args):
    """Auto-reply to comments across channels."""
    from src.engage.responder import AutoResponder
    responder = AutoResponder()

    channel = args.channel if hasattr(args, "channel") and args.channel else None
    results = responder.process_all_comments(
        channel_slug=channel, dry_run=args.dry_run
    )

    print(f"\n{'═' * 60}")
    print(f"  ENGAGEMENT SUMMARY")
    print(f"{'═' * 60}")
    print(f"  💬 Comments processed: {len(results)}")
    print(f"  ✅ Replies posted: {sum(1 for r in results if r['posted'])}")
    if args.dry_run:
        print(f"  🧪 (dry run — no replies posted)")
    print()


def cmd_feedback(args):
    """View and manage audience feedback."""
    from src.engage.feedback import FeedbackLoop
    feedback = FeedbackLoop()

    if args.extract:
        # Extract feedback from recent comments
        from src.engage.monitor import CommentMonitor
        monitor = CommentMonitor()
        channel = args.channel if hasattr(args, "channel") and args.channel else None
        comments = monitor.fetch_new_comments(channel)
        if comments:
            channels_seen = set()
            for c in comments:
                if c["channel_slug"] not in channels_seen:
                    channel_comments = [
                        x for x in comments
                        if x["channel_slug"] == c["channel_slug"]
                    ]
                    items = feedback.extract_feedback(
                        channel_comments, c["channel_slug"]
                    )
                    channels_seen.add(c["channel_slug"])
                    print(f"\n  📊 {c['channel_slug']}: {len(items)} feedback items extracted")
        else:
            print("  No comments found to extract feedback from")
    else:
        # Show feedback summary
        channel = args.channel if hasattr(args, "channel") and args.channel else None
        summary = feedback.get_feedback_summary(channel)
        print(f"\n{'═' * 60}")
        print(f"  AUDIENCE FEEDBACK")
        print(f"{'═' * 60}")
        print(f"  📊 Total feedback items: {summary['total_feedback']}")
        print(f"  ⏳ Pending (not yet incorporated): {summary['pending']}")
        print(f"  ✅ Incorporated into content: {summary['incorporated']}")

        if channel:
            context = feedback.get_channel_feedback_context(channel)
            if context:
                print(f"\n  Current feedback context for {channel}:")
                print(context)
        print()


def cmd_chart(args):
    """Graphyard chart tools."""
    from pathlib import Path
    from src.charts import GraphyardDB, ChartBuilder, ChartSpec, ChartType

    db = GraphyardDB.from_env()
    subcmd = getattr(args, "chart_command", None)

    if subcmd == "schemas":
        if not db.test_connection():
            print("❌ Cannot connect to graphyard database")
            return

        schemas = db.list_schemas()
        print(f"\n{'═' * 50}")
        print(f"  GRAPHYARD SCHEMAS — {len(schemas)} found")
        print(f"{'═' * 50}\n")
        for s in schemas:
            tables = db.list_tables(s)
            print(f"  📁 {s} ({len(tables)} tables)")

    elif subcmd == "tables":
        schema = args.schema
        if not db.test_connection():
            print("❌ Cannot connect to graphyard database")
            return

        tables = db.list_tables(schema)
        print(f"\n{'═' * 50}")
        print(f"  TABLES IN {schema} — {len(tables)} found")
        print(f"{'═' * 50}\n")
        for t in tables:
            rows = t.get("row_estimate", "?")
            print(f"  📊 {t['table_name']:40s} ~{rows:>10} rows")

    elif subcmd == "query":
        if not db.test_connection():
            print("❌ Cannot connect to graphyard database")
            return

        sql = args.sql
        limit = args.limit
        # Add LIMIT if not present
        if "limit" not in sql.lower():
            sql += f" LIMIT {limit}"

        df = db.query(sql)
        print(f"\n  📊 {len(df)} rows returned\n")
        print(df)

    elif subcmd == "test":
        if not db.test_connection():
            print("❌ Cannot connect to graphyard database")
            return

        theme = args.theme
        output_dir = Path("data/output/test-charts")
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'═' * 60}")
        print(f"  GENERATING TEST CHARTS (theme: {theme})")
        print(f"{'═' * 60}\n")

        builder = ChartBuilder(theme=theme)

        # Test 1: Line chart — World GDP trend
        print("  📈 Test 1: World GDP trend (line chart)...")
        try:
            df = db.query("""
                SELECT year, value / 1e12 as value_trillions
                FROM public.world_data
                WHERE indicator_code = 'NY.GDP.MKTP.CD'
                  AND year BETWEEN 1960 AND 2023
                  AND value IS NOT NULL
                ORDER BY year
            """)
            if len(df) > 0:
                chart = builder.line(
                    df, x="year", y="value_trillions",
                    title="World GDP Over Time",
                    y_label="GDP (Trillions USD)",
                    x_label="Year",
                    source_note="World Bank WDI",
                )
                paths = builder.save(chart, output_dir / "test_line_world_gdp")
                print(f"     ✅ Saved: {', '.join(str(p) for p in paths)}")
            else:
                print("     ⚠️  No data returned for world GDP query")
        except Exception as e:
            print(f"     ❌ Failed: {e}")

        # Test 2: Bar chart — Top economies
        print("  📊 Test 2: Top 10 economies (horizontal bar)...")
        try:
            df = db.query("""
                SELECT e.entity_name, d.value / 1e12 as gdp_trillions
                FROM public.country_data d
                JOIN public.entities e ON d.entity_code = e.entity_code
                WHERE d.indicator_code = 'NY.GDP.MKTP.CD'
                  AND d.year = 2022
                  AND d.value IS NOT NULL
                ORDER BY d.value DESC
                LIMIT 10
            """)
            if len(df) > 0:
                chart = builder.horizontal_bar(
                    df, x="gdp_trillions", y="entity_name",
                    title="World's Largest Economies (2022)",
                    x_label="GDP (Trillions USD)",
                    source_note="World Bank WDI",
                )
                paths = builder.save(chart, output_dir / "test_hbar_top_economies")
                print(f"     ✅ Saved: {', '.join(str(p) for p in paths)}")
            else:
                print("     ⚠️  No data returned for top economies query")
        except Exception as e:
            print(f"     ❌ Failed: {e}")

        # Test 3: Multi-line — Country comparison
        print("  📈 Test 3: US vs China GDP comparison (multi-line)...")
        try:
            df = db.query("""
                SELECT e.entity_name as country, d.year,
                       d.value / 1e12 as gdp_trillions
                FROM public.country_data d
                JOIN public.entities e ON d.entity_code = e.entity_code
                WHERE d.indicator_code = 'NY.GDP.MKTP.CD'
                  AND d.entity_code IN ('USA', 'CHN')
                  AND d.year BETWEEN 1990 AND 2023
                  AND d.value IS NOT NULL
                ORDER BY d.year
            """)
            if len(df) > 0:
                chart = builder.line(
                    df, x="year", y="gdp_trillions", color="country",
                    title="US vs China: GDP Over Time",
                    y_label="GDP (Trillions USD)",
                    x_label="Year",
                    source_note="World Bank WDI",
                )
                paths = builder.save(chart, output_dir / "test_line_us_china")
                print(f"     ✅ Saved: {', '.join(str(p) for p in paths)}")
            else:
                print("     ⚠️  No data returned for US/China comparison")
        except Exception as e:
            print(f"     ❌ Failed: {e}")

        # Test 4: Bar with negative values — GDP growth
        print("  📊 Test 4: World GDP growth rate (bar with negatives)...")
        try:
            df = db.query("""
                SELECT year, value as growth_rate
                FROM public.world_data
                WHERE indicator_code = 'NY.GDP.MKTP.KD.ZG'
                  AND year BETWEEN 2000 AND 2023
                  AND value IS NOT NULL
                ORDER BY year
            """)
            if len(df) > 0:
                chart = builder.bar(
                    df, x="year", y="growth_rate",
                    title="World GDP Growth Rate",
                    y_label="Annual Growth (%)",
                    x_label="Year",
                    highlight_negative=True,
                    source_note="World Bank WDI",
                )
                paths = builder.save(chart, output_dir / "test_bar_gdp_growth")
                print(f"     ✅ Saved: {', '.join(str(p) for p in paths)}")
            else:
                print("     ⚠️  No data returned for GDP growth query")
        except Exception as e:
            print(f"     ❌ Failed: {e}")

        print(f"\n  📂 Output: {output_dir.resolve()}")

    else:
        print("Usage: python -m src.cli chart {schemas|tables|query|test}")
        print()
        print("  schemas           List all graphyard database schemas")
        print("  tables [schema]   List tables in a schema (default: public)")
        print("  query \"SQL\"       Run a query and display results")
        print("  test [--theme T]  Generate throwaway test charts")


def main():
    load_env()

    parser = argparse.ArgumentParser(
        description="Lluminate Network — Multi-Channel Content Pipeline"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # daily
    daily_parser = subparsers.add_parser("daily", help="Run daily pipeline")
    daily_parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    daily_parser.set_defaults(func=cmd_daily)

    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest from a source")
    ingest_parser.add_argument("type", choices=["youtube", "substack", "web"])
    ingest_parser.add_argument("--url", required=True)
    ingest_parser.add_argument("--source-id", default=None)
    ingest_parser.add_argument("--count", type=int, default=3)
    ingest_parser.add_argument("--show-content", action="store_true")
    ingest_parser.set_defaults(func=cmd_ingest)

    # prepare
    prepare_parser = subparsers.add_parser("prepare", help="Prepare sources for agent composition")
    prepare_parser.add_argument("channel", help="Channel slug")
    prepare_parser.add_argument("--count", type=int, default=3, help="Max sources to gather")
    prepare_parser.set_defaults(func=cmd_prepare)

    # verify
    verify_parser = subparsers.add_parser("verify", help="Verify composed content quality")
    verify_parser.add_argument("path", help="Path to draft.md file")
    verify_parser.add_argument("--channel", help="Channel slug (auto-detected from path)")
    verify_parser.set_defaults(func=cmd_verify)

    # publish
    publish_parser = subparsers.add_parser("publish", help="Publish to a channel")
    publish_parser.add_argument("channel", help="Channel slug")
    publish_parser.add_argument("--video", help="Path to video file")
    publish_parser.add_argument("--audio", help="Path to audio file")
    publish_parser.set_defaults(func=cmd_publish)

    # channels
    channels_parser = subparsers.add_parser("channels", help="List all channels")
    channels_parser.set_defaults(func=cmd_channels)

    # status
    status_parser = subparsers.add_parser("status", help="Show pipeline status")
    status_parser.set_defaults(func=cmd_status)

    # engage
    engage_parser = subparsers.add_parser("engage", help="Auto-reply to comments")
    engage_parser.add_argument("--channel", help="Specific channel slug (default: all)")
    engage_parser.add_argument("--dry-run", action="store_true", help="Preview replies without posting")
    engage_parser.set_defaults(func=cmd_engage)

    # feedback
    feedback_parser = subparsers.add_parser("feedback", help="View/extract audience feedback")
    feedback_parser.add_argument("--channel", help="Specific channel slug")
    feedback_parser.add_argument("--extract", action="store_true", help="Extract feedback from recent comments")
    feedback_parser.set_defaults(func=cmd_feedback)

    # chart
    chart_parser = subparsers.add_parser("chart", help="Graphyard chart tools")
    chart_sub = chart_parser.add_subparsers(dest="chart_command", help="Chart subcommands")

    chart_schemas = chart_sub.add_parser("schemas", help="List graphyard schemas")
    chart_schemas.set_defaults(func=cmd_chart)

    chart_tables = chart_sub.add_parser("tables", help="List tables in a schema")
    chart_tables.add_argument("schema", nargs="?", default="public", help="Schema name")
    chart_tables.set_defaults(func=cmd_chart)

    chart_query = chart_sub.add_parser("query", help="Run a SQL query and display results")
    chart_query.add_argument("sql", help="SQL query to execute")
    chart_query.add_argument("--limit", type=int, default=20, help="Max rows to display")
    chart_query.set_defaults(func=cmd_chart)

    chart_test = chart_sub.add_parser("test", help="Generate throwaway test charts")
    chart_test.add_argument("--theme", default="publication", help="Chart theme")
    chart_test.set_defaults(func=cmd_chart)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    # Discover plugins before executing commands
    from src.core.registry import discover_plugins
    try:
        discover_plugins()
    except ImportError:
        pass  # Some plugins may not have all dependencies yet

    args.func(args)


if __name__ == "__main__":
    main()
