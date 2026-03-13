"""
Emotion detection from text using VADER sentiment analysis
with extended pattern matching for nuanced emotional categories.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


# Keyword patterns for emotions that VADER alone cannot reliably detect
_SURPRISE_PATTERNS: List[str] = [
    r"\bwow\b", r"\bamazing\b", r"\bincredible\b", r"\bunbelievable\b",
    r"\bstunning\b", r"\bshocking\b", r"\bblew my mind\b", r"\bno way\b",
    r"\bcan't believe\b", r"\bcannot believe\b",
]

_CURIOSITY_PATTERNS: List[str] = [
    r"\bwonder\b", r"\bcurious\b", r"\bfascinating\b", r"\bintriguing\b",
    r"\bi wonder\b", r"\bhow does\b", r"\bwhat if\b",
    r"\bwhy does\b", r"\btell me more\b",
]

_CONCERN_PATTERNS: List[str] = [
    r"\bworri", r"\bconcern", r"\bnervous\b", r"\banxious\b",
    r"\bafraid\b", r"\bscared\b", r"\bfrightened\b", r"\buneasy\b",
    r"\btrouble\b", r"\bproblem\b", r"\bissue\b", r"\bunsure\b",
]


@dataclass
class EmotionResult:
    """Holds the outcome of a single emotion detection pass."""

    emotion: str
    intensity: float  # 0.0 (weak) – 1.0 (strong)
    raw_scores: Dict[str, float] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.emotion} (intensity={self.intensity:.2f})"


class EmotionDetector:
    """
    Classifies text into one of six emotional categories:
    positive, negative, neutral, surprise, curiosity, concern.

    Detection order:
      1. Pattern-based check for surprise / curiosity / concern.
      2. VADER compound score for positive / negative / neutral.

    Intensity is derived from VADER's compound magnitude and
    pattern match confidence, then clamped to [0.0, 1.0].
    """

    def __init__(self) -> None:
        self._analyzer = SentimentIntensityAnalyzer()

    def detect(self, text: str) -> EmotionResult:
        """Return the dominant emotion and its intensity for *text*."""
        if not text or not text.strip():
            return EmotionResult("neutral", 0.5)

        scores = self._analyzer.polarity_scores(text)
        compound = scores["compound"]
        lower = text.lower()

        # Pattern-based emotions take priority when the compound score is
        # not strongly negative (to avoid labeling grief as "surprise").
        if self._matches(lower, _SURPRISE_PATTERNS) and compound > -0.4:
            intensity = min(1.0, 0.55 + abs(compound) * 0.45)
            return EmotionResult("surprise", intensity, scores)

        if self._matches(lower, _CURIOSITY_PATTERNS) and compound > -0.3:
            intensity = min(1.0, 0.45 + abs(compound) * 0.35)
            return EmotionResult("curiosity", intensity, scores)

        if self._matches(lower, _CONCERN_PATTERNS):
            intensity = min(1.0, 0.40 + abs(compound) * 0.50)
            return EmotionResult("concern", intensity, scores)

        # Standard VADER classification
        if compound >= 0.05:
            intensity = min(1.0, (compound + 0.05) / 1.05)
            return EmotionResult("positive", intensity, scores)

        if compound <= -0.05:
            intensity = min(1.0, (abs(compound) + 0.05) / 1.05)
            return EmotionResult("negative", intensity, scores)

        return EmotionResult("neutral", 0.5, scores)

    @staticmethod
    def _matches(text: str, patterns: List[str]) -> bool:
        return any(re.search(p, text) for p in patterns)
