"""
Direct YouTube Upload

Uploads a video directly to YouTube via OAuth, bypassing the DB-tracked
content pipeline. Used when the agent composes content directly.

Usage:
    python scripts/upload_youtube.py <channel-slug> <video-path> [--title TITLE] [--description DESC]
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import ConfigLoader


def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


def get_youtube_service(channel_slug: str):
    """Get authenticated YouTube API service."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    token_path = Path(__file__).parent.parent / "tokens" / f"youtube_{channel_slug}.json"

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            client_config = {
                "installed": {
                    "client_id": os.environ["YOUTUBE_CLIENT_ID"],
                    "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def extract_title_subtitle(draft_path: Path) -> tuple[str, str]:
    """Extract title and subtitle from a draft.md file."""
    if not draft_path.exists():
        return "Untitled", ""

    content = draft_path.read_text()
    lines = content.strip().split("\n")
    title = "Untitled"
    subtitle = ""

    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip()
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith("#"):
                    if next_line.startswith("**") and next_line.endswith("**"):
                        subtitle = next_line.strip("*").strip()
                    elif len(next_line) < 200:
                        subtitle = next_line
                    break
            break

    return title, subtitle


def main():
    parser = argparse.ArgumentParser(description="Upload video to YouTube")
    parser.add_argument("channel", help="Channel slug")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--title", help="Video title (auto-detected from draft.md)")
    parser.add_argument("--description", help="Video description")
    parser.add_argument("--thumbnail", help="Path to thumbnail image")
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded")
    args = parser.parse_args()

    load_env()

    config = ConfigLoader()
    channel_config = config.load_channel(args.channel)

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"❌ Video not found: {video_path}")
        sys.exit(1)

    # Auto-detect title from draft.md in same directory
    draft_path = video_path.parent / "draft.md"
    title, subtitle = extract_title_subtitle(draft_path)

    if args.title:
        title = args.title

    description = args.description or subtitle
    description += f"\n\nPart of the Lluminate Network — {channel_config['name']}"

    # Tags
    tags = ["analysis", "commentary", channel_config["name"].lower()]

    print(f"\n{'═' * 60}")
    print(f"  YouTube Upload — {channel_config['name']}")
    print(f"{'═' * 60}")
    print(f"  📹 Video: {video_path} ({video_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  📝 Title: {title}")
    print(f"  📄 Description: {description[:100]}...")
    print(f"  🔒 Privacy: {args.privacy}")
    print(f"  🏷️  Tags: {', '.join(tags)}")

    if args.dry_run:
        print(f"\n  🏃 DRY RUN — would upload to channel {channel_config['name']}")
        return

    print(f"\n  ⬆️  Uploading...")

    service = get_youtube_service(args.channel)

    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "categoryId": "25",  # News & Politics
            "tags": tags[:30],
        },
        "status": {
            "privacyStatus": args.privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5,  # 5MB chunks
    )

    request = service.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  ⬆️  Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"\n  ✅ Published: {url}")

    # Upload thumbnail if provided
    if args.thumbnail:
        thumb_path = Path(args.thumbnail)
        if thumb_path.exists():
            try:
                service.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(thumb_path)),
                ).execute()
                print(f"  ✅ Thumbnail set")
            except Exception as e:
                print(f"  ⚠️ Thumbnail upload failed: {e}")

    print(f"\n  🎉 Done! Video live at: {url}")


if __name__ == "__main__":
    main()
