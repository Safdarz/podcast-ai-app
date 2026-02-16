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
            st.success("Unlocked ✅")
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()

@st.cache_resource
def usage_store():
    return {}

def get_visitor_id() -> str:
    if "visitor_id" not in st.session_state:
        raw = f"{time.time()}::{st.session_state.get('_seed', '')}"
        st.session_state.visitor_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return st.session_state.visitor_id

def rate_limit_ok(cost: int = 1) -> bool:
    vid = get_visitor_id()
    store = usage_store()
    today = str(date.today())
    key = f"{today}:{vid}"

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

# Protect app (optional)
password_gate()

# ===================== STATE =====================
if "mode" not in st.session_state:
    st.session_state.mode = "create"  # create | edit
if "last_result_bytes" not in st.session_state:
    st.session_state.last_result_bytes = None

# ===================== STYLE (Canva-like) =====================
st.markdown(
    """
<style>
/* Hide default Streamlit header/footer */
header {visibility: hidden; height: 0px;}
footer {visibility: hidden; height: 0px;}
#MainMenu {visibility: hidden;}

.block-container {
  max-width: 1250px;
  padding-top: 1.2rem;
  padding-bottom: 2rem;
}

/* Top nav */
.navbar{
  display:flex; align-items:center; justify-content:space-between;
  padding:14px 18px;
  border-radius:18px;
  background: rgba(255,255,255,0.75);
  border: 1px solid rgba(0,0,0,0.06);
  backdrop-filter: blur(10px);
}
.brand{
  display:flex; align-items:center; gap:12px;
  font-weight:800; font-size:18px;
}
.logo{
  width:40px; height:40px; border-radius:14px;
  background:#2f6fed;
  display:flex; align-items:center; justify-content:center;
  color:white; font-weight:900;
}
.navlinks{
  display:flex; gap:22px;
  font-size:14px; color:#374151;
}
.navbtn{
  display:flex; gap:10px; align-items:center;
}
.btn-primary{
  background:#2f6fed; color:white;
  padding:10px 14px; border-radius:14px;
  font-weight:700; font-size:14px;
}
.btn-ghost{
  background:white; color:#111827;
  padding:10px 14px; border-radius:14px;
  border:1px solid rgba(0,0,0,0.10);
  font-weight:700; font-size:14px;
}

/* Hero */
.hero-wrap{
  margin-top:16px;
  border-radius:26px;
  padding:28px;
  background: linear-gradient(135deg, rgba(47,111,237,0.10), rgba(99,102,241,0.06));
  border: 1px solid rgba(0,0,0,0.06);
}
.badge{
  display:inline-flex; gap:8px; align-items:center;
  padding:8px 14px; border-radius:999px;
  background: rgba(47,111,237,0.10);
  color:#1f3fb8;
  font-weight:700; font-size:13px;
}
.hero-title{
  margin-top:14px;
  font-size:54px; line-height:1.05;
  font-weight:900;
  color:#0f172a;
}
.hero-sub{
  margin-top:14px;
  font-size:18px;
  color:#334155;
  max-width: 520px;
}

/* Cards */
.card{
  border-radius:24px;
  background: rgba(255,255,255,0.85);
  border: 1px solid rgba(0,0,0,0.06);
  padding:18px;
}
.preview-card{
  border-radius:28px;
  background: white;
  border: 1px solid rgba(0,0,0,0.06);
  padding:16px;
  box-shadow: 0 12px 30px rgba(2,6,23,0.08);
}
.small-muted{
  font-size:12px; color:#64748b;
}
.section-title{
  font-size:16px; font-weight:900; color:#0f172a;
  margin:0 0 10px 0;
}

/* Step buttons */
.stepbar{
  display:flex; gap:10px; flex-wrap:wrap;
}
.step{
  padding:10px 14px;
  border-radius:999px;
  border:1px solid rgba(0,0,0,0.10);
  background:white;
  font-weight:800;
}
.step-active{
  border-color: rgba(47,111,237,0.35);
  background: rgba(47,111,237,0.10);
  color:#1f3fb8;
}
</style>
    """,
    unsafe_allow_html=True
)

