"""
Content Statistics

Quantitative analysis of composed content — tracks metrics over time
to ensure consistency and improvement across channels.

Usage:
    python -m src.verify.stats data/output/hindsight-politics/
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class ContentStats:
    """Tracks and analyzes content metrics over time."""

    def __init__(self, data_dir: Path = Path("data")):
        self.data_dir = data_dir
        self.stats_file = data_dir / "stats.jsonl"

    def analyze(self, content: str, channel_slug: str) -> dict:
        """Generate comprehensive statistics for a piece of content."""
        words = content.split()
        sentences = [
            s.strip() for s in re.split(r'[.!?]+', content)
            if s.strip()
        ]
        paragraphs = [
            p.strip() for p in content.split("\n\n")
            if p.strip() and not p.strip().startswith("#")
        ]
        headers = re.findall(r'^#{1,3}\s+(.+)', content, re.MULTILINE)

        # Quote analysis
        inline_quotes = re.findall(r'"([^"]{15,})"', content)
        blockquotes = re.findall(r'^>\s*(.+)', content, re.MULTILINE)

        # Link/reference analysis
        urls = re.findall(r'https?://\S+', content)
        named_refs = re.findall(
            r'(?:according to|as|per)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            content
        )

        # Sentence length distribution
        sent_lengths = [len(s.split()) for s in sentences]
        short_sents = sum(1 for l in sent_lengths if l < 10)
        medium_sents = sum(1 for l in sent_lengths if 10 <= l <= 25)
        long_sents = sum(1 for l in sent_lengths if l > 25)

        # Vocabulary richness (type-token ratio)
        unique_words = set(w.lower().strip(".,!?;:'\"()[]") for w in words)
        ttr = round(len(unique_words) / max(len(words), 1), 3)

        stats = {
            "channel": channel_slug,
            "timestamp": datetime.now().isoformat(),
            "word_count": len(words),
            "sentence_count": len(sentences),
            "paragraph_count": len(paragraphs),
            "header_count": len(headers),
            "avg_sentence_length": round(
                sum(sent_lengths) / max(len(sent_lengths), 1), 1
            ),
            "sentence_variety": {
                "short": short_sents,
                "medium": medium_sents,
                "long": long_sents,
            },
            "vocabulary_richness": ttr,
            "unique_words": len(unique_words),
            "quotes": {
                "inline": len(inline_quotes),
                "blockquotes": len(blockquotes),
                "total": len(inline_quotes) + len(blockquotes),
            },
            "references": {
                "urls": len(urls),
                "named": len(named_refs),
                "named_sources": list(set(named_refs)),
            },
            "structure": {
                "headers": headers,
                "avg_paragraph_length": round(
                    len(words) / max(len(paragraphs), 1)
                ),
            },
        }

        return stats

    def record(self, stats: dict) -> None:
        """Append stats to the JSONL tracking file."""
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.stats_file, "a") as f:
            f.write(json.dumps(stats) + "\n")

    def get_channel_history(
        self, channel_slug: str, limit: int = 30
    ) -> list[dict]:
        """Get historical stats for a channel."""
        if not self.stats_file.exists():
            return []

        history = []
        with open(self.stats_file) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("channel") == channel_slug:
                        history.append(entry)
                except json.JSONDecodeError:
                    continue

        return history[-limit:]

    def get_channel_averages(self, channel_slug: str) -> dict:
        """Get average stats across all pieces for a channel."""
        history = self.get_channel_history(channel_slug)
        if not history:
            return {}

        avg = {
            "pieces_count": len(history),
            "avg_word_count": round(
                sum(h["word_count"] for h in history) / len(history)
            ),
            "avg_sentence_length": round(
                sum(h["avg_sentence_length"] for h in history) / len(history),
                1
            ),
            "avg_vocabulary_richness": round(
                sum(h["vocabulary_richness"] for h in history) / len(history),
                3
            ),
            "avg_quotes": round(
                sum(h["quotes"]["total"] for h in history) / len(history),
                1
            ),
        }

        return avg

    def print_stats(self, stats: dict) -> None:
        """Pretty-print content statistics."""
        print(f"\n{'═' * 60}")
        print(f"  CONTENT STATISTICS — {stats.get('channel', '?')}")
        print(f"{'═' * 60}\n")

        print(f"  📏 Words: {stats['word_count']}")
        print(f"  📝 Sentences: {stats['sentence_count']}")
        print(f"  📄 Paragraphs: {stats['paragraph_count']}")
        print(f"  📑 Headers: {stats['header_count']}")
        print()

        sv = stats["sentence_variety"]
        print(f"  📊 Sentence variety:")
        print(f"     Short (<10 words):  {sv['short']}")
        print(f"     Medium (10-25):     {sv['medium']}")
        print(f"     Long (>25):         {sv['long']}")
        print(f"     Avg length:         {stats['avg_sentence_length']} words")
        print()

        print(f"  🔤 Vocabulary richness: {stats['vocabulary_richness']}")
        print(f"     Unique words:       {stats['unique_words']}")
        print()

        q = stats["quotes"]
        print(f"  💬 Quotes: {q['total']} ({q['inline']} inline, {q['blockquotes']} block)")

        r = stats["references"]
        print(f"  🔗 References: {r['urls']} URLs, {r['named']} named sources")
        if r["named_sources"]:
            print(f"     Named: {', '.join(r['named_sources'][:5])}")
        print()


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m src.verify.stats <path> [channel-slug]")
        sys.exit(1)

    path = Path(sys.argv[1])
    channel = sys.argv[2] if len(sys.argv) > 2 else path.parent.name

    if path.is_file():
        content = path.read_text()
        stats_obj = ContentStats()
        stats = stats_obj.analyze(content, channel)
        stats_obj.print_stats(stats)
        stats_obj.record(stats)
        print(f"  📁 Stats recorded to data/stats.jsonl")
    elif path.is_dir():
        # Show channel history
        stats_obj = ContentStats()
        avgs = stats_obj.get_channel_averages(channel)
        if avgs:
            print(f"\n  📊 Channel averages for {channel}:")
            for k, v in avgs.items():
                print(f"     {k}: {v}")
        else:
            print(f"  No history for {channel}")


if __name__ == "__main__":
    main()
