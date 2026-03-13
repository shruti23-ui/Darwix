"""
Empathy Engine – CLI entry point.

Usage examples
--------------
# Speak a short phrase using the default pyttsx3 engine:
    python app/main.py "I just got promoted!"

# Use gTTS and save as MP3:
    python app/main.py --engine gtts --output outputs/result.mp3 "This is concerning."

# Verbose mode (prints detected emotion + voice parameters):
    python app/main.py -v "Wow, that is absolutely stunning!"

# Read input from stdin:
    echo "I'm not sure about this…" | python app/main.py -
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.emotion import EmotionDetector
from app.mapper import VoiceMapper
from app.tts_engine import create_engine


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
        choices=["pyttsx3", "gtts"],
        default="pyttsx3",
        help="TTS backend to use (default: pyttsx3).",
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
    return parser


def resolve_text(raw: str) -> str:
    """Return the actual input text, reading from stdin if *raw* is '-'."""
    if raw == "-":
        if sys.stdin.isatty():
            print("Enter text (press Ctrl-D when done):")
        return sys.stdin.read().strip()
    return raw.strip()


def run(text: str, engine_type: str, output: str, verbose: bool) -> str:
    """
    Full pipeline: detect emotion → map to voice params → synthesize.

    Returns the path of the written audio file.
    """
    detector = EmotionDetector()
    mapper = VoiceMapper()
    engine = create_engine(engine_type)

    emotion_result = detector.detect(text)
    voice_params = mapper.map(emotion_result)

    if verbose:
        print(f"  Detected : {emotion_result}")
        print(f"  Voice    : {voice_params}")

    output_path = engine.synthesize(text, voice_params, output)
    return output_path


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    text = resolve_text(args.text)
    if not text:
        parser.error("No text provided.")

    try:
        output_path = run(
            text=text,
            engine_type=args.engine,
            output=args.output,
            verbose=args.verbose,
        )
        print(f"Audio saved to: {output_path}")
    except Exception as exc:  # pragma: no cover
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
