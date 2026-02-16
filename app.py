import time
import base64
import hashlib
from io import BytesIO
from datetime import date

import streamlit as st
from openai import OpenAI
from PIL import Image

# ===================== CONFIG =====================
st.set_page_config(page_title="PodCraftAI Studio", layout="wide")

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")
MAX_DAILY = int(st.secrets.get("MAX_DAILY_GENERATIONS", 10))
COOLDOWN = int(st.secrets.get("COOLDOWN_SECONDS", 15))

client = OpenAI(api_key=OPENAI_API_KEY)

# ===================== SECURITY =====================
def password_gate():
    if not APP_PASSWORD:
        return
    if st.session_state.get("authed"):
        return
    st.markdown("## 🔒 Access Required")
    pw = st.text_input("Enter access password", type="password")
    if st.button("Unlock"):
        if pw == APP_PASSWORD:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()

@st.cache_resource
def usage_store():
    return {}

def get_visitor_id() -> str:
    if "visitor_id" not in st.session_state:
        raw = f"{time.time()}::{st.session_state.get('_seed','')}"
        st.session_state.visitor_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return st.session_state.visitor_id

def rate_limit_ok(cost: int = 1) -> bool:
    vid = get_visitor_id()
    store = usage_store()
    key = f"{date.today()}:{vid}"

    used = store.get(key, 0)
    if used + cost > MAX_DAILY:
        st.warning(f"Daily limit reached ({MAX_DAILY}/day). Try again tomorrow.")
        return False

    last_ts = st.session_state.get("last_action_ts", 0.0)
    now = time.time()
    if now - last_ts < COOLDOWN:
        wait = int(COOLDOWN - (now - last_ts))
        st.info(f"Please wait {wait}s before trying again.")
        return False

    store[key] = used + cost
    st.session_state.last_action_ts = now
    return True

# Optional password
password_gate()

# ===================== STATE =====================
if "started" not in st.session_state:
    st.session_state.started = False
if "mode" not in st.session_state:
    st.session_state.mode = "Generate"  # Generate | Edit
if "last_result_bytes" not in st.session_state:
    st.session_state.last_result_bytes = None

# ===================== PRESETS =====================
PRESETS = {
    "Instagram Post (Square)": "1024x1024",
    "TikTok Cover (Vertical)": "1024x1536",
    "YouTube Thumbnail (Landscape)": "1536x1024",
    "Facebook Post (Landscape)": "1536x1024",
    "LinkedIn Banner (Wide)": "1536x1024",
    "Podcast Cover (Square)": "1024x1024",
}

CATEGORIES = [
    "YouTube Thumbnail",
    "TikTok Cover",
    "Instagram Post",
    "Facebook Post",
    "LinkedIn Banner",
    "Podcast Cover",
    "Business Promo",
    "Event Flyer",
    "Other / Custom",
]

DEFAULT_TEMPLATE_FOR_TYPE = {
    "YouTube Thumbnail": "YouTube Thumbnail (Landscape)",
    "TikTok Cover": "TikTok Cover (Vertical)",
    "Instagram Post": "Instagram Post (Square)",
    "Facebook Post": "Facebook Post (Landscape)",
    "LinkedIn Banner": "LinkedIn Banner (Wide)",
    "Podcast Cover": "Podcast Cover (Square)",
}

# ===================== STYLE (clean website feel) =====================
st.markdown(
    """
<style>
header {visibility:hidden;height:0px;}
footer {visibility:hidden;height:0px;}
#MainMenu {visibility:hidden;}

.block-container {max-width:1250px; padding-top: 1.2rem;}

.navbar{
  display:flex; align-items:center; justify-content:space-between;
  padding:14px 18px; border-radius:18px;
  background: rgba(255,255,255,0.75);
  border: 1px solid rgba(0,0,0,0.06);
  backdrop-filter: blur(10px);
}
.brand{display:flex; align-items:center; gap:12px; font-weight:900; font-size:18px;}
.logo{
  width:40px; height:40px; border-radius:14px;
  background:#2f6fed; color:white; display:flex; align-items:center; justify-content:center;
  font-weight:900;
}
.navlinks{display:flex; gap:22px; font-size:14px; color:#374151;}
.cta{background:#2f6fed;color:white;padding:10px 14px;border-radius:14px;font-weight:800;}

.hero{
  margin-top:16px; border-radius:26px; padding:28px;
  background: linear-gradient(135deg, rgba(47,111,237,0.10), rgba(99,102,241,0.06));
  border: 1px solid rgba(0,0,0,0.06);
}
.badge{
  display:inline-flex; align-items:center; gap:8px;
  padding:8px 14px; border-radius:999px;
  background: rgba(47,111,237,0.10); color:#1f3fb8; font-weight:800; font-size:13px;
}
.h1{margin-top:14px;font-size:54px;line-height:1.05;font-weight:950;color:#0f172a;}
.sub{margin-top:14px;font-size:18px;color:#334155;max-width:540px;}

.card{
  border-radius:24px;
  background: rgba(255,255,255,0.9);
  border: 1px solid rgba(0,0,0,0.06);
  padding:18px;
}
.preview{
  border-radius:28px;
  background: white;
  border: 1px solid rgba(0,0,0,0.06);
  padding:16px;
  box-shadow: 0 12px 30px rgba(2,6,23,0.08);
}
.muted{font-size:12px;color:#64748b;}
</style>
    """,
    unsafe_allow_html=True
)

