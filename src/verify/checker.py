"""
Content Checker

Quantitative analysis and guideline compliance checks for composed content.
Run after the agent composes a piece to verify it meets all standards.

Usage:
    python -m src.verify.checker data/output/hindsight-politics/2026-03-01/draft.md
"""

import re
import sys
from pathlib import Path
from typing import Optional

from src.core.config import ConfigLoader


class ContentChecker:
    """Runs quantitative checks against composed content."""

    def __init__(self, config: Optional[ConfigLoader] = None):
        self.config = config or ConfigLoader()
        self.voice = self.config.load_voice()
        self.issues: list[dict] = []
        self.stats: dict = {}

    def check(self, content: str, channel_slug: str = "") -> dict:
        """Run all checks and return a report.

        Args:
            content: The composed markdown content.
            channel_slug: Channel this was composed for.

        Returns:
            Dict with 'passed', 'stats', 'issues', 'score'.
        """
        self.issues = []
        self.stats = {}

        # Run all checks
        self._check_word_count(content)
        self._check_title_and_subtitle(content)
        self._check_formula_adherence(content)
        self._check_voice_compliance(content)
        self._check_source_references(content)
        self._check_external_quotes(content)
        self._check_closing_insight(content)
        self._check_readability(content)
        self._check_forbidden_patterns(content)
        self._check_section_structure(content)

        # Calculate score
        total_checks = len(self.stats)
        passed_checks = sum(
            1 for v in self.stats.values()
            if isinstance(v, dict) and v.get("passed", False)
        )
        score = round(passed_checks / max(total_checks, 1) * 100)

        return {
            "passed": len(self.issues) == 0,
            "score": score,
            "stats": self.stats,
            "issues": self.issues,
            "summary": self._generate_summary(),
        }

    def _check_word_count(self, content: str) -> None:
        """Check word count is within range."""
        words = len(content.split())
        target_min, target_max = 1500, 3000

        self.stats["word_count"] = {
            "value": words,
            "target": f"{target_min}–{target_max}",
            "passed": target_min <= words <= target_max,
        }

        if words < target_min:
            self.issues.append({
                "severity": "error",
                "check": "word_count",
                "message": f"Too short: {words} words (minimum {target_min})",
            })
        elif words > target_max:
            self.issues.append({
                "severity": "warning",
                "check": "word_count",
                "message": f"Too long: {words} words (maximum {target_max})",
            })

    def _check_title_and_subtitle(self, content: str) -> None:
        """Check for title (# ) and subtitle."""
        lines = content.strip().split("\n")
        has_title = any(
            l.strip().startswith("# ") and not l.strip().startswith("## ")
            for l in lines[:5]
        )
        has_subtitle = False
        for i, l in enumerate(lines[:5]):
            if l.strip().startswith("# "):
                # Check next non-empty lines for subtitle
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_l = lines[j].strip()
                    if next_l and not next_l.startswith("#"):
                        has_subtitle = True
                        break
                break

        self.stats["title"] = {"value": has_title, "passed": has_title}
        self.stats["subtitle"] = {"value": has_subtitle, "passed": has_subtitle}

        if not has_title:
            self.issues.append({
                "severity": "error",
                "check": "title",
                "message": "Missing title (should start with '# ')",
            })
        if not has_subtitle:
            self.issues.append({
                "severity": "warning",
                "check": "subtitle",
                "message": "Missing subtitle after title",
            })

    def _check_formula_adherence(self, content: str) -> None:
        """Estimate how well the 4-part formula is followed."""
        content_lower = content.lower()

        # 1. Report as own (25%) — claims, assertions, analysis
        own_indicators = [
            "the real ", "what this means", "the point is",
            "what's actually", "the truth is", "in reality",
            "the important", "worth noting", "crucially",
        ]
        own_score = sum(1 for p in own_indicators if p in content_lower)

        # 2. Reference source (10%) — light sourcing
        ref_indicators = [
            "according to", "as reported", "noted by",
            "pointed out", "as described", "reported that",
        ]
        ref_score = sum(1 for p in ref_indicators if p in content_lower)

        # 3. Frame in context (35%) — history, disagreements
        context_indicators = [
            "historically", "in context", "what's not being said",
            "the broader", "precedent", "compared to",
            "in contrast", "the pattern", "goes back to",
            "echoes of", "reminiscent of", "unlike",
        ]
        context_score = sum(1 for p in context_indicators if p in content_lower)

        # 4. Research and quote (30%) — external sources
        quote_indicators = content.count("\"") // 2  # Rough quote count
        blockquote_count = content.count("> ")

        self.stats["formula"] = {
            "report_as_own": own_score,
            "reference_source": ref_score,
            "frame_in_context": context_score,
            "research_quotes": quote_indicators + blockquote_count,
            "passed": (own_score >= 2 and context_score >= 2
                       and (quote_indicators + blockquote_count) >= 2),
        }

        if context_score < 2:
            self.issues.append({
                "severity": "warning",
                "check": "formula",
                "message": "Weak on 'Frame in Context' — needs more historical/contextual framing",
            })

    def _check_voice_compliance(self, content: str) -> None:
        """Check content matches the voice configuration."""
        voice_config = self.voice.get("voice", {})
        content_lower = content.lower()

        # Check IS NOT violations
        is_not = voice_config.get("is_not", [])
        violations = []

        # Common AI-sounding patterns to flag
        ai_patterns = [
            r"in conclusion",
            r"it's worth noting that",
            r"it is important to note",
            r"at the end of the day",
            r"let's dive in",
            r"without further ado",
            r"in this article",
            r"as we can see",
            r"it goes without saying",
            r"needless to say",
            r"in today's world",
            r"in summary",
        ]

        for pattern in ai_patterns:
            if re.search(pattern, content_lower):
                violations.append(pattern)

        self.stats["voice_compliance"] = {
            "ai_pattern_violations": len(violations),
            "violations": violations,
            "passed": len(violations) == 0,
        }

        for v in violations:
            self.issues.append({
                "severity": "error",
                "check": "voice",
                "message": f"AI-sounding pattern detected: '{v}'",
            })

    def _check_source_references(self, content: str) -> None:
        """Check that sources are referenced lightly, not over-cited."""
        # Count how many times source-like references appear
        ref_patterns = [
            r"according to .+?,",
            r"as .+ (noted|reported|said|wrote|argued)",
            r"in .+'s (article|video|report|essay|analysis)",
        ]
        ref_count = sum(
            len(re.findall(p, content, re.IGNORECASE))
            for p in ref_patterns
        )

        words = len(content.split())
        refs_per_1000 = round(ref_count / max(words, 1) * 1000, 1)

        self.stats["source_references"] = {
            "count": ref_count,
            "per_1000_words": refs_per_1000,
            "passed": 1 <= refs_per_1000 <= 8,
        }

        if refs_per_1000 > 8:
            self.issues.append({
                "severity": "warning",
                "check": "source_references",
                "message": f"Too many source references ({refs_per_1000}/1000 words) — reads like a book report",
            })
        elif refs_per_1000 < 1:
            self.issues.append({
                "severity": "warning",
                "check": "source_references",
                "message": "No source references found — should lightly reference the source",
            })

    def _check_external_quotes(self, content: str) -> None:
        """Check for external quotes/paraphrases beyond provided sources."""
        # Count distinct quoted passages
        quotes = re.findall(r'"([^"]{20,})"', content)
        blockquotes = re.findall(r'^>\s*(.+)', content, re.MULTILINE)
        total_quotes = len(quotes) + len(blockquotes)

        self.stats["external_quotes"] = {
            "inline_quotes": len(quotes),
            "blockquotes": len(blockquotes),
            "total": total_quotes,
            "target": "≥3",
            "passed": total_quotes >= 3,
        }

        if total_quotes < 3:
            self.issues.append({
                "severity": "warning",
                "check": "external_quotes",
                "message": f"Only {total_quotes} quotes found (target: ≥3 from external sources)",
            })

    def _check_closing_insight(self, content: str) -> None:
        """Check that the piece ends with a lingering thought."""
        # Get last paragraph
        paragraphs = [
            p.strip() for p in content.split("\n\n")
            if p.strip() and not p.strip().startswith("#")
        ]

        if not paragraphs:
            self.stats["closing"] = {"passed": False}
            return

        last_para = paragraphs[-1]
        words_in_closing = len(last_para.split())

        # A lingering closing should be moderate length (not too short/long)
        good_length = 20 <= words_in_closing <= 150

        self.stats["closing"] = {
            "words": words_in_closing,
            "passed": good_length,
        }

        if words_in_closing < 20:
            self.issues.append({
                "severity": "warning",
                "check": "closing",
                "message": "Closing paragraph too short — needs a lingering insight",
            })

    def _check_readability(self, content: str) -> None:
        """Calculate readability metrics."""
        # Strip markdown
        clean = re.sub(r'[#*>\[\]()]', '', content)
        sentences = re.split(r'[.!?]+', clean)
        sentences = [s.strip() for s in sentences if s.strip()]
        words = clean.split()
        syllables = sum(self._count_syllables(w) for w in words)

        if not sentences or not words:
            self.stats["readability"] = {"passed": True}
            return

        avg_words_per_sentence = len(words) / len(sentences)
        avg_syllables_per_word = syllables / len(words)

        # Flesch-Kincaid Grade Level
        fk_grade = (
            0.39 * avg_words_per_sentence
            + 11.8 * avg_syllables_per_word
            - 15.59
        )

        self.stats["readability"] = {
            "sentences": len(sentences),
            "avg_words_per_sentence": round(avg_words_per_sentence, 1),
            "flesch_kincaid_grade": round(fk_grade, 1),
            "target_grade": "10–14",
            "passed": 10 <= fk_grade <= 14,
        }

        if fk_grade < 8:
            self.issues.append({
                "severity": "warning",
                "check": "readability",
                "message": f"Reading level too simple (grade {fk_grade:.1f}) — should be 10–14",
            })
        elif fk_grade > 16:
            self.issues.append({
                "severity": "warning",
                "check": "readability",
                "message": f"Reading level too dense (grade {fk_grade:.1f}) — should be 10–14",
            })

    def _check_forbidden_patterns(self, content: str) -> None:
        """Check for patterns that violate voice guidelines."""
        forbidden = [
            (r"(?i)\bdelve\b", "delve"),
            (r"(?i)\bunpack\b", "unpack"),
            (r"(?i)\bimpactful\b", "impactful"),
            (r"(?i)\bsynerg", "synergy/synergize"),
            (r"(?i)\bgame.?changer\b", "game-changer"),
            (r"(?i)\bparadigm shift\b", "paradigm shift"),
            (r"(?i)\brobust\b", "robust"),
            (r"(?i)\bleverage\b", "leverage (as verb)"),
            (r"(?i)\bholistic\b", "holistic"),
            (r"(?i)\bstakeholder\b", "stakeholder"),
            (r"!{2,}", "multiple exclamation marks"),
        ]

        violations = []
        for pattern, name in forbidden:
            if re.search(pattern, content):
                violations.append(name)

        self.stats["forbidden_words"] = {
            "violations": violations,
            "passed": len(violations) == 0,
        }

        for v in violations:
            self.issues.append({
                "severity": "error",
                "check": "forbidden",
                "message": f"Forbidden pattern: '{v}'",
            })

    def _check_section_structure(self, content: str) -> None:
        """Check for proper section structure."""
        headers = re.findall(r'^#{1,3}\s+.+', content, re.MULTILINE)

        self.stats["structure"] = {
            "header_count": len(headers),
            "headers": [h.strip() for h in headers],
            "passed": len(headers) >= 3,
        }

        if len(headers) < 3:
            self.issues.append({
                "severity": "warning",
                "check": "structure",
                "message": f"Only {len(headers)} headers — needs more structure",
            })

    def _count_syllables(self, word: str) -> int:
        """Rough syllable count for English words."""
        word = word.lower().strip(".,!?;:'\"")
        if not word:
            return 0
        count = len(re.findall(r'[aeiouy]+', word))
        if word.endswith('e') and count > 1:
            count -= 1
        return max(count, 1)

    def _generate_summary(self) -> str:
        """Generate a human-readable summary of the check results."""
        lines = []
        errors = [i for i in self.issues if i["severity"] == "error"]
        warnings = [i for i in self.issues if i["severity"] == "warning"]

        if not self.issues:
            lines.append("✅ All checks passed!")
        else:
            if errors:
                lines.append(f"❌ {len(errors)} error(s):")
                for e in errors:
                    lines.append(f"   • {e['message']}")
            if warnings:
                lines.append(f"⚠️  {len(warnings)} warning(s):")
                for w in warnings:
                    lines.append(f"   • {w['message']}")

        # Key stats
        wc = self.stats.get("word_count", {})
        if wc:
            lines.append(f"\n📊 Word count: {wc.get('value', '?')}")

        rd = self.stats.get("readability", {})
        if rd and "flesch_kincaid_grade" in rd:
            lines.append(f"📊 Reading level: grade {rd['flesch_kincaid_grade']}")

        eq = self.stats.get("external_quotes", {})
        if eq:
            lines.append(f"📊 Quotes: {eq.get('total', 0)} found")

        fm = self.stats.get("formula", {})
        if fm:
            lines.append(
                f"📊 Formula: own={fm.get('report_as_own', 0)} "
                f"ref={fm.get('reference_source', 0)} "
                f"context={fm.get('frame_in_context', 0)} "
                f"quotes={fm.get('research_quotes', 0)}"
            )

        return "\n".join(lines)

    def print_report(self, report: dict) -> None:
        """Pretty-print the check report."""
        score = report["score"]
        emoji = "✅" if score >= 80 else ("⚠️" if score >= 60 else "❌")

        print(f"\n{'═' * 60}")
        print(f"  CONTENT CHECK — Score: {emoji} {score}%")
        print(f"{'═' * 60}\n")
        print(report["summary"])
        print()


def main():
    """CLI entry point for content checking."""
    if len(sys.argv) < 2:
        print("Usage: python -m src.verify.checker <path-to-draft.md> [channel-slug]")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)

    channel = sys.argv[2] if len(sys.argv) > 2 else ""
    content = path.read_text()

    checker = ContentChecker()
    report = checker.check(content, channel)
    checker.print_report(report)


if __name__ == "__main__":
    main()
