"""
Empathy Engine – Streamlit web interface.

Run locally:
    streamlit run streamlit_app.py

Deploy on Streamlit Cloud:
    Push to GitHub, connect the repo, and set ELEVENLABS_API_KEY in the
    app's Secrets manager.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

import streamlit as st

# Ensure the project root is importable when running via `streamlit run`
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.emotion import EmotionDetector
from app.mapper import VoiceMapper
from app.tts_engine import ELEVENLABS_VOICES, create_engine

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Empathy Engine",
    page_icon="🎙️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .main-title {
        font-size: 2.4rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        line-height: 1.2;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        color: #94a3b8;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    .emotion-card {
        background: #1e1e2e;
        border-radius: 14px;
        padding: 1.2rem 1.6rem;
        border: 1px solid #2d2d44;
        margin: 1rem 0;
    }
    .emotion-label {
        font-size: 1.5rem;
        font-weight: 700;
        text-transform: capitalize;
        margin-bottom: 0.3rem;
    }
    .param-row {
        display: flex;
        gap: 1.5rem;
        flex-wrap: wrap;
        margin-top: 0.6rem;
    }
    .param-chip {
        background: #2d2d44;
        border-radius: 8px;
        padding: 0.3rem 0.75rem;
        font-size: 0.82rem;
        color: #cbd5e1;
    }
    .param-chip span { color: #e2e8f0; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Emotion styling
# ---------------------------------------------------------------------------

_EMOTION_META = {
    "positive":  {"emoji": "😊", "color": "#22c55e", "desc": "Upbeat and energetic delivery"},
    "negative":  {"emoji": "😔", "color": "#f87171", "desc": "Slow, subdued, lower pitch"},
    "neutral":   {"emoji": "😐", "color": "#94a3b8", "desc": "Calm, default vocal quality"},
    "surprise":  {"emoji": "😲", "color": "#f59e0b", "desc": "Fast, high-energy, expressive"},
    "curiosity": {"emoji": "🤔", "color": "#38bdf8", "desc": "Slightly quickened, inquisitive tone"},
    "concern":   {"emoji": "😟", "color": "#fb923c", "desc": "Measured, careful, softer delivery"},
}

# ---------------------------------------------------------------------------
# API key resolution
# ---------------------------------------------------------------------------

def _resolve_api_key() -> str:
    """Try Streamlit secrets first, then environment variable."""
    try:
        return st.secrets["ELEVENLABS_API_KEY"]
    except (KeyError, FileNotFoundError):
        return os.environ.get("ELEVENLABS_API_KEY", "")


# ---------------------------------------------------------------------------
# Core pipeline (cached per unique (text, voice, engine))
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=600)
def _synthesize(
    text: str,
    engine_type: str,
    voice: str,
    api_key: str,
) -> tuple[bytes, str, float, dict]:
    """
    Run the full emotion → synthesis pipeline.

    Returns
    -------
    audio_bytes : bytes
    emotion     : str
    intensity   : float
    params_dict : dict  (for display)
    """
    detector = EmotionDetector()
    mapper = VoiceMapper()

    emotion_result = detector.detect(text)
    voice_params = mapper.map(emotion_result)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        kwargs: dict = {}
        if engine_type == "elevenlabs":
            kwargs = {"api_key": api_key, "voice": voice}

        engine = create_engine(engine_type, **kwargs)
        engine.synthesize(text, voice_params, tmp_path)
        audio_bytes = Path(tmp_path).read_bytes()
    finally:
        if Path(tmp_path).exists():
            Path(tmp_path).unlink()

    params_dict = {
        "Rate": f"{voice_params.rate} wpm",
        "Volume": f"{voice_params.volume:.0%}",
        "Pitch": f"{voice_params.pitch_semitones:+.1f} st",
        "EL Speed": f"{voice_params.el_speed:.2f}×",
        "EL Stability": f"{voice_params.el_stability:.2f}",
        "EL Style": f"{voice_params.el_style:.2f}",
    }

    return audio_bytes, emotion_result.emotion, emotion_result.intensity, params_dict


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.markdown('<p class="main-title">🎙️ Empathy Engine</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Type anything — the engine detects your emotional tone '
    "and shapes the voice to match.</p>",
    unsafe_allow_html=True,
)

# Sidebar – configuration
with st.sidebar:
    st.header("⚙️ Configuration")

    engine_type = st.selectbox(
        "TTS Backend",
        options=["elevenlabs", "gtts", "pyttsx3"],
        index=0,
        help="ElevenLabs produces the highest quality output.",
    )

    voice_name = "Rachel"
    if engine_type == "elevenlabs":
        voice_name = st.selectbox(
            "Voice",
            options=list(ELEVENLABS_VOICES.keys()),
            index=0,
        )

        manual_key = st.text_input(
            "ElevenLabs API Key",
            type="password",
            placeholder="sk_… (or set via Secrets / env var)",
            help="Leave blank if you have set ELEVENLABS_API_KEY as a secret.",
        )
    else:
        manual_key = ""

    st.divider()
    st.caption("Emotion → Voice Mapping")
    for emotion, meta in _EMOTION_META.items():
        st.markdown(
            f"{meta['emoji']} **{emotion.capitalize()}** — {meta['desc']}"
        )

# Main area
sample_texts = {
    "Custom…": "",
    "😊 Positive":  "I just got promoted and honestly couldn't be happier – this is incredible!",
    "😔 Negative":  "This has been the worst week of my life. Nothing is going right.",
    "😐 Neutral":   "The meeting is scheduled for Tuesday at three in the afternoon.",
    "😲 Surprise":  "Wow, I absolutely cannot believe that just happened! No way!",
    "🤔 Curiosity": "I wonder how black holes form and what actually happens beyond the event horizon.",
    "😟 Concern":   "I'm really worried about the test results – I just don't know what to expect.",
}

preset = st.selectbox("Quick presets", options=list(sample_texts.keys()), index=0)
default_text = sample_texts[preset]

text = st.text_area(
    "Your text",
    value=default_text,
    height=130,
    placeholder="Type something with feeling…",
    label_visibility="collapsed",
)

col1, col2 = st.columns([3, 1])
with col1:
    speak_btn = st.button("🎙️ Generate Speech", use_container_width=True, type="primary")
with col2:
    clear_btn = st.button("Clear", use_container_width=True)

if clear_btn:
    st.rerun()

# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

if speak_btn:
    if not text.strip():
        st.warning("Please enter some text first.")
        st.stop()

    api_key = manual_key.strip() or _resolve_api_key()

    if engine_type == "elevenlabs" and not api_key:
        st.error(
            "No ElevenLabs API key found.  Add it in the sidebar, set the "
            "`ELEVENLABS_API_KEY` environment variable, or switch to gTTS / pyttsx3."
        )
        st.stop()

    with st.spinner("Analysing emotion and synthesising speech…"):
        try:
            audio_bytes, emotion, intensity, params = _synthesize(
                text=text.strip(),
                engine_type=engine_type,
                voice=voice_name,
                api_key=api_key,
            )
        except Exception as exc:
            st.error(f"Synthesis failed: {exc}")
            st.stop()

    meta = _EMOTION_META.get(emotion, _EMOTION_META["neutral"])
    color = meta["color"]
    emoji = meta["emoji"]

    # Emotion card
    intensity_pct = int(intensity * 100)
    st.markdown(
        f"""
        <div class="emotion-card">
            <div class="emotion-label" style="color:{color}">
                {emoji} {emotion.capitalize()}
            </div>
            <div style="color:#94a3b8;font-size:0.85rem;margin-bottom:0.6rem">
                {meta['desc']} &nbsp;·&nbsp; Intensity {intensity_pct}%
            </div>
            <div style="background:#0f1117;border-radius:8px;height:8px;overflow:hidden">
                <div style="width:{intensity_pct}%;height:100%;
                            background:linear-gradient(90deg,{color}88,{color});
                            border-radius:8px;transition:width 0.4s ease">
                </div>
            </div>
            <div class="param-row">
                {"".join(
                    f'<div class="param-chip">{k}&nbsp;<span>{v}</span></div>'
                    for k, v in params.items()
                )}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Audio player
    st.audio(audio_bytes, format="audio/mp3")

    # Download button
    ts = int(time.time())
    st.download_button(
        label="⬇️ Download audio",
        data=audio_bytes,
        file_name=f"empathy-engine-{emotion}-{ts}.mp3",
        mime="audio/mpeg",
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "Empathy Engine · "
    "emotion detection via [VADER](https://github.com/cjhutto/vaderSentiment) · "
    "speech synthesis via [ElevenLabs](https://elevenlabs.io)"
)
