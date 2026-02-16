import time
import base64
import hashlib
from io import BytesIO
from datetime import date

import streamlit as st
from openai import OpenAI
from PIL import Image

# ------------------ CONFIG ------------------
st.set_page_config(page_title="PodCraft AI Studio", layout="centered")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")
MAX_DAILY = int(st.secrets.get("MAX_DAILY_GENERATIONS", 10))
COOLDOWN = int(st.secrets.get("COOLDOWN_SECONDS", 20))

# ------------------ SIMPLE SECURITY ------------------
def get_visitor_id() -> str:
    """
    Streamlit doesn't reliably expose client IP. We'll create a lightweight per-browser ID.
    It's not perfect security, but it reduces casual abuse.
    """
    if "visitor_id" not in st.session_state:
        raw = f"{time.time()}-{st.experimental_user.email if hasattr(st, 'experimental_user') else ''}-{st.session_state.get('hash_seed','')}"
        st.session_state.visitor_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return st.session_state.visitor_id

@st.cache_resource
def usage_store():
    # Global in-memory store (resets when app restarts)
    return {}

def check_password_gate():
    if not APP_PASSWORD:
        return True  # no password configured
    if st.session_state.get("authed"):
        return True

    st.subheader("🔒 Access Required")
    pw = st.text_input("Enter access password", type="password")
    if st.button("Unlock"):
        if pw == APP_PASSWORD:
            st.session_state.authed = True
            st.success("Unlocked ✅")
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()

def rate_limit_ok(action_cost: int = 1) -> bool:
    """
    Per-day generation limit + cooldown per session.
    """
    vid = get_visitor_id()
    store = usage_store()

    today = str(date.today())
    key = f"{today}:{vid}"

    used = store.get(key, 0)
    if used + action_cost > MAX_DAILY:
        st.warning(f"Daily limit reached ({MAX_DAILY} generations/day). Try tomorrow.")
        return False

    last = st.session_state.get("last_action_ts", 0.0)
    now = time.time()
    if now - last < COOLDOWN:
        wait = int(COOLDOWN - (now - last))
        st.info(f"Please wait {wait}s before generating again.")
        return False

    # Allow, then record
    store[key] = used + action_cost
    st.session_state.last_action_ts = now
    return True

# ------------------ NAV ------------------
page = st.sidebar.radio("Navigation", ["Home", "Create", "Edit (Upload)"])

# Password gate for everything except Home
if page != "Home":
    check_password_gate()

# ------------------ HOME ------------------
if page == "Home":
    st.title("🎙️ PodCraft AI Studio")
    st.write("Generate and edit podcast artwork for social media.")
    st.markdown("### What you can do")
    st.write("✅ Create covers with AI\n\n✅ Upload and edit your image with AI\n\n✅ Download ready-to-post PNGs")
    st.markdown("---")
    st.write("Use the sidebar to **Create** or **Edit (Upload)**.")
    st.stop()

# ------------------ CREATE (TEXT -> IMAGE) ------------------
if page == "Create":
    st.title("🎨 Create Podcast Cover (AI)")

    platform = st.selectbox("Platform", ["Instagram", "TikTok", "Facebook", "YouTube"])
    topic = st.text_input("Podcast topic")
    vibe = st.selectbox("Vibe", ["Clean", "Bold", "Minimal", "Modern"])
    extra = st.text_area("Extra instructions (optional)")

    quality = st.selectbox("Quality (cost increases with quality)", ["low", "medium", "high"])
    size = st.selectbox("Size", ["1024x1024", "1024x1536", "1536x1024"])

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
Clean layout, strong contrast, modern design, high quality.
Leave a clear area for title text (top or center).
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
        image = Image.open(BytesIO(img_bytes))

        st.image(image, use_container_width=True)
        st.download_button("Download PNG", img_bytes, file_name="podcast_cover.png")

# ------------------ EDIT (UPLOAD -> EDIT) ------------------
if page == "Edit (Upload)":
    st.title("🛠️ Edit an Uploaded Image (AI)")

    uploaded = st.file_uploader("Upload an image (PNG/JPG)", type=["png", "jpg", "jpeg"])

    edit_prompt = st.text_area(
        "What do you want to change?",
        placeholder="Example: Replace background with a modern blue gradient studio look. Keep the person same. Add subtle mic icon. Leave space for title."
    )

    quality = st.selectbox("Quality (cost increases with quality)", ["low", "medium", "high"])
    size = st.selectbox("Output size", ["1024x1024", "1024x1536", "1536x1024"])

    if uploaded:
        original_bytes = uploaded.read()
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

            final_prompt = f"""
Edit the uploaded image.
Instruction: {edit_prompt}
Important: keep the main subject recognizable unless the user requests otherwise.
"""

            with st.spinner("Editing..."):
                edited = client.images.edit(
                    model="gpt-image-1",
                    image=BytesIO(original_bytes),
                    prompt=final_prompt,
                    size=size,
                    quality=quality
                )

            edited_b64 = edited.data[0].b64_json
            edited_bytes = base64.b64decode(edited_b64)
            edited_img = Image.open(BytesIO(edited_bytes))

            st.subheader("Edited Result")
            st.image(edited_img, use_container_width=True)
            st.download_button("Download Edited PNG", edited_bytes, file_name="podcast_cover_edited.png")
    else:
        st.info("Upload an image to enable editing.")
