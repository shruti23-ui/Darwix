"""
Empathy Engine – FastAPI REST server.

Endpoints
---------
GET  /          Simple HTML interface with a textarea and audio player.
POST /speak     Accept JSON { "text": "...", "engine": "pyttsx3" },
                synthesize, and stream back the audio file.
GET  /health    Liveness probe.

Run with:
    uvicorn api.server:app --reload --port 8000
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from app.emotion import EmotionDetector
from app.mapper import VoiceMapper
from app.tts_engine import create_engine

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Empathy Engine",
    description="Text-to-speech with emotion-driven vocal modulation.",
    version="1.0.0",
)

_OUTPUTS_DIR = Path("outputs")
_OUTPUTS_DIR.mkdir(exist_ok=True)

_detector = EmotionDetector()
_mapper = VoiceMapper()

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="Text to synthesize.")
    engine: Literal["pyttsx3", "gtts"] = Field(
        "pyttsx3", description="TTS backend (pyttsx3 = offline, gtts = Google TTS)."
    )
    output_format: Literal["wav", "mp3"] = Field(
        "wav", description="Audio container format."
    )


class SpeakMetadata(BaseModel):
    emotion: str
    intensity: float
    rate: int
    volume: float
    pitch_semitones: float
    audio_url: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok", "timestamp": int(time.time())}


@app.post(
    "/speak",
    response_class=FileResponse,
    summary="Synthesize emotionally expressive speech",
    responses={
        200: {"content": {"audio/wav": {}, "audio/mpeg": {}}},
        422: {"description": "Validation error"},
        500: {"description": "Synthesis failed"},
    },
)
def speak(request: SpeakRequest) -> FileResponse:
    """
    Detect the emotion in *text*, compute voice parameters, synthesize
    speech, and return the audio file directly.

    Emotion and voice metadata are attached as custom response headers:

    - ``X-Emotion``
    - ``X-Intensity``
    - ``X-Rate``
    - ``X-Volume``
    - ``X-Pitch-Semitones``
    """
    emotion_result = _detector.detect(request.text)
    voice_params = _mapper.map(emotion_result)

    filename = f"{uuid.uuid4().hex}.{request.output_format}"
    output_path = _OUTPUTS_DIR / filename

    try:
        engine = create_engine(request.engine)
        engine.synthesize(request.text, voice_params, str(output_path))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {exc}") from exc

    media_type = "audio/wav" if request.output_format == "wav" else "audio/mpeg"

    return FileResponse(
        path=str(output_path),
        media_type=media_type,
        filename=f"empathy-engine.{request.output_format}",
        headers={
            "X-Emotion": voice_params.emotion,
            "X-Intensity": str(voice_params.intensity),
            "X-Rate": str(voice_params.rate),
            "X-Volume": str(voice_params.volume),
            "X-Pitch-Semitones": str(voice_params.pitch_semitones),
        },
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Empathy Engine</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f1117;
      color: #e2e8f0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .card {
      background: #1a1d2e;
      border: 1px solid #2d3148;
      border-radius: 16px;
      padding: 2.5rem;
      width: min(560px, 95vw);
      box-shadow: 0 8px 40px rgba(0,0,0,0.5);
    }
    h1 { font-size: 1.6rem; font-weight: 700; margin-bottom: 0.4rem; }
    .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    label { display: block; font-size: 0.82rem; color: #94a3b8; margin-bottom: 0.4rem; }
    textarea {
      width: 100%; height: 120px; padding: 0.75rem 1rem;
      background: #0f1117; border: 1px solid #2d3148; border-radius: 10px;
      color: #e2e8f0; font-size: 1rem; resize: vertical;
      outline: none; transition: border-color 0.2s;
    }
    textarea:focus { border-color: #6366f1; }
    .row { display: flex; gap: 1rem; margin-top: 1rem; }
    select {
      flex: 1; padding: 0.6rem 0.9rem;
      background: #0f1117; border: 1px solid #2d3148; border-radius: 8px;
      color: #e2e8f0; font-size: 0.9rem; cursor: pointer;
    }
    button {
      flex: 1; padding: 0.65rem 1.2rem;
      background: #6366f1; border: none; border-radius: 8px;
      color: #fff; font-size: 0.95rem; font-weight: 600;
      cursor: pointer; transition: background 0.2s;
    }
    button:hover { background: #4f52e0; }
    button:disabled { background: #3d3f6b; cursor: not-allowed; }
    .status {
      margin-top: 1.2rem; font-size: 0.85rem; color: #94a3b8;
      min-height: 1.2em;
    }
    .emotion-badge {
      display: inline-block; margin-top: 0.8rem;
      padding: 0.25rem 0.75rem; border-radius: 999px;
      font-size: 0.8rem; font-weight: 600; text-transform: capitalize;
    }
    audio { width: 100%; margin-top: 1.2rem; border-radius: 8px; }
    .err { color: #f87171; }
  </style>
</head>
<body>
<div class="card">
  <h1>🎙️ Empathy Engine</h1>
  <p class="subtitle">Converts text into emotionally expressive speech.</p>

  <label for="txt">Your text</label>
  <textarea id="txt" placeholder="Type something with feeling…">I just got some incredible news – I'm so excited!</textarea>

  <div class="row">
    <select id="engine">
      <option value="pyttsx3">pyttsx3 (offline)</option>
      <option value="gtts">gTTS (Google)</option>
    </select>
    <select id="fmt">
      <option value="wav">WAV</option>
      <option value="mp3">MP3</option>
    </select>
    <button id="btn" onclick="speak()">Speak</button>
  </div>

  <div class="status" id="status"></div>
  <div id="badge-wrap"></div>
  <audio id="player" controls style="display:none"></audio>
</div>

<script>
  const EMOTION_COLORS = {
    positive: "#22c55e", negative: "#f87171", neutral: "#94a3b8",
    surprise: "#f59e0b", curiosity: "#38bdf8", concern: "#fb923c",
  };

  async function speak() {
    const text = document.getElementById("txt").value.trim();
    if (!text) return;

    const btn = document.getElementById("btn");
    const status = document.getElementById("status");
    const player = document.getElementById("player");
    const badgeWrap = document.getElementById("badge-wrap");

    btn.disabled = true;
    status.textContent = "Synthesizing…";
    status.className = "status";
    badgeWrap.innerHTML = "";
    player.style.display = "none";

    try {
      const resp = await fetch("/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          engine: document.getElementById("engine").value,
          output_format: document.getElementById("fmt").value,
        }),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || resp.statusText);
      }

      const emotion = resp.headers.get("X-Emotion") || "neutral";
      const intensity = parseFloat(resp.headers.get("X-Intensity") || "0.5");
      const rate = resp.headers.get("X-Rate");
      const pitch = resp.headers.get("X-Pitch-Semitones");

      const blob = await resp.blob();
      player.src = URL.createObjectURL(blob);
      player.style.display = "block";
      player.play();

      const color = EMOTION_COLORS[emotion] || "#94a3b8";
      badgeWrap.innerHTML = `<span class="emotion-badge" style="background:${color}22;color:${color}">
        ${emotion} &nbsp; ${(intensity * 100).toFixed(0)}%
      </span>`;
      status.textContent = `Rate: ${rate} wpm  ·  Pitch: ${parseFloat(pitch) >= 0 ? "+" : ""}${parseFloat(pitch).toFixed(2)} semitones`;

    } catch (e) {
      status.innerHTML = `<span class="err">Error: ${e.message}</span>`;
    } finally {
      btn.disabled = false;
    }
  }

  document.getElementById("txt").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.ctrlKey) speak();
  });
</script>
</body>
</html>"""
