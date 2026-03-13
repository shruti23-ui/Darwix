# Empathy Engine

A Python service that converts text into emotionally expressive speech.
The engine detects the emotional tone of input text and adjusts vocal
characteristics—speaking rate, pitch, and volume—to match that emotion
before synthesising the final audio file.

---

## Features

| Capability | Details |
|---|---|
| Emotion detection | VADER sentiment analysis + keyword pattern matching |
| Emotion categories | positive, negative, neutral, surprise, curiosity, concern |
| Intensity scaling | Each emotion's vocal effect scales with detected intensity |
| TTS backends | pyttsx3 (offline) and gTTS (Google, online) |
| Pitch modulation | Post-processing via pydub sample-rate manipulation |
| Output formats | WAV (default) or MP3 |
| Interfaces | CLI and FastAPI REST server with web UI |

---

## Project Structure

```
empathy-engine/
├── app/
│   ├── emotion.py      Emotion detection (VADER + keyword patterns)
│   ├── mapper.py       Emotion → VoiceParameters mapping
│   ├── tts_engine.py   TTS synthesis + pydub post-processing
│   └── main.py         CLI entry point
├── api/
│   └── server.py       FastAPI server with web UI
├── outputs/            Generated audio files land here
├── requirements.txt
└── README.md
```

---

## Installation

### 1. Clone and create a virtual environment

```bash
git clone <repo-url> empathy-engine
cd empathy-engine
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install ffmpeg (required for MP3 support)

| OS | Command |
|---|---|
| Windows | `winget install Gyan.FFmpeg` |
| macOS | `brew install ffmpeg` |
| Ubuntu/Debian | `sudo apt install ffmpeg` |

> WAV output does **not** require ffmpeg.

---

## Running the CLI

```bash
# Basic usage – detects emotion and writes outputs/output.wav
python app/main.py "I just got promoted, this is amazing!"

# Verbose output (shows emotion + voice parameters)
python app/main.py -v "I'm really worried about the deadline."

# Choose engine and output path
python app/main.py --engine gtts --output outputs/greet.mp3 "Hello there!"

# Read from stdin
echo "What a fascinating question!" | python app/main.py -

# Show help
python app/main.py --help
```

### CLI output example

```
  Detected : positive (intensity=0.82)
  Voice    : VoiceParameters(emotion=positive, intensity=0.82, rate=208 wpm, volume=0.94, pitch=+2.05 st)
Audio saved to: outputs/output.wav
```

---

## Running the API Server

```bash
uvicorn api.server:app --reload --port 8000
```

Then open [http://localhost:8000](http://localhost:8000) in your browser to
use the web interface, or call the API programmatically:

### POST /speak

```bash
curl -X POST http://localhost:8000/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Wow, that is absolutely incredible!", "engine": "pyttsx3", "output_format": "wav"}' \
  --output response.wav
```

**Request body**

```json
{
  "text": "string (1–2000 chars)",
  "engine": "pyttsx3 | gtts",
  "output_format": "wav | mp3"
}
```

**Response**

The audio file is returned directly (`audio/wav` or `audio/mpeg`).
Emotion metadata is available in the response headers:

| Header | Example |
|---|---|
| `X-Emotion` | `positive` |
| `X-Intensity` | `0.823` |
| `X-Rate` | `208` |
| `X-Volume` | `0.94` |
| `X-Pitch-Semitones` | `2.058` |

### GET /health

```bash
curl http://localhost:8000/health
# {"status":"ok","timestamp":1710000000}
```

---

## Emotion-to-Voice Mapping

Emotion detection uses two layers:

1. **VADER sentiment analysis** — produces a compound score in [-1, 1].
2. **Keyword pattern matching** — identifies surprise, curiosity, and concern
   from lexical cues that VADER's polarity model doesn't capture well.

Once an emotion and its intensity are determined, voice parameters are
computed by linearly interpolating the emotion's *maximum delta* profile
against the detected intensity (0 = no effect, 1 = full effect):

| Emotion | Rate delta (WPM) | Volume delta | Pitch (semitones) |
|---|---|---|---|
| positive | +28 | +0.07 | +2.5 |
| negative | −32 | −0.12 | −3.0 |
| neutral | 0 | 0 | 0 |
| surprise | +38 | +0.10 | +4.0 |
| curiosity | +12 | +0.02 | +1.5 |
| concern | −22 | −0.06 | −1.5 |

Base values: **185 WPM**, **0.88 volume**.

For example, a *positive* sentence with intensity 0.8 will produce:
- Rate: 185 + 28 × 0.8 = **207 WPM**
- Volume: 0.88 + 0.07 × 0.8 = **0.94**
- Pitch: +2.5 × 0.8 = **+2.0 semitones**

Pitch is applied in post-processing using pydub's sample-rate trick:
the synthesised WAV is respawned at `frame_rate × 2^(semitones/12)` then
resampled back to the original sample rate.

---

## Backends

### pyttsx3 (default, offline)

Uses the OS speech engine (Windows SAPI5, macOS NSSpeech, Linux eSpeak).
No network access required.  Rate and volume are set natively; pitch
adjustment is applied in post-processing.

```bash
python app/main.py --engine pyttsx3 "..."
```

### gTTS (online)

Uses Google's Text-to-Speech API.  Produces more natural-sounding audio
but requires an internet connection.  All voice modulation is done via
pydub post-processing.

```bash
python app/main.py --engine gtts "..."
```

---

## Example Sentences

```
Positive  : "I just got promoted and I couldn't be happier!"
Negative  : "This has been the worst week of my life."
Neutral   : "The meeting is scheduled for Tuesday at three."
Surprise  : "Wow, I can't believe that just happened!"
Curiosity : "I wonder how black holes actually form."
Concern   : "I'm really worried about the test results."
```

---

## License

MIT
