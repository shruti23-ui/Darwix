"""
Maps detected emotion + intensity to concrete TTS voice parameters.

Covers both classic pyttsx3/gTTS parameters and ElevenLabs voice settings
so every backend can be driven from a single VoiceParameters object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from app.emotion import EmotionResult


@dataclass
class VoiceParameters:
    """
    Target vocal characteristics for the TTS engine.

    Classic fields (pyttsx3 / gTTS):
        rate:             Words per minute (typical range 120–280).
        volume:           Linear amplitude scalar 0.0–1.0.
        pitch_semitones:  Semitone shift relative to the engine's default pitch.

    ElevenLabs fields:
        el_speed:         Playback speed multiplier, 0.7–1.3 (1.0 = default).
        el_stability:     Voice consistency 0.0 (expressive) – 1.0 (monotone).
        el_style:         Style exaggeration 0.0–1.0.

    Shared metadata:
        emotion:          Detected emotion label.
        intensity:        Detection intensity 0.0–1.0.
    """

    rate: int
    volume: float
    pitch_semitones: float
    el_speed: float
    el_stability: float
    el_style: float
    emotion: str
    intensity: float

    def __str__(self) -> str:
        return (
            f"VoiceParameters(emotion={self.emotion}, intensity={self.intensity:.2f}, "
            f"rate={self.rate} wpm, volume={self.volume:.2f}, "
            f"pitch={self.pitch_semitones:+.2f} st, "
            f"el_speed={self.el_speed:.2f}, el_stability={self.el_stability:.2f}, "
            f"el_style={self.el_style:.2f})"
        )


# Base values represent a calm, neutral speaker.
_BASE_RATE: int = 185
_BASE_VOLUME: float = 0.88

# Each profile defines *maximum* deltas or absolute targets at intensity = 1.0.
# All values are linearly interpolated against detected intensity.
_PROFILES: Dict[str, Dict[str, float]] = {
    "positive": {
        "rate_delta": 28.0,
        "volume_delta": 0.07,
        "pitch_semitones": 2.5,
        "el_speed_delta": 0.15,
        "el_stability": 0.35,
        "el_style": 0.65,
    },
    "negative": {
        "rate_delta": -32.0,
        "volume_delta": -0.12,
        "pitch_semitones": -3.0,
        "el_speed_delta": -0.18,
        "el_stability": 0.72,
        "el_style": 0.20,
    },
    "neutral": {
        "rate_delta": 0.0,
        "volume_delta": 0.0,
        "pitch_semitones": 0.0,
        "el_speed_delta": 0.0,
        "el_stability": 0.60,
        "el_style": 0.20,
    },
    "surprise": {
        "rate_delta": 38.0,
        "volume_delta": 0.10,
        "pitch_semitones": 4.0,
        "el_speed_delta": 0.22,
        "el_stability": 0.18,
        "el_style": 0.85,
    },
    "curiosity": {
        "rate_delta": 12.0,
        "volume_delta": 0.02,
        "pitch_semitones": 1.5,
        "el_speed_delta": 0.07,
        "el_stability": 0.48,
        "el_style": 0.50,
    },
    "concern": {
        "rate_delta": -22.0,
        "volume_delta": -0.06,
        "pitch_semitones": -1.5,
        "el_speed_delta": -0.10,
        "el_stability": 0.68,
        "el_style": 0.35,
    },
}

# ElevenLabs base values (neutral baseline)
_EL_BASE_SPEED: float = 1.0
_EL_BASE_STABILITY: float = 0.60
_EL_BASE_STYLE: float = 0.20


class VoiceMapper:
    """
    Deterministically converts an :class:`EmotionResult` into
    :class:`VoiceParameters` by interpolating emotion profiles
    against the detected intensity.
    """

    def map(self, result: EmotionResult) -> VoiceParameters:
        """Return voice parameters for the given emotion result."""
        profile = _PROFILES.get(result.emotion, _PROFILES["neutral"])
        i = result.intensity

        rate = max(90, min(320, int(_BASE_RATE + profile["rate_delta"] * i)))
        volume = max(0.10, min(1.0, _BASE_VOLUME + profile["volume_delta"] * i))
        pitch = profile["pitch_semitones"] * i

        # ElevenLabs: stability and style are absolute targets interpolated
        # from neutral baseline toward the emotion's target value.
        el_speed = round(
            max(0.7, min(1.3, _EL_BASE_SPEED + profile["el_speed_delta"] * i)), 3
        )
        el_stability = round(
            _EL_BASE_STABILITY + (profile["el_stability"] - _EL_BASE_STABILITY) * i, 3
        )
        el_style = round(
            max(0.0, min(1.0, _EL_BASE_STYLE + (profile["el_style"] - _EL_BASE_STYLE) * i)), 3
        )

        return VoiceParameters(
            rate=rate,
            volume=volume,
            pitch_semitones=round(pitch, 3),
            el_speed=el_speed,
            el_stability=el_stability,
            el_style=el_style,
            emotion=result.emotion,
            intensity=round(result.intensity, 3),
        )