# ===================== NAVBAR =====================
st.markdown(
    """
<div class="navbar">
  <div class="brand">
    <div class="logo">✓</div>
    <div>PodCraftAI</div>
  </div>
  <div class="navlinks">
    <div>Features</div>
    <div>Pricing</div>
    <div>FAQ</div>
  </div>
  <div class="navbtn">
    <div style="color:#2f6fed;font-weight:800;">Log In</div>
    <div class="btn-primary">Get Started</div>
  </div>
</div>
    """,
    unsafe_allow_html=True
)

# ===================== HERO (2 columns like Canva) =====================
left, right = st.columns([1.15, 0.85], gap="large")

with left:
    st.markdown('<div class="hero-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="badge">● AI-Powered Design Tools</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">Create Stunning Social Content<br/>in Minutes</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">AI-powered tools to design, edit, and export images for Instagram, TikTok, YouTube, Facebook, LinkedIn — and podcasts too.</div>', unsafe_allow_html=True)

    cta1, cta2 = st.columns([0.52, 0.48], gap="medium")
    with cta1:
        if st.button("Start Creating →", use_container_width=True):
            st.session_state.mode = "create"
            st.rerun()
    with cta2:
        if st.button("▶ See Demo", use_container_width=True):
            st.info("Demo tip: Generate an image, then switch to Edit Upload.")
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="preview-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Preview</div>', unsafe_allow_html=True)
    st.markdown('<div class="small-muted">Your latest result appears here. Download when ready.</div>', unsafe_allow_html=True)

    if st.session_state.last_result_bytes:
        st.image(Image.open(BytesIO(st.session_state.last_result_bytes)), use_container_width=True)
        st.download_button(
            "Download PNG",
            st.session_state.last_result_bytes,
            file_name="design.png",
            use_container_width=True
        )
    else:
        st.info("No image yet. Click Start Creating to generate.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("")

# ===================== DASHBOARD (single page, step selector) =====================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="small-muted">Choose Step 1 or Step 2, then fill options and generate/edit.</div>', unsafe_allow_html=True)

b1, b2 = st.columns([0.5, 0.5], gap="small")
with b1:
    if st.button("1) Generate New", use_container_width=True):
        st.session_state.mode = "create"
        st.rerun()
with b2:
    if st.button("2) Edit Upload", use_container_width=True):
        st.session_state.mode = "edit"
        st.rerun()

st.markdown(
    f"""
<div class="stepbar" style="margin-top:10px;">
  <div class="step {'step-active' if st.session_state.mode=='create' else ''}">Step 1: Generate</div>
  <div class="step {'step-active' if st.session_state.mode=='edit' else ''}">Step 2: Edit Upload</div>
</div>
    """,
    unsafe_allow_html=True
)

st.markdown("---")

# ===================== COMMON OPTIONS (general, not only podcast) =====================
PRESETS = {
    "Instagram Post (Square)": "1024x1024",
    "TikTok Cover (Vertical)": "1024x1536",
    "YouTube Thumbnail (Landscape)": "1536x1024",
    "Facebook Post (Landscape)": "1536x1024",
    "LinkedIn Banner (Wide)": "1536x1024",
    "Podcast Cover (Square)": "1024x1024",
}

CATEGORIES = [
    "Podcast Cover",
    "YouTube Thumbnail",
    "TikTok Cover",
    "Instagram Post",
    "Facebook Post",
    "LinkedIn Banner",
    "Business Promo",
    "Event Flyer",
    "Other / Custom",
]

top1, top2, top3 = st.columns([0.38, 0.34, 0.28], gap="medium")
with top1:
    category = st.selectbox("Design type", CATEGORIES)
with top2:
    preset_name = st.selectbox("Template size", list(PRESETS.keys()))
with top3:
    size = PRESETS[preset_name]

row1, row2 = st.columns([1, 1], gap="medium")
with row1:
    title_text = st.text_input("Main title (optional)", placeholder="e.g., Tech Talk Daily")
    subtitle_text = st.text_input("Subtitle (optional)", placeholder="e.g., weekly tech insights")
with row2:
    style = st.selectbox("Style", ["Modern", "Minimal", "Bold", "Clean", "Luxury", "Fun"])
    colors = st.text_input("Colors (optional)", placeholder="e.g., blue + white, purple gradient, black & gold")

extra = st.text_area("Extra instructions", placeholder="e.g., add subtle microphone icon, leave space for text, clean background, high contrast")

# ===================== STEP 1: GENERATE =====================
if st.session_state.mode == "create":
    st.markdown("#### Step 1 — Generate a new design")
    q1, q2 = st.columns([0.35, 0.65], gap="medium")
    with q1:
        quality = st.selectbox("Quality (higher costs more)", ["low", "medium", "high"])
    with q2:
        st.caption("Tip: start with **low** while testing, then switch to medium/high.")

    if st.button("Generate Design", type="primary", use_container_width=True):
        if not rate_limit_ok(1):
            st.stop()

        prompt = f"""
Create a professional social media design.
Design type: {category}.
Template size: {preset_name} ({size}).

Text (if possible):
Title: {title_text if title_text.strip() else "none"}
Subtitle: {subtitle_text if subtitle_text.strip() else "none"}

Style: {style}.
Colors: {colors if colors.strip() else "designer choice"}.

Instructions:
- Clean, modern, high-contrast
- Leave clear space for readable text
- Don’t overcrowd
Extra requests: {extra if extra.strip() else "none"}
"""

        with st.spinner("Generating..."):
            result = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size=size,
                quality=quality
            )

        img_b64 = result.data[0].b64_json
        st.session_state.last_result_bytes = base64.b64decode(img_b64)
        st.success("Generated ✅ Check Preview (top right).")
        st.rerun()