# ===================== NAVBAR =====================
st.markdown(
    """
<div class="navbar">
  <div class="brand"><div class="logo">✓</div><div>PodCraftAI</div></div>
  <div class="navlinks"><div>Features</div><div>Pricing</div><div>FAQ</div></div>
  <div class="cta">Get Started</div>
</div>
    """,
    unsafe_allow_html=True
)

# ===================== HERO =====================
hero_left, hero_right = st.columns([1.15, 0.85], gap="large")

with hero_left:
    st.markdown('<div class="hero">', unsafe_allow_html=True)
    st.markdown('<div class="badge">● AI-Powered Social Media Tools</div>', unsafe_allow_html=True)
    st.markdown('<div class="h1">Create Stunning Social Content<br/>in Minutes</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub">Generate new graphics or edit your uploaded image for YouTube, TikTok, Instagram, Facebook, LinkedIn — and podcasts too.</div>', unsafe_allow_html=True)

    if not st.session_state.started:
        if st.button("Start Creating →", type="primary"):
            st.session_state.started = True
            st.rerun()
    else:
        st.success("Scroll down to the dashboard ✅")

    st.markdown("</div>", unsafe_allow_html=True)

with hero_right:
    st.markdown('<div class="preview">', unsafe_allow_html=True)
    st.markdown("**Preview**")
    st.markdown('<div class="muted">Your latest result will appear here.</div>', unsafe_allow_html=True)

    if st.session_state.last_result_bytes:
        st.image(Image.open(BytesIO(st.session_state.last_result_bytes)), use_container_width=True)
        st.download_button("Download PNG", st.session_state.last_result_bytes, file_name="design.png", use_container_width=True)
    else:
        st.info("No image yet. Use the dashboard below.")
    st.markdown("</div>", unsafe_allow_html=True)

# Stop here until user clicks Start Creating (real website flow)
if not st.session_state.started:
    st.stop()

st.markdown("")

# ===================== DASHBOARD (minimal) =====================
dash_left, dash_right = st.columns([1.0, 0.60], gap="large")

with dash_left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Dashboard")

    # Mode toggle (no extra buttons)
    st.session_state.mode = st.radio("Mode", ["Generate", "Edit"], horizontal=True)

    # Design type (auto sets template)
    category = st.selectbox("Design type", CATEGORIES, key="design_type")

    preset_options = list(PRESETS.keys())
    default_template = DEFAULT_TEMPLATE_FOR_TYPE.get(category, preset_options[0])

    # Auto-set only when design type changes (but still allows user override)
    if st.session_state.get("template_autoset") != category:
        st.session_state.template_size = default_template
        st.session_state.template_autoset = category

    # Template dropdown (auto selected)
    preset_name = st.selectbox(
        "Template size",
        preset_options,
        index=preset_options.index(st.session_state.get("template_size", default_template)),
        key="template_size"
    )
    size = PRESETS[preset_name]

    # Core inputs (minimal)
    title_text = st.text_input("Title (optional)", placeholder="e.g., Tech Talk Daily")
    subtitle_text = st.text_input("Subtitle (optional)", placeholder="e.g., weekly tech insights")
    instruction = st.text_area("What should it look like?", placeholder="e.g., modern, clean, blue gradient, add mic icon, leave space for title")

    # Conditional options (only show when needed)
    if category == "YouTube Thumbnail":
        yt_style = st.selectbox("YouTube style", ["Face + Big Text", "Icon + Big Text", "Clean Minimal"])
    else:
        yt_style = None

    # Advanced options hidden (removes clutter)
    with st.expander("Advanced (optional)"):
        style = st.selectbox("Style", ["Modern", "Minimal", "Bold", "Clean", "Luxury", "Fun"])
        colors = st.text_input("Colors (optional)", placeholder="e.g., blue & white, purple gradient")
        quality = st.selectbox("Quality (Generate only)", ["low", "medium", "high"])
    st.markdown("</div>", unsafe_allow_html=True)

