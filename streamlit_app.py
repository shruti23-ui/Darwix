"""
Empathy Engine – Streamlit web interface.

Run locally:
    streamlit run streamlit_app.py

Deploy on Streamlit Cloud:
    Set ELEVENLABS_API_KEY in the app's Secrets manager,
    or use the Google TTS engine which requires no API key.
"""

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
from app.mapper import VoiceMapper, VoiceParameters
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


def _resolve_api_key():
    try:
        return st.secrets["ELEVENLABS_API_KEY"]
    except (KeyError, FileNotFoundError):
        return os.environ.get("ELEVENLABS_API_KEY", "")


@st.cache_data(show_spinner=False, ttl=600)
def _detect(text):
    detector = EmotionDetector()
    mapper = VoiceMapper()
    result = detector.detect(text)
    params = mapper.map(result)
    return result.emotion, result.intensity, params


@st.cache_data(show_spinner=False, ttl=600)
def _synthesize(text, engine_type, voice, api_key,
                speed, stability, style, rate, pitch, volume,
                emotion, intensity):
    params = VoiceParameters(
        rate=rate,
        volume=volume,
        pitch_semitones=pitch,
        el_speed=speed,
        el_stability=stability,
        el_style=style,
        emotion=emotion,
        intensity=intensity,
    )

    ssml_markup = generate_ssml(text, params)

    suffix = ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name

    try:
        if engine_type == "elevenlabs":
            engine = create_engine("elevenlabs", api_key=api_key, voice=voice)
        else:
            engine = create_engine("gtts")
        engine.synthesize(text, params, tmp_path)
        audio_bytes = Path(tmp_path).read_bytes()
    finally:
        if Path(tmp_path).exists():
            Path(tmp_path).unlink()

    params_dict = {
        "Speed":  f"{params.el_speed:.2f}×",
        "Rate":   f"{params.rate} wpm",
        "Pitch":  f"{params.pitch_semitones:+.1f} st",
        "Volume": f"{params.volume:.0%}",
    }
    if engine_type == "elevenlabs":
        params_dict["Stability"] = f"{params.el_stability:.2f}"
        params_dict["Style"]     = f"{params.el_style:.2f}"

    return audio_bytes, params_dict, ssml_markup


# ── Header ────────────────────────────────────────────────────────────────────

st.markdown('<p class="main-title">🎙️ Empathy Engine</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Type anything — emotion is detected automatically '
    "and shapes the voice to match.</p>",
    unsafe_allow_html=True,
)

# ── Engine selector ───────────────────────────────────────────────────────────

st.markdown('<p class="section-label">TTS Engine</p>', unsafe_allow_html=True)
engine_choice = st.radio(
    "Engine",
    options=["ElevenLabs — Premium voices", "Google TTS — Free, no API key"],
    index=0,
    horizontal=True,
    label_visibility="collapsed",
)
use_elevenlabs = engine_choice.startswith("ElevenLabs")

# ── API key (only for ElevenLabs) ─────────────────────────────────────────────

api_key = ""
if use_elevenlabs:
    api_key = _resolve_api_key()
    if not api_key:
        api_key = st.text_input(
            "ElevenLabs API Key",
            type="password",
            placeholder="sk_… (or set ELEVENLABS_API_KEY as an env var / Streamlit secret)",
        ).strip()
else:
    st.info("Google TTS requires no API key and works everywhere.", icon="ℹ️")

# ── Text input ────────────────────────────────────────────────────────────────

preset = st.selectbox("Quick presets", options=list(_SAMPLE_TEXTS.keys()), label_visibility="collapsed")
text = st.text_area(
    "Your text",
    value=_SAMPLE_TEXTS[preset],
    height=120,
    placeholder="Type something with feeling…",
    label_visibility="collapsed",
)

# ── Voice selector (ElevenLabs only) ─────────────────────────────────────────

voice_name = "Sarah"
if use_elevenlabs:
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

# ── Advanced Controls ─────────────────────────────────────────────────────────

st.markdown('<p class="section-label" style="margin-top:1rem">Advanced Controls</p>', unsafe_allow_html=True)

