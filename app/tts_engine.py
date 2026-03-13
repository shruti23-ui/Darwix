"""
Text-to-speech synthesis backends.

Supported backends
------------------
elevenlabs  (default, highest quality, requires API key)
    Returns MP3 bytes directly from the API — no local audio processing needed.

pyttsx3     (fully offline, Python < 3.13 recommended)
    Controls rate and volume natively; pitch adjusted via pydub post-processing.

gtts        (requires internet, no API key, Python < 3.13 recommended)
    Google TTS; rate/pitch adjustments applied via pydub post-processing.

Note: pyttsx3 and gtts backends rely on pydub for post-processing.
pydub requires audioop which was removed in Python 3.13.  ElevenLabs is
fully compatible with Python 3.13+.

Select the backend with the ``--engine`` CLI flag or the ``engine``
parameter of :func:`create_engine`.
"""

from __future__ import annotations

import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from app.mapper import VoiceParameters


# ---------------------------------------------------------------------------
# Helpers (pydub-dependent — imported lazily to avoid Python 3.13 breakage)
# ---------------------------------------------------------------------------

def _get_audio_segment():
    """Lazy import of pydub.AudioSegment with a helpful error message."""
    try:
        from pydub import AudioSegment
        return AudioSegment
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "pydub is required for pyttsx3/gTTS backends but could not be imported. "
            "audioop was removed in Python 3.13.  Use ElevenLabs backend or "
            "downgrade to Python 3.12.  Original error: " + str(exc)
        ) from exc


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _shift_pitch(audio, semitones: float):
    """
    Shift pitch by resampling: respawn the audio at a modified sample rate
    then set it back to the original frame rate.
    """
    freq_ratio: float = 2.0 ** (semitones / 12.0)
    shifted = audio._spawn(
        audio.raw_data,
        overrides={"frame_rate": int(audio.frame_rate * freq_ratio)},
    )
    return shifted.set_frame_rate(audio.frame_rate)


def _apply_post_processing(audio, params: VoiceParameters):
    """Apply pitch shift and volume normalisation to a pydub AudioSegment."""
    if abs(params.pitch_semitones) > 0.05:
        audio = _shift_pitch(audio, params.pitch_semitones)

    target_dbfs = -20.0 + (params.volume - 0.5) * 20.0
    change = target_dbfs - audio.dBFS
    if abs(change) > 0.5:
        audio = audio + change

    return audio


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseTTSEngine(ABC):
    """Common interface for all TTS backends."""

    @abstractmethod
    def synthesize(
        self,
        text: str,
        params: VoiceParameters,
        output_path: str,
    ) -> str:
        """
        Synthesize *text* with *params* and write the result to *output_path*.
        Returns the resolved path of the written file.
        """


# ---------------------------------------------------------------------------
# ElevenLabs backend
# ---------------------------------------------------------------------------

# ElevenLabs premade voices available on all plan tiers.
ELEVENLABS_VOICES: dict[str, str] = {
    "Sarah":   "EXAVITQu4vr4xnSDxMaL",   # Mature, Reassuring, Confident
    "Alice":   "Xb7hH8MSUJpSbSDYk0k2",   # Clear, Engaging Educator
    "Laura":   "FGY2WhTYpPnrIDTdsKH5",   # Enthusiast, Quirky Attitude
    "Jessica": "cgSgspJ2msm6clMCkdW9",   # Playful, Bright, Warm
    "Matilda": "XrExE9yKIg1WjnnlVkGX",   # Knowledgable, Professional
    "Lily":    "pFZP5JQG7iQjIQuC4Bku",   # Velvety Actress
    "Adam":    "pNInz6obpgDQGcFmaJgB",   # Dominant, Firm
    "Brian":   "nPczCjzI2devNBz1zQrb",   # Deep, Resonant and Comforting
    "Charlie": "IKne3meq5aSn9XLyUdCD",   # Deep, Confident, Energetic
    "Daniel":  "onwK4e9ZLuTAKqWW03F9",   # Steady Broadcaster
    "Eric":    "cjVigY5qzO86Huf0OWal",   # Smooth, Trustworthy
    "George":  "JBFqnCBsd6RMkjVDRZzb",   # Warm, Captivating Storyteller
    "Liam":    "TX3LPaxmHKxFdv7VOQHJ",   # Energetic, Social Media Creator
    "River":   "SAz9YHcvj6GT2YYXdXww",   # Relaxed, Neutral, Informative
    "Roger":   "CwhRBWXzGAHq8TQ4Fs17",   # Laid-Back, Casual, Resonant
    "Will":    "bIHbv24MWmeRgasZH58o",   # Relaxed Optimist
}

_DEFAULT_VOICE = "Sarah"
_DEFAULT_MODEL = "eleven_multilingual_v2"


