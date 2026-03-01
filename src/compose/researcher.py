"""
Research Augmentation

Uses web search and Gemini to find supporting quotes, statistics,
and historical parallels for the value-add sections of content.
"""

import os
import json
import re
from typing import Optional

from src.core.config import ConfigLoader


class Researcher:
    """Finds supporting/contrasting sources for content value-add."""

    def __init__(self, config: Optional[ConfigLoader] = None):
        self.config = config or ConfigLoader()

    def find_supporting_sources(
        self, topic: str, thesis: str, count: int = 5
    ) -> list[dict]:
        """Find sources that support or contrast with a thesis.

        Args:
            topic: The broad topic area.
            thesis: The specific argument or claim to support/contrast.
            count: Number of sources to find.

        Returns:
            List of dicts with 'quote', 'source', 'author', 'year', 'relevance'.
        """
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return []

        prompt = f"""Find {count} real, verifiable quotes and sources that either 
support or provide interesting counterpoints to this thesis:

Topic: {topic}
Thesis: {thesis}

For each source, provide:
1. An exact or accurately paraphrased quote
2. The full source (book title, article, speech, etc.)
3. Author name
4. Year
5. Whether it supports or contrasts the thesis

IMPORTANT: Only cite real, verifiable sources. Do not fabricate quotes.
Prefer well-known, authoritative sources.

Format as a JSON array with keys: quote, source, author, year, relation (support/contrast).
"""

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
            response = model.generate_content(prompt)

            json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"Research query failed: {e}")

        return []

    def find_historical_parallels(
        self, situation: str, count: int = 3
    ) -> list[dict]:
        """Find historical parallels to a current situation.

        Returns:
            List of dicts with 'event', 'year', 'parallel', 'source'.
        """
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return []

        prompt = f"""Find {count} historical parallels to this current situation:

{situation}

For each parallel, provide:
1. The historical event or period
2. Year or date range
3. How it parallels the current situation
4. A specific detail or quote that makes the parallel vivid
5. A credible source or historian who has written about this

IMPORTANT: Only cite real historical events and real historians/sources.

Format as a JSON array with keys: event, year, parallel, detail, source.
"""

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
            response = model.generate_content(prompt)

            json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"Historical parallels query failed: {e}")

        return []

    def fact_check_claims(self, claims: list[str]) -> list[dict]:
        """Verify factual claims before publishing.

        Returns:
            List of dicts with 'claim', 'verdict', 'evidence', 'confidence'.
        """
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return []

        claims_text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))

        prompt = f"""Fact-check these claims rigorously:

{claims_text}

For each claim, provide:
1. The claim (as stated)
2. Verdict: CONFIRMED, MOSTLY_TRUE, NEEDS_CONTEXT, MISLEADING, or FALSE
3. Evidence for your verdict with specific sources
4. Confidence level (high, medium, low)

Be conservative — if you're not sure, say NEEDS_CONTEXT.

Format as a JSON array with keys: claim, verdict, evidence, confidence.
"""

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
            response = model.generate_content(prompt)

            json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"Fact-check query failed: {e}")

        return []
