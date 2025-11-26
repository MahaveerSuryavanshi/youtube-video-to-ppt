import streamlit as st
import yt_dlp
import cv2
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import shutil

# Paths
TEMP_VIDEO = "video.mp4"
SLIDE_DIR = "slides"
PDF_FILE = "slides.pdf"


# -------------------------
# Download YouTube Video
# -------------------------
def download_video(url):
    ydl_opts = {
        "outtmpl": TEMP_VIDEO,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        "merge_output_format": "mp4",
        "quiet": True,
        "ignoreerrors": True,
        "noprogress": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info is None:
            raise Exception("Failed to download video. Stream may be restricted.")


# -------------------------
# Extract Slides via Scene Detection
# -------------------------
def extract_slides(video_path):
    if os.path.exists(SLIDE_DIR):
        shutil.rmtree(SLIDE_DIR)
    os.makedirs(SLIDE_DIR)

    cap = cv2.VideoCapture(video_path)
    prev = None
    slide_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if prev is None:
            prev = gray
            continue

        diff = cv2.absdiff(prev, gray)
        threshold = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)[1]
        diff_value = cv2.countNonZero(threshold)

        # When diff is large → slide changed
        if diff_value > 500000:
            fname = f"{SLIDE_DIR}/slide_{slide_count}.jpg"
            cv2.imwrite(fname, frame)
            slide_count += 1

            prev = gray

    cap.release()
    return slide_count


# -------------------------
# Build PDF
# -------------------------
def create_pdf():
    c = canvas.Canvas(PDF_FILE, pagesize=letter)

    slide_files = sorted(os.listdir(SLIDE_DIR))
    for slide in slide_files:
        path = os.path.join(SLIDE_DIR, slide)
        img = ImageReader(path)
        pw, ph = letter
        c.drawImage(img, 0, 0, width=pw, height=ph)
        c.showPage()

    c.save()
    return PDF_FILE


# -------------------------
# Streamlit App UI
# -------------------------
st.title("📌 Extract PPT Slides from YouTube Video")
st.write("Upload a YouTube link and automatically extract slides into a downloadable PDF.")

youtube_url = st.text_input("🎥 Enter YouTube Video URL")

if st.button("Start Process"):
    if youtube_url.strip() == "":
        st.error("Please enter a YouTube link.")
        st.stop()

    st.info("Downloading video... please wait ⏳")
    download_video(youtube_url)

    st.info("Extracting slides from video... 🖼️")
    count = extract_slides(TEMP_VIDEO)

    if count == 0:
        st.error("No slides detected. Try a video with clear slide transitions.")
        st.stop()

    st.success(f"Detected {count} slides!")

    st.info("Generating PDF... 📄")
    pdf_path = create_pdf()

    with open(pdf_path, "rb") as f:
        st.download_button(
            label="⬇️ Download Slides PDF",
            data=f,
            file_name="slides.pdf",
            mime="application/pdf"
        )

    st.success("Done! Your PDF is ready 🎉")