class ElevenLabsEngine(BaseTTSEngine):
    """
    High-quality neural TTS via the ElevenLabs API.

    Emotion is expressed through three voice settings:
    - ``stability``  — lower values produce more expressive, variable delivery.
    - ``style``      — amplifies the voice's natural style characteristics.
    - ``speed``      — playback speed (0.7 = slow / 1.3 = fast).

    The API key is read from the ``ELEVENLABS_API_KEY`` environment variable
    or passed directly as ``api_key``.
    """

    def __init__(
        self,
        voice: str = _DEFAULT_VOICE,
        model: str = _DEFAULT_MODEL,
        api_key: str | None = None,
    ) -> None:
        from elevenlabs.client import ElevenLabs

        resolved_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "ElevenLabs API key not found.  Set the ELEVENLABS_API_KEY "
                "environment variable or pass api_key= explicitly."
            )

        self._client = ElevenLabs(api_key=resolved_key)
        self._voice_id = ELEVENLABS_VOICES.get(voice, voice)
        self._model = model

    def synthesize(
        self,
        text: str,
        params: VoiceParameters,
        output_path: str,
    ) -> str:
        from elevenlabs import VoiceSettings

        out = Path(output_path)
        _ensure_dir(out)

        audio_iter = self._client.text_to_speech.convert(
            text=text,
            voice_id=self._voice_id,
            model_id=self._model,
            voice_settings=VoiceSettings(
                stability=params.el_stability,
                similarity_boost=0.80,
                style=params.el_style,
                use_speaker_boost=True,
                speed=params.el_speed,
            ),
            output_format="mp3_44100_128",
        )

        out.write_bytes(b"".join(audio_iter))
        return str(out)


# ---------------------------------------------------------------------------
# pyttsx3 backend
# ---------------------------------------------------------------------------

class Pyttsx3Engine(BaseTTSEngine):
    """Offline TTS via pyttsx3 with pydub pitch post-processing."""

    def __init__(self) -> None:
        import pyttsx3
        self._engine = pyttsx3.init()

    def synthesize(
        self,
        text: str,
        params: VoiceParameters,
        output_path: str,
    ) -> str:
        AudioSegment = _get_audio_segment()

        self._engine.setProperty("rate", params.rate)
        self._engine.setProperty("volume", params.volume)

        out = Path(output_path)
        _ensure_dir(out)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            self._engine.save_to_file(text, tmp_path)
            self._engine.runAndWait()

            audio = AudioSegment.from_wav(tmp_path)
            audio = _apply_post_processing(audio, params)
            fmt = out.suffix.lstrip(".") or "wav"
            audio.export(str(out), format=fmt)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return str(out)


# ---------------------------------------------------------------------------
# gTTS backend
# ---------------------------------------------------------------------------

class GTTSEngine(BaseTTSEngine):
    """Online TTS via Google Text-to-Speech with pydub post-processing."""

    def __init__(self, lang: str = "en", tld: str = "com") -> None:
        self._lang = lang
        self._tld = tld

    def synthesize(
        self,
        text: str,
        params: VoiceParameters,
        output_path: str,
    ) -> str:
        from gtts import gTTS
        AudioSegment = _get_audio_segment()

        out = Path(output_path)
        _ensure_dir(out)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            gTTS(text=text, lang=self._lang, tld=self._tld).save(tmp_path)
            audio = AudioSegment.from_mp3(tmp_path)
            audio = self._apply_rate(audio, params.rate)
            audio = _apply_post_processing(audio, params)
            fmt = out.suffix.lstrip(".") or "mp3"
            audio.export(str(out), format=fmt)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return str(out)

    @staticmethod
    def _apply_rate(audio, target_rate: int, base_rate: int = 185):
        ratio = target_rate / base_rate
        if abs(ratio - 1.0) < 0.03:
            return audio
        sped = audio._spawn(
            audio.raw_data,
            overrides={"frame_rate": int(audio.frame_rate * ratio)},
        )
        return sped.set_frame_rate(audio.frame_rate)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_ENGINES = {
    "elevenlabs": ElevenLabsEngine,
    "pyttsx3": Pyttsx3Engine,
    "gtts": GTTSEngine,
}


def create_engine(engine_type: str = "elevenlabs", **kwargs) -> BaseTTSEngine:
    """
    Instantiate and return a TTS engine by name.

    Parameters
    ----------
    engine_type:
        One of ``"elevenlabs"`` (default), ``"pyttsx3"``, or ``"gtts"``.
    **kwargs:
        Passed to the engine constructor (e.g. ``api_key=``, ``voice=``).
    """
    key = engine_type.lower()
    if key not in _ENGINES:
        raise ValueError(
            f"Unknown TTS engine '{engine_type}'. "
            f"Available options: {', '.join(_ENGINES)}"
        )
    return _ENGINES[key](**kwargs)