# ===================== STEP 2: EDIT UPLOAD =====================
if st.session_state.mode == "edit":
    st.markdown("#### Step 2 — Upload and edit an image")
    uploaded = st.file_uploader("Upload an image (PNG/JPG)", type=["png", "jpg", "jpeg"])

    if uploaded:
        original_bytes = uploaded.read()
        try:
            original_img = Image.open(BytesIO(original_bytes))
        except Exception:
            st.error("Could not read this image. Please upload a valid PNG/JPG.")
            st.stop()

        st.image(original_img, use_container_width=True)

        if st.button("Apply AI Edit", type="primary", use_container_width=True):
            if not extra.strip():
                st.error("Please write what to change in 'Extra instructions'.")
                st.stop()

            if not rate_limit_ok(1):
                st.stop()

            # Convert to PNG + resize (prevents common errors)
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

            final_prompt = f"""
Edit the uploaded image into a professional social media design.
Target design type: {category}.
Target template: {preset_name} ({size}).

User request: {extra}

Text (if requested):
Title: {title_text if title_text.strip() else "none"}
Subtitle: {subtitle_text if subtitle_text.strip() else "none"}

Style: {style}.
Colors: {colors if colors.strip() else "keep consistent or improve"}.

Important:
- Keep the main subject recognizable unless user requests otherwise.
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

            edited_b64 = edited.data[0].b64_json
            st.session_state.last_result_bytes = base64.b64decode(edited_b64)
            st.success("Edited ✅ Check Preview (top right).")
            st.rerun()
    else:
        st.info("Upload an image to enable editing.")

st.markdown("</div>", unsafe_allow_html=True)

st.caption("Pro tip: set APP_PASSWORD in Streamlit Secrets to protect your public app.")
