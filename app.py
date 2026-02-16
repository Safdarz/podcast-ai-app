import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image

st.set_page_config(page_title="Podcast AI Studio", layout="centered")
st.title("🎙️ Podcast Cover Generator")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

platform = st.selectbox("Platform", ["Instagram", "TikTok", "Facebook", "YouTube"])
topic = st.text_input("Podcast topic")
vibe = st.selectbox("Vibe", ["Clean", "Bold", "Minimal", "Modern"])
extra = st.text_area("Extra instructions (optional)")

if st.button("Generate"):
    if not topic.strip():
        st.error("Please enter a podcast topic.")
        st.stop()

    prompt = f"""
    Create a professional podcast cover optimized for {platform}.
    Topic: {topic}.
    Style: {vibe}.
    Extra: {extra}.
    Clean layout, strong contrast, readable title area, modern design, high quality.
    """

    with st.spinner("Generating image..."):
        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )

    img_b64 = result.data[0].b64_json
    img_bytes = base64.b64decode(img_b64)
    image = Image.open(BytesIO(img_bytes))

    st.image(image, use_container_width=True)
    st.download_button("Download PNG", img_bytes, file_name="podcast_cover.png")
