"""
SSML (Speech Synthesis Markup Language) generation.

Produces W3C SSML 1.0 compliant markup from detected emotion and intensity.

Usage contexts
--------------
- Displayed in the web UI so users can see the expressive markup.
- Used natively by pyttsx3 on Windows (SAPI5 parses SSML).
- Stripped to plain text with ellipsis pauses for backends that don't
  support SSML (gTTS, ElevenLabs — which has its own voice settings).
"""

from __future__ import annotations

import re

from app.mapper import VoiceParameters


# Emotion profiles

# Percentage-based rate deltas at full intensity (scaled linearly below 1.0)
_RATE_DELTA: dict[str, float] = {
    "positive": 18.0,
    "negative": -22.0,
    "neutral":   0.0,
    "surprise":  30.0,
    "curiosity":  8.0,
    "concern":  -15.0,
}

# Semitone pitch shifts at full intensity
_PITCH_ST: dict[str, float] = {
    "positive":  2.5,
    "negative": -3.0,
    "neutral":   0.0,
    "surprise":  4.0,
    "curiosity": 1.5,
    "concern":  -1.5,
}

# SSML volume keywords
_VOLUME_WORD: dict[str, str] = {
    "positive":  "loud",
    "negative":  "soft",
    "neutral":   "medium",
    "surprise":  "x-loud",
    "curiosity": "medium",
    "concern":   "soft",
}

# Base break durations (ms) after sentence-ending punctuation
_SENTENCE_BREAK_MS: dict[str, int] = {
    "positive":  200,
    "negative":  650,
    "neutral":   350,
    "surprise":  120,
    "curiosity": 280,
    "concern":   550,
}

# Base break durations (ms) after commas
_COMMA_BREAK_MS: dict[str, int] = {
    "positive":   90,
    "negative":  300,
    "neutral":   150,
    "surprise":   70,
    "curiosity": 140,
    "concern":   250,
}


# Public API

def generate_ssml(text: str, params: VoiceParameters) -> str:
    """
    Generate W3C SSML 1.0 markup for *text* modulated by *params*.

    The root ``<speak>`` element contains a ``<prosody>`` wrapper that sets
    rate, pitch, and volume.  Sentence and clause boundaries receive
    ``<break>`` elements whose durations scale with emotion intensity.

    Parameters
    ----------
    text:   Input plain text.
    params: Voice parameters produced by :class:`~app.mapper.VoiceMapper`.

    Returns
    -------
    A UTF-8 SSML string ready for compatible TTS engines.
    """
    i = params.intensity
    emotion = params.emotion

    rate_str = _format_rate(emotion, i)
    pitch_str = _format_pitch(emotion, i)
    volume_str = _VOLUME_WORD.get(emotion, "medium")

    sentence_ms = int(_SENTENCE_BREAK_MS.get(emotion, 350) * (0.4 + i * 0.6))
    comma_ms = int(_COMMA_BREAK_MS.get(emotion, 150) * (0.4 + i * 0.6))

    inner = _insert_breaks(text, sentence_ms, comma_ms)
    inner = _add_emphasis(inner, params)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis">\n'
        f'  <prosody rate="{rate_str}" pitch="{pitch_str}" volume="{volume_str}">\n'
        f'    {inner}\n'
        '  </prosody>\n'
        '</speak>'
    )


def strip_ssml(ssml_text: str) -> str:
    """
    Strip all SSML tags and return plain text.

    ``<break>`` elements are converted to ellipsis characters so that
    backends like ElevenLabs still introduce natural micro-pauses when
    encountering ``…``.
    """
    text = re.sub(r"<break[^/]*/?>", "… ", ssml_text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def ssml_to_sapi(ssml_text: str) -> str:
    """
    Return the SSML string as-is for SAPI5 (Windows pyttsx3).

    SAPI5 accepts the full ``<speak>`` document including ``<prosody>``
    and ``<break>`` elements, so no transformation is needed.
    """
    return ssml_text


# Private helpers

def _format_rate(emotion: str, intensity: float) -> str:
    delta = _RATE_DELTA.get(emotion, 0.0) * intensity
    if abs(delta) < 1.0:
        return "medium"
    return f"{delta:+.0f}%"


def _format_pitch(emotion: str, intensity: float) -> str:
    st = _PITCH_ST.get(emotion, 0.0) * intensity
    if abs(st) < 0.15:
        return "medium"
    return f"{st:+.2f}st"


def _insert_breaks(text: str, sentence_ms: int, comma_ms: int) -> str:
    """Insert ``<break>`` tags at punctuation boundaries."""
    # After sentence-ending punctuation followed by whitespace
    text = re.sub(
        r"([.!?])\s+",
        lambda m: f'{m.group(1)} <break time="{sentence_ms}ms"/> ',
        text,
    )
    # After commas
    text = re.sub(
        r"(,)\s+",
        lambda m: f'{m.group(1)} <break time="{comma_ms}ms"/> ',
        text,
    )
    return text


def _add_emphasis(text: str, params: VoiceParameters) -> str:
    """
    Wrap strongly sentiment-charged words in ``<emphasis>`` tags.

    Emphasis level is chosen based on emotion intensity:
    - intensity >= 0.75  → strong
    - intensity >= 0.45  → moderate
    - below              → reduced (for concern / negative)
    """
    if params.intensity < 0.35:
        return text

    _POSITIVE_WORDS = {
        "amazing", "incredible", "fantastic", "wonderful", "brilliant",
        "excellent", "outstanding", "perfect", "love", "great",
    }
    _NEGATIVE_WORDS = {
        "terrible", "awful", "horrible", "dreadful", "worst",
        "disastrous", "failed", "broken", "devastated",
    }

    if params.emotion in ("positive", "surprise"):
        targets = _POSITIVE_WORDS
        level = "strong" if params.intensity >= 0.75 else "moderate"
    elif params.emotion in ("negative", "concern"):
        targets = _NEGATIVE_WORDS
        level = "reduced"
    else:
        return text

    def replace(m: re.Match) -> str:
        word = m.group(0)
        if word.lower() in targets:
            return f'<emphasis level="{level}">{word}</emphasis>'
        return word

    return re.sub(r"\b\w+\b", replace, text)