with dash_right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Action")

    if st.session_state.mode == "Generate":
        if st.button("Generate Design", type="primary", use_container_width=True):
            if not rate_limit_ok(1):
                st.stop()

            style_txt = (style if "style" in locals() else "Modern")
            colors_txt = (colors if "colors" in locals() and colors.strip() else "designer choice")
            quality_txt = (quality if "quality" in locals() else "low")

            extra_bits = []
            if yt_style:
                extra_bits.append(f"YouTube style: {yt_style}")
            if instruction.strip():
                extra_bits.append(instruction)

            prompt = f"""
Create a professional social media design.
Design type: {category}.
Template size: {preset_name} ({size}).

Text (if possible):
Title: {title_text if title_text.strip() else "none"}
Subtitle: {subtitle_text if subtitle_text.strip() else "none"}

Style: {style_txt}.
Colors: {colors_txt}.

Instructions:
- Clean, modern, high contrast
- Leave space for readable text
- Don't overcrowd
Extra: {'; '.join(extra_bits) if extra_bits else 'none'}
"""
            with st.spinner("Generating..."):
                result = client.images.generate(
                    model="gpt-image-1",
                    prompt=prompt,
                    size=size,
                    quality=quality_txt
                )

            st.session_state.last_result_bytes = base64.b64decode(result.data[0].b64_json)
            st.success("Generated ✅ Check Preview at the top-right.")
            st.rerun()

    else:
        uploaded = st.file_uploader("Upload image (PNG/JPG)", type=["png", "jpg", "jpeg"])
        if uploaded:
            original_bytes = uploaded.read()
            try:
                original_img = Image.open(BytesIO(original_bytes))
                st.image(original_img, use_container_width=True)
            except Exception:
                st.error("Could not read this image.")
                st.stop()

            if st.button("Apply AI Edit", type="primary", use_container_width=True):
                if not instruction.strip():
                    st.error("Write what you want to change in 'What should it look like?'")
                    st.stop()

                if not rate_limit_ok(1):
                    st.stop()

                # Convert to PNG + resize
                img = Image.open(BytesIO(original_bytes)).convert("RGBA")
                MAX_SIDE = 1024
                w, h = img.size
                scale = min(MAX_SIDE / max(w, h), 1.0)
                if scale < 1.0:
                    img = img.resize((int(w * scale), int(h * scale)))

                png_buffer = BytesIO()
                img.save(png_buffer, format="PNG")
                png_buffer.seek(0)
                png_buffer.name = "upload.png"

                style_txt = (style if "style" in locals() else "Modern")
                colors_txt = (colors if "colors" in locals() and colors.strip() else "keep consistent or improve")

                extra_bits = []
                if yt_style:
                    extra_bits.append(f"YouTube style: {yt_style}")
                extra_bits.append(instruction)

                final_prompt = f"""
Edit the uploaded image into a professional social media design.
Target design type: {category}.
Target template: {preset_name} ({size}).

User request: {'; '.join(extra_bits)}

Text (if requested):
Title: {title_text if title_text.strip() else "none"}
Subtitle: {subtitle_text if subtitle_text.strip() else "none"}

Style: {style_txt}.
Colors: {colors_txt}.

Important:
- Keep main subject recognizable unless user requests otherwise.
- Improve lighting/contrast if needed.
- Leave space for readable text.
"""
                with st.spinner("Editing..."):
                    edited = client.images.edit(
                        model="gpt-image-1",
                        image=png_buffer,
                        prompt=final_prompt,
                        size=size
                    )

                st.session_state.last_result_bytes = base64.b64decode(edited.data[0].b64_json)
                st.success("Edited ✅ Check Preview at the top-right.")
                st.rerun()
        else:
            st.info("Upload an image to edit it.")
    st.markdown("</div>", unsafe_allow_html=True)
