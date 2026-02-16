# app.py — PodCraft AI Studio (Streamlit)
# Features:
# - Home page
# - Create (text -> image) with quality option
# - Edit (upload -> edit) with PNG conversion + resize (NO quality param on edit)
# - API key secured via Streamlit Secrets (server-side)
# - Optional password gate via Streamlit Secrets
# - Simple per-session cooldown + basic daily limit (in-memory)

import time
import base64
import hashlib
from io import BytesIO
from datetime import date

import streamlit as st
from openai import OpenAI
from PIL import Image


# ------------------ PAGE CONFIG ------------------
st.set_page_config(page_title="PodCraft AI Studio", layout="centered")


# ------------------ SECRETS ------------------
# Streamlit Cloud -> App -> Settings -> Secrets
# OPENAI_API_KEY="sk-..."
# (optional) APP_PASSWORD="your-password"
# (optional) MAX_DAILY_GENERATIONS="10"
# (optional) COOLDOWN_SECONDS="15"

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")
MAX_DAILY = int(st.secrets.get("MAX_DAILY_GENERATIONS", 10))
COOLDOWN = int(st.secrets.get("COOLDOWN_SECONDS", 15))

client = OpenAI(api_key=OPENAI_API_KEY)


# ------------------ BASIC SECURITY (OPTIONAL PASSWORD) ------------------
def password_gate():
    if not APP_PASSWORD:
        return  # no password configured

    if st.session_state.get("authed"):
        return

    st.title("🔒 PodCraft AI Studio")
    st.write("Access is protected. Enter the password to continue.")

    pw = st.text_input("Password", type="password")
    if st.button("Unlock"):
        if pw == APP_PASSWORD:
            st.session_state.authed = True
            st.success("Unlocked ✅")
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()


# ------------------ BASIC RATE LIMITING ------------------
@st.cache_resource
def usage_store():
    # global in-memory store (resets if app restarts)
    return {}


def get_visitor_id() -> str:
    # lightweight per-browser visitor id (not perfect, but reduces abuse)
    if "visitor_id" not in st.session_state:
        raw = f"{time.time()}::{st.session_state.get('_seed', '')}"
        st.session_state.visitor_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return st.session_state.visitor_id


def rate_limit_ok(cost: int = 1) -> bool:
    # daily limit + cooldown per session
    vid = get_visitor_id()
    store = usage_store()
    today = str(date.today())
    key = f"{today}:{vid}"

    used = store.get(key, 0)
    if used + cost > MAX_DAILY:
        st.warning(f"Daily limit reached ({MAX_DAILY} generations/day). Try again tomorrow.")
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


# ------------------ NAV ------------------
page = st.sidebar.radio("Navigation", ["Home", "Create", "Edit (Upload)"])

# Password protects Create/Edit pages (Home stays public)
if page in ["Create", "Edit (Upload)"]:
    password_gate()


# ------------------ HOME ------------------
if page == "Home":
    st.title("🎙️ PodCraft AI Studio")
    st.write("Generate and edit podcast artwork for social media—fast and simple.")
    st.markdown("### What you can do")
    st.write("✅ **Create** podcast covers from a prompt")
    st.write("✅ **Edit** an uploaded image (change background, add items, clean up look)")
    st.markdown("---")
    st.write("Use the sidebar to start.")
    st.stop()


# ------------------ CREATE (TEXT -> IMAGE) ------------------
if page == "Create":
    st.title("🎨 Create Podcast Cover (AI)")

    platform = st.selectbox("Platform", ["Instagram", "TikTok", "Facebook", "YouTube"])
    topic = st.text_input("Podcast topic")
    vibe = st.selectbox("Vibe", ["Clean", "Bold", "Minimal", "Modern"])
    extra = st.text_area("Extra instructions (optional)", placeholder="e.g., blue gradient background, microphone icon, space for title")

    size = st.selectbox("Size", ["1024x1024", "1024x1536", "1536x1024"])
    quality = st.selectbox("Quality (higher = more cost)", ["low", "medium", "high"])

    if st.button("Generate Cover"):
        if not topic.strip():
            st.error("Please enter a podcast topic.")
            st.stop()

        if not rate_limit_ok(1):
            st.stop()

        prompt = f"""
Create a professional podcast cover optimized for {platform}.
Topic: {topic}.
Style: {vibe}.
Extra: {extra}.
Clean layout, modern design, strong contrast, high quality.
Leave a clear area for title text.
"""

        with st.spinner("Generating..."):
            result = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size=size,
                quality=quality
            )

        img_b64 = result.data[0].b64_json
        img_bytes = base64.b64decode(img_b64)

        st.image(Image.open(BytesIO(img_bytes)), use_container_width=True)
        st.download_button("Download PNG", img_bytes, file_name="podcast_cover.png")


# ------------------ EDIT (UPLOAD -> EDIT) ------------------
if page == "Edit (Upload)":
    st.title("🛠️ Edit an Uploaded Image (AI)")
    st.caption("Upload a PNG/JPG. We convert it to PNG and resize to avoid errors.")

    uploaded = st.file_uploader("Upload an image (PNG/JPG)", type=["png", "jpg", "jpeg"])

    edit_prompt = st.text_area(
        "What do you want to change?",
        placeholder="Example: Replace the background with a modern blue gradient studio look. Keep the person the same. Add a subtle microphone icon. Leave space for the title at the top."
    )

    size = st.selectbox("Output size", ["1024x1024", "1024x1536", "1536x1024"])

    if uploaded:
        original_bytes = uploaded.read()

        # Show original
        try:
            original_img = Image.open(BytesIO(original_bytes))
        except Exception:
            st.error("Could not read this image. Please upload a valid PNG/JPG.")
            st.stop()

        st.subheader("Original")
        st.image(original_img, use_container_width=True)

        if st.button("Apply AI Edit"):
            if not edit_prompt.strip():
                st.error("Please write what you want to change.")
                st.stop()

            if not rate_limit_ok(1):
                st.stop()

            # Convert to PNG + resize to reduce failures
            img = Image.open(BytesIO(original_bytes)).convert("RGBA")

            MAX_SIDE = 1024
            w, h = img.size
            scale = min(MAX_SIDE / max(w, h), 1.0)
            if scale < 1.0:
                img = img.resize((int(w * scale), int(h * scale)))

            png_buffer = BytesIO()
            img.save(png_buffer, format="PNG")
            png_buffer.seek(0)
            png_buffer.name = "upload.png"  # important for multipart upload

            final_prompt = f"""
Edit the uploaded image.
Instruction: {edit_prompt}
Important: keep the main subject recognizable unless the user requests otherwise.
"""

            with st.spinner("Editing..."):
                # NOTE: images.edit does NOT accept "quality" in your environment.
                edited = client.images.edit(
                    model="gpt-image-1",
                    image=png_buffer,
                    prompt=final_prompt,
                    size=size
                )

            edited_b64 = edited.data[0].b64_json
            edited_bytes = base64.b64decode(edited_b64)

            st.subheader("Edited Result")
            st.image(Image.open(BytesIO(edited_bytes)), use_container_width=True)
            st.download_button("Download Edited PNG", edited_bytes, file_name="podcast_cover_edited.png")
    else:
        st.info("Upload an image to enable editing.")
