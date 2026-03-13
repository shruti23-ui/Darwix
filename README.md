# Empathy Engine

> Dynamically modulates synthesized speech based on the detected emotional
> tone of the input text — moving beyond monotonic TTS delivery to achieve
> genuine emotional resonance.

---

## Assignment Checklist

| Requirement | Status | Details |
|---|---|---|
| Text input (CLI) | ✅ | `python app/main.py "..."` |
| Text input (API) | ✅ | `POST /speak` via FastAPI |
| Emotion detection (≥3 categories) | ✅ | 6 categories: positive, negative, neutral, surprise, curiosity, concern |
| Vocal parameter modulation (≥2 params) | ✅ | Rate, pitch, volume + EL speed, stability, style |
| Emotion-to-voice mapping | ✅ | Deterministic profile table with linear intensity scaling |
| Audio output (.mp3) | ✅ | ElevenLabs neural TTS → high-quality MP3 |
| **Bonus:** Granular emotions | ✅ | 6 emotions (3 beyond basic pos/neg/neutral) |
| **Bonus:** Intensity scaling | ✅ | All parameter deltas × detected intensity |
| **Bonus:** Web interface + audio player | ✅ | Streamlit UI with embedded player and download |
| **Bonus:** SSML integration | ✅ | `app/ssml.py` — W3C SSML 1.0 with prosody, break, emphasis |

---

## Project Structure

```
empathy-engine/
├── app/
│   ├── emotion.py      Emotion detection (VADER + keyword patterns)
│   ├── mapper.py       Emotion → VoiceParameters mapping
│   ├── ssml.py         W3C SSML 1.0 markup generator
│   ├── tts_engine.py   ElevenLabs synthesis engine
│   └── main.py         CLI entry point
├── api/
│   └── server.py       FastAPI REST server with HTML web UI
├── outputs/            Generated audio files
├── streamlit_app.py    Streamlit web interface
├── requirements.txt
└── README.md
```

---

## Installation

```bash
git clone https://github.com/shruti23-ui/Darwix.ai
cd Darwix.ai/empathy-engine

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Set your ElevenLabs API key:

```bash
# Option 1 — environment variable
export ELEVENLABS_API_KEY=sk_...          # Windows: set ELEVENLABS_API_KEY=sk_...

# Option 2 — Streamlit secret (for Streamlit Cloud)
# Add to .streamlit/secrets.toml:
# ELEVENLABS_API_KEY = "sk_..."
```

---

## Running

### Streamlit Web Interface

```bash
streamlit run streamlit_app.py
```

Opens at `http://localhost:8501` with:
- Voice selector dropdown (16 ElevenLabs premade voices)
- Preset example sentences for each emotion
- Emotion card with intensity bar and voice parameter breakdown
- Embedded audio player with download button
- SSML markup tab showing the generated XML

### CLI

```bash
# ElevenLabs (default voice — Sarah):
python app/main.py --engine elevenlabs --api-key sk_... "I just got promoted!"

# Choose a different voice:
python app/main.py --engine elevenlabs --voice Charlie --api-key sk_... "Wow!"

# Verbose — print detected emotion and voice parameters:
python app/main.py -v --api-key sk_... "I'm really worried about this."

# Print generated SSML markup:
python app/main.py --ssml --api-key sk_... "That is absolutely incredible!"

# Save as MP3:
python app/main.py --output outputs/result.mp3 --api-key sk_... "Hello!"

# Full help:
python app/main.py --help
```

Example output (`-v --ssml`):

```
  Detected : positive (intensity=0.82)
  Voice    : VoiceParameters(emotion=positive, rate=208 wpm, pitch=+2.05 st, el_speed=1.12)

Generated SSML:
<?xml version="1.0" encoding="UTF-8"?>
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis">
  <prosody rate="+15%" pitch="+2.05st" volume="loud">
    I just got promoted and I am so <emphasis level="strong">excited</emphasis>!
  </prosody>
</speak>

Audio saved to: outputs/output.mp3
```

### FastAPI REST Server

```bash
uvicorn api.server:app --reload --port 8000
```

Open `http://localhost:8000` for the HTML interface, or call the API directly:

```bash
curl -X POST http://localhost:8000/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Wow, I cannot believe this!", "engine": "elevenlabs", "api_key": "sk_..."}' \
  --output result.mp3
```

Response headers carry emotion metadata:

```
X-Emotion: surprise
X-Intensity: 0.83
X-Rate: 219
X-Pitch-Semitones: 3.32
```

---

## Design Choices: Emotion-to-Voice Mapping

### Layer 1 — Emotion Detection

Detection runs two passes in order:

1. **Keyword pattern matching** (regex) — catches emotions that sentiment
   polarity alone misses:

   | Emotion | Example triggers |
   |---|---|
   | Surprise | "wow", "incredible", "no way", "can't believe" |
   | Curiosity | "wonder", "fascinating", "what if", "how does" |
   | Concern | "worried", "nervous", "anxious", "afraid" |

2. **VADER compound score** — classifies the remainder:
   - ≥ 0.05 → **positive**
   - ≤ −0.05 → **negative**
   - Otherwise → **neutral**

   Intensity is derived from the magnitude of the compound score,
   clamped to [0.0, 1.0].

### Layer 2 — Voice Parameter Mapping

Each emotion has a *maximum delta profile* applied at intensity = 1.0.
At intermediate intensities all deltas scale linearly.

| Emotion | EL Speed | EL Stability | EL Style | Rate Δ | Pitch Δ |
|---|---|---|---|---|---|
| positive | 1.15× | 0.35 | 0.65 | +28 wpm | +2.5 st |
| negative | 0.82× | 0.72 | 0.20 | −32 wpm | −3.0 st |
| neutral  | 1.00× | 0.60 | 0.20 | 0 | 0 |
| surprise | 1.20× | 0.18 | 0.85 | +38 wpm | +4.0 st |
| curiosity| 1.07× | 0.48 | 0.50 | +12 wpm | +1.5 st |
| concern  | 0.90× | 0.68 | 0.35 | −22 wpm | −1.5 st |

**Worked example** — *"I just got promoted!"* (positive, intensity 0.82):

```
EL speed    = 1.0 + 0.15 × 0.82  = 1.12×
EL stability = 0.60 → 0.35 × 0.82 = 0.40
rate        = 185 + 28 × 0.82    = 208 wpm
pitch       = +2.5 × 0.82        = +2.05 semitones
```

### Layer 3 — SSML Generation

On every request `app/ssml.py` generates W3C SSML 1.0 markup:

- `<prosody rate="..." pitch="..." volume="...">` driven by the emotion profile
- `<break time="Nms"/>` at sentence and clause boundaries — durations scale
  with intensity (120 ms for surprise → 650 ms for negative/concern)
- `<emphasis level="strong|moderate|reduced">` on high-valence words

The markup is shown in the **SSML Markup** tab of the Streamlit UI on every
generation, giving full visibility into the expressive intent behind each
audio output.

---

## Example Sentences

```
Positive  : "I just got promoted and couldn't be happier!"
Negative  : "This has been the worst week of my life."
Neutral   : "The meeting is scheduled for Tuesday at three."
Surprise  : "Wow, I can't believe that just happened!"
Curiosity : "I wonder how black holes actually form."
Concern   : "I'm really worried about the test results."
```

---

## License

This project is licensed under the [MIT License](LICENSE) — free to use, modify, and distribute for any purpose, public or commercial, with attribution.
