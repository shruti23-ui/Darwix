"""
Empathy Engine – Streamlit web interface.

Run locally:
    streamlit run streamlit_app.py

Deploy on Streamlit Cloud:
    Set ELEVENLABS_API_KEY in the app's Secrets manager.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parent
os.chdir(_ROOT)
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.emotion import EmotionDetector
from app.mapper import VoiceMapper
from app.ssml import generate_ssml
from app.tts_engine import ELEVENLABS_VOICES, create_engine

st.set_page_config(
    page_title="Empathy Engine",
    page_icon="🎙️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .main-title {
        font-size: 2.4rem; font-weight: 700;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text; line-height: 1.2; margin-bottom: 0.2rem;
    }
    .subtitle { color: #94a3b8; font-size: 1rem; margin-bottom: 1.6rem; }

    .voice-card {
        background: #1e1e2e; border: 1.5px solid #2d2d44;
        border-radius: 12px; padding: 0.7rem 1rem;
        text-align: center; min-height: 72px;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
    }
    .voice-card.selected { border-color: #6366f1; background: #1a1a3e; }
    .voice-name { font-weight: 600; font-size: 0.9rem; color: #e2e8f0; }
    .voice-desc { font-size: 0.72rem; color: #64748b; margin-top: 2px; }

    .emotion-card {
        background: #1e1e2e; border-radius: 14px;
        padding: 1.2rem 1.6rem; border: 1px solid #2d2d44; margin: 1rem 0;
    }
    .emotion-label {
        font-size: 1.5rem; font-weight: 700;
        text-transform: capitalize; margin-bottom: 0.3rem;
    }
    .param-row { display: flex; gap: 0.8rem; flex-wrap: wrap; margin-top: 0.7rem; }
    .param-chip {
        background: #2d2d44; border-radius: 8px;
        padding: 0.28rem 0.7rem; font-size: 0.8rem; color: #cbd5e1;
    }
    .param-chip span { color: #e2e8f0; font-weight: 600; }

    .section-label {
        font-size: 0.78rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.08em; color: #64748b; margin-bottom: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

_EMOTION_META = {
    "positive":  {"emoji": "😊", "color": "#22c55e", "desc": "Upbeat and energetic delivery"},
    "negative":  {"emoji": "😔", "color": "#f87171", "desc": "Slow, subdued, lower pitch"},
    "neutral":   {"emoji": "😐", "color": "#94a3b8", "desc": "Calm, default vocal quality"},
    "surprise":  {"emoji": "😲", "color": "#f59e0b", "desc": "Fast, high-energy, expressive"},
    "curiosity": {"emoji": "🤔", "color": "#38bdf8", "desc": "Slightly quickened, inquisitive tone"},
    "concern":   {"emoji": "😟", "color": "#fb923c", "desc": "Measured, careful, softer delivery"},
}

_VOICE_DESCRIPTIONS = {
    "Sarah":   "Mature, Reassuring",
    "Alice":   "Clear, Educator",
    "Laura":   "Quirky, Enthusiast",
    "Jessica": "Playful, Warm",
    "Matilda": "Professional",
    "Lily":    "Velvety, Actress",
    "Adam":    "Dominant, Firm",
    "Brian":   "Deep, Comforting",
    "Charlie": "Confident, Energetic",
    "Daniel":  "Steady, Broadcaster",
    "Eric":    "Smooth, Trustworthy",
    "George":  "Warm, Storyteller",
    "Liam":    "Energetic, Social",
    "River":   "Relaxed, Neutral",
    "Roger":   "Casual, Resonant",
    "Will":    "Relaxed Optimist",
}

_SAMPLE_TEXTS = {
    "Custom…": "",
    "😊 Positive":  "I just got promoted and honestly couldn't be happier – this is absolutely incredible!",
    "😔 Negative":  "This has been the worst week of my life. Nothing is going right at all.",
    "😐 Neutral":   "The meeting is scheduled for Tuesday at three in the afternoon.",
    "😲 Surprise":  "Wow, I absolutely cannot believe that just happened! No way!",
    "🤔 Curiosity": "I wonder how black holes form and what actually happens beyond the event horizon.",
    "😟 Concern":   "I'm really worried about the test results – I just don't know what to expect.",
}


def _resolve_api_key() -> str:
    try:
        return st.secrets["ELEVENLABS_API_KEY"]
    except (KeyError, FileNotFoundError):
        return os.environ.get("ELEVENLABS_API_KEY", "")


@st.cache_data(show_spinner=False, ttl=600)
def _synthesize(text: str, voice: str, api_key: str):
    detector = EmotionDetector()
    mapper = VoiceMapper()

    emotion_result = detector.detect(text)
    voice_params = mapper.map(emotion_result)
    ssml_markup = generate_ssml(text, voice_params)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        engine = create_engine("elevenlabs", api_key=api_key, voice=voice)
        engine.synthesize(text, voice_params, tmp_path)
        audio_bytes = Path(tmp_path).read_bytes()
    finally:
        if Path(tmp_path).exists():
            Path(tmp_path).unlink()

    params_dict = {
        "Speed":     f"{voice_params.el_speed:.2f}×",
        "Stability": f"{voice_params.el_stability:.2f}",
        "Style":     f"{voice_params.el_style:.2f}",
        "Rate":      f"{voice_params.rate} wpm",
        "Pitch":     f"{voice_params.pitch_semitones:+.1f} st",
        "Volume":    f"{voice_params.volume:.0%}",
    }

    return audio_bytes, emotion_result.emotion, emotion_result.intensity, params_dict, ssml_markup


# Header

st.markdown('<p class="main-title">🎙️ Empathy Engine</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Type anything — emotion is detected automatically '
    "and shapes the voice to match.</p>",
    unsafe_allow_html=True,
)

# API key

api_key = _resolve_api_key()
if not api_key:
    api_key = st.text_input(
        "ElevenLabs API Key",
        type="password",
        placeholder="sk_… (or set ELEVENLABS_API_KEY as an env var / Streamlit secret)",
    ).strip()

# Text input

preset = st.selectbox("Quick presets", options=list(_SAMPLE_TEXTS.keys()), label_visibility="collapsed")
text = st.text_area(
    "Your text",
    value=_SAMPLE_TEXTS[preset],
    height=120,
    placeholder="Type something with feeling…",
    label_visibility="collapsed",
)

# Voice selector

st.markdown('<p class="section-label" style="margin-top:0.8rem">Voice</p>', unsafe_allow_html=True)

voices = list(ELEVENLABS_VOICES.keys())
voice_labels = [f"{v}  —  {_VOICE_DESCRIPTIONS.get(v, '')}" for v in voices]
label_to_voice = dict(zip(voice_labels, voices))

selected_label = st.selectbox(
    "Choose voice",
    options=voice_labels,
    index=0,
    label_visibility="collapsed",
)
voice_name = label_to_voice[selected_label]

desc = _VOICE_DESCRIPTIONS.get(voice_name, "")
st.markdown(
    f"""<div class="voice-card selected"
            style="border-color:#6366f1;background:#1a1a3e;
                   max-width:260px;margin:0.3rem 0 0.6rem 0;">
        <div class="voice-name">{voice_name}</div>
        <div class="voice-desc">{desc}</div>
    </div>""",
    unsafe_allow_html=True,
)

# Generate button

st.markdown("")
col_btn, col_clr = st.columns([4, 1])
with col_btn:
    speak_btn = st.button("🎙️ Generate Speech", use_container_width=True, type="primary")
with col_clr:
    if st.button("Clear", use_container_width=True):
        st.rerun()

# Synthesis

if speak_btn:
    if not text.strip():
        st.warning("Please enter some text first.")
        st.stop()
    if not api_key:
        st.error("ElevenLabs API key required. Enter it above or set ELEVENLABS_API_KEY.")
        st.stop()

    with st.spinner("Detecting emotion and generating speech…"):
        try:
            audio_bytes, emotion, intensity, params, ssml_markup = _synthesize(
                text=text.strip(),
                voice=voice_name,
                api_key=api_key,
            )
        except Exception as exc:
            st.error(f"Synthesis failed: {exc}")
            st.stop()

    meta = _EMOTION_META.get(emotion, _EMOTION_META["neutral"])
    color = meta["color"]
    intensity_pct = int(intensity * 100)

    st.markdown(
        f"""
        <div class="emotion-card">
            <div class="emotion-label" style="color:{color}">
                {meta['emoji']} {emotion.capitalize()}
            </div>
            <div style="color:#94a3b8;font-size:0.85rem;margin-bottom:0.6rem">
                {meta['desc']} &nbsp;·&nbsp; Intensity {intensity_pct}%
            </div>
            <div style="background:#0f1117;border-radius:8px;height:8px;overflow:hidden">
                <div style="width:{intensity_pct}%;height:100%;
                            background:linear-gradient(90deg,{color}88,{color});
                            border-radius:8px"></div>
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

    st.audio(audio_bytes, format="audio/mp3")

    tab_dl, tab_ssml = st.tabs(["⬇️ Download", "📄 SSML Markup"])
    with tab_dl:
        st.download_button(
            label="Download audio",
            data=audio_bytes,
            file_name=f"empathy-engine-{emotion}-{int(time.time())}.mp3",
            mime="audio/mpeg",
            use_container_width=True,
        )
    with tab_ssml:
        st.caption(
            "W3C SSML 1.0 markup generated from the detected emotion — "
            "shows the expressive intent: prosody rate/pitch/volume, "
            "sentence breaks scaled to intensity, and emphasis on key words."
        )
        st.code(ssml_markup, language="xml")

# Sidebar

with st.sidebar:
    st.header("Emotion → Voice Mapping")
    st.caption("All deltas scale linearly with detected intensity (0–100%).")
    st.markdown(
        """
| Emotion | Speed | Stability | Style |
|---------|-------|-----------|-------|
| 😊 Positive | 1.15× | 0.35 | 0.65 |
| 😔 Negative | 0.82× | 0.72 | 0.20 |
| 😐 Neutral | 1.00× | 0.60 | 0.20 |
| 😲 Surprise | 1.22× | 0.18 | 0.85 |
| 🤔 Curiosity | 1.07× | 0.48 | 0.50 |
| 😟 Concern | 0.90× | 0.68 | 0.35 |
        """
    )

st.divider()
st.caption(
    "Empathy Engine · "
    "emotion via [VADER](https://github.com/cjhutto/vaderSentiment) · "
    "speech via [ElevenLabs](https://elevenlabs.io)"
)
