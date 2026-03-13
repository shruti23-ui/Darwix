"""
Empathy Engine – CLI entry point.

Usage examples
--------------
# Default (pyttsx3, offline):
    python app/main.py "I just got promoted!"

# ElevenLabs with a specific voice:
    python app/main.py --engine elevenlabs --voice Sarah "This is incredible!"

# gTTS, save as MP3:
    python app/main.py --engine gtts --output outputs/result.mp3 "I'm worried."

# Show emotion, voice params, and generated SSML:
    python app/main.py -v --ssml "Wow, that is absolutely stunning!"

# Read from stdin:
    echo "I'm not sure about this…" | python app/main.py -
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from app.emotion import EmotionDetector
from app.mapper import VoiceMapper
from app.ssml import generate_ssml, strip_ssml
from app.tts_engine import ELEVENLABS_VOICES, create_engine


_DEFAULT_OUTPUT = Path("outputs") / "output.wav"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="empathy-engine",
        description="Convert text to emotionally expressive speech.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "text",
        nargs="?",
        default="-",
        help="Text to synthesize.  Pass '-' (or omit) to read from stdin.",
    )
    parser.add_argument(
        "--engine",
        choices=["pyttsx3", "gtts", "elevenlabs"],
        default="pyttsx3",
        help="TTS backend (default: pyttsx3).",
    )
    parser.add_argument(
        "--voice",
        default="Sarah",
        choices=list(ELEVENLABS_VOICES.keys()),
        help="ElevenLabs voice name (default: Sarah, ignored for other engines).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        dest="api_key",
        help="ElevenLabs API key.  Falls back to ELEVENLABS_API_KEY env var.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(_DEFAULT_OUTPUT),
        help=f"Output audio file path (default: {_DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detected emotion and voice parameters.",
    )
    parser.add_argument(
        "--ssml",
        action="store_true",
        help="Print the generated SSML markup before synthesising.",
    )
    return parser


def resolve_text(raw: str) -> str:
    """Return the actual input text, reading from stdin if *raw* is '-'."""
    if raw == "-":
        if sys.stdin.isatty():
            print("Enter text (press Ctrl-D when done):")
        return sys.stdin.read().strip()
    return raw.strip()


def build_engine_kwargs(args: argparse.Namespace) -> dict:
    kwargs: dict = {}
    if args.engine == "elevenlabs":
        api_key = args.api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        if not api_key:
            print(
                "Error: ElevenLabs API key required.  Pass --api-key or set "
                "the ELEVENLABS_API_KEY environment variable.",
                file=sys.stderr,
            )
            sys.exit(1)
        kwargs["api_key"] = api_key
        kwargs["voice"] = args.voice
    return kwargs


def run(
    text: str,
    engine_type: str,
    engine_kwargs: dict,
    output: str,
    verbose: bool,
    show_ssml: bool,
) -> str:
    """
    Full pipeline: detect emotion → map to voice params → [SSML] → synthesize.

    Returns the path of the written audio file.
    """
    detector = EmotionDetector()
    mapper = VoiceMapper()
    engine = create_engine(engine_type, **engine_kwargs)

    emotion_result = detector.detect(text)
    voice_params = mapper.map(emotion_result)

    if verbose:
        print(f"  Detected : {emotion_result}")
        print(f"  Voice    : {voice_params}")

    ssml_markup = generate_ssml(text, voice_params)

    if show_ssml:
        print("\n── Generated SSML ──────────────────────────────────────")
        print(ssml_markup)
        print("────────────────────────────────────────────────────────\n")

    # ElevenLabs manages its own prosody via voice settings, so we pass
    # plain text.  pyttsx3 on Windows can consume SSML natively.
    synth_text = text if engine_type in ("elevenlabs", "gtts") else ssml_markup

    output_path = engine.synthesize(synth_text, voice_params, output)
    return output_path


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    text = resolve_text(args.text)
    if not text:
        parser.error("No text provided.")

    engine_kwargs = build_engine_kwargs(args)

    try:
        output_path = run(
            text=text,
            engine_type=args.engine,
            engine_kwargs=engine_kwargs,
            output=args.output,
            verbose=args.verbose,
            show_ssml=args.ssml,
        )
        print(f"Audio saved to: {output_path}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