with st.expander("⚙️ Override voice parameters & edit SSML"):
    use_manual = st.toggle(
        "Override auto-detected parameters",
        value=False,
        help="When on, the sliders below are used for synthesis instead of auto-detected values.",
    )

    st.markdown("**Voice Parameters**")
    c1, c2, c3 = st.columns(3)
    with c1:
        sl_speed     = st.slider("Speed",        0.7,  1.2,  1.00, 0.01, key="sl_speed")
        sl_stability = st.slider("Stability",    0.0,  1.0,  0.60, 0.01, key="sl_stability")
    with c2:
        sl_style     = st.slider("Style",        0.0,  1.0,  0.20, 0.01, key="sl_style")
        sl_rate      = st.slider("Rate (wpm)",   90,   320,  185,  1,    key="sl_rate")
    with c3:
        sl_pitch     = st.slider("Pitch (st)",  -5.0,  5.0,  0.0,  0.1,  key="sl_pitch")
        sl_volume    = st.slider("Volume",       0.10, 1.0,  0.88, 0.01, key="sl_volume")

    st.markdown("---")
    st.markdown("**SSML Markup Editor**")
    st.caption(
        "The SSML below is generated from the current parameters. "
        "Edit it freely — the markup is available for export or use with any SSML-compatible engine."
    )

    if text.strip():
        if use_manual:
            preview_params = VoiceParameters(
                rate=sl_rate, volume=sl_volume, pitch_semitones=sl_pitch,
                el_speed=sl_speed, el_stability=sl_stability, el_style=sl_style,
                emotion="neutral", intensity=1.0,
            )
        else:
            try:
                _em, _in, _vp = _detect(text.strip())
                preview_params = _vp
            except Exception:
                preview_params = VoiceParameters(
                    rate=185, volume=0.88, pitch_semitones=0.0,
                    el_speed=1.0, el_stability=0.6, el_style=0.2,
                    emotion="neutral", intensity=0.5,
                )
        default_ssml = generate_ssml(text.strip(), preview_params)
    else:
        default_ssml = '<?xml version="1.0" encoding="UTF-8"?>\n<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis">\n  <!-- enter text above to preview SSML -->\n</speak>'

    st.text_area(
        "SSML",
        value=default_ssml,
        height=220,
        label_visibility="collapsed",
        key="ssml_editor",
    )

# ── Generate button ───────────────────────────────────────────────────────────

st.markdown("")
col_btn, col_clr = st.columns([4, 1])
with col_btn:
    speak_btn = st.button("🎙️ Generate Speech", use_container_width=True, type="primary")
with col_clr:
    if st.button("Clear", use_container_width=True):
        st.rerun()

# ── Synthesis ─────────────────────────────────────────────────────────────────

if speak_btn:
    if not text.strip():
        st.warning("Please enter some text first.")
        st.stop()
    if use_elevenlabs and not api_key:
        st.error("ElevenLabs API key required. Enter it above or switch to Google TTS.")
        st.stop()

    with st.spinner("Detecting emotion and generating speech…"):
        try:
            emotion, intensity, auto_params = _detect(text.strip())

            if use_manual:
                final_speed     = sl_speed
                final_stability = sl_stability
                final_style     = sl_style
                final_rate      = sl_rate
                final_pitch     = sl_pitch
                final_volume    = sl_volume
            else:
                final_speed     = auto_params.el_speed
                final_stability = auto_params.el_stability
                final_style     = auto_params.el_style
                final_rate      = auto_params.rate
                final_pitch     = auto_params.pitch_semitones
                final_volume    = auto_params.volume

            engine_type = "elevenlabs" if use_elevenlabs else "gtts"

            audio_bytes, params, ssml_markup = _synthesize(
                text=text.strip(),
                engine_type=engine_type,
                voice=voice_name,
                api_key=api_key,
                speed=final_speed,
                stability=final_stability,
                style=final_style,
                rate=final_rate,
                pitch=final_pitch,
                volume=final_volume,
                emotion=emotion,
                intensity=intensity,
            )
        except Exception as exc:
            st.error(f"Synthesis failed: {exc}")
            st.stop()

    meta = _EMOTION_META.get(emotion, _EMOTION_META["neutral"])
    color = meta["color"]
    intensity_pct = int(intensity * 100)
    mode_note = " · <span style='color:#a855f7;font-size:0.78rem'>manual override</span>" if use_manual else ""

    st.markdown(
        f"""
        <div class="emotion-card">
            <div class="emotion-label" style="color:{color}">
                {meta['emoji']} {emotion.capitalize()}
            </div>
            <div style="color:#94a3b8;font-size:0.85rem;margin-bottom:0.6rem">
                {meta['desc']} &nbsp;·&nbsp; Intensity {intensity_pct}%{mode_note}
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
            "W3C SSML 1.0 markup used for this generation — "
            "prosody rate/pitch/volume, sentence breaks scaled to intensity, "
            "and emphasis on key words."
        )
        st.text_area(
            "Generated SSML",
            value=ssml_markup,
            height=220,
            label_visibility="collapsed",
            key="result_ssml",
        )

# ── Sidebar ───────────────────────────────────────────────────────────────────

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
| 😲 Surprise | 1.20× | 0.18 | 0.85 |
| 🤔 Curiosity | 1.07× | 0.48 | 0.50 |
| 😟 Concern | 0.90× | 0.68 | 0.35 |
        """
    )

st.divider()
st.caption(
    "Empathy Engine · "
    "emotion via [VADER](https://github.com/cjhutto/vaderSentiment) · "
    "speech via [ElevenLabs](https://elevenlabs.io) / [Google TTS](https://gtts.readthedocs.io)"
)
