import streamlit as st
import cv2
import os
import tempfile
import re
import shutil
from fpdf import FPDF
from PIL import Image, ImageFile
import yt_dlp
from skimage.metrics import structural_similarity as ssim

ImageFile.LOAD_TRUNCATED_IMAGES = True


# -------------------------------
# YOUTUBE DOWNLOAD
# -------------------------------
def download_video(url, filename, max_retries=3):
    ydl_opts = {
        'outtmpl': filename,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
        'merge_output_format': 'mp4',
        'ignoreerrors': True,
        'quiet': True
    }
    retries = 0
    while retries < max_retries:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                return filename
        except yt_dlp.utils.DownloadError:
            retries += 1
            st.warning(f"Retrying download... {retries}/{max_retries}")
    return None


# -------------------------------
# VIDEO ID / PLAYLIST
# -------------------------------
def get_video_id(url):
    patterns = [
        r"shorts\/(\w+)",
        r"youtu\.be\/([\w\-_]+)",
        r"v=([\w\-_]+)",
        r"live\/(\w+)"
    ]
    for p in patterns:
        match = re.search(p, url)
        if match:
            return match.group(1)
    return None


def get_playlist_videos(playlist_url):
    ydl_opts = {
        'ignoreerrors': True,
        'playlistend': 999,
        'extract_flat': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        pl = ydl.extract_info(playlist_url, download=False)
        return [e['url'] for e in pl['entries']]


# -------------------------------
# SLIDE EXTRACTION (SSIM METHOD)
# -------------------------------
def extract_unique_frames(video_file, output_folder, n=3, ssim_threshold=0.80):
    cap = cv2.VideoCapture(video_file)
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    last_frame = None
    saved_frame = None
    frame_number = 0
    last_saved_frame_number = -1
    timestamps = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_number % n == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (128, 72))

            if last_frame is not None:
                similarity = ssim(gray, last_frame)

                if similarity < ssim_threshold:
                    if (
                        saved_frame is not None and
                        frame_number - last_saved_frame_number > fps
                    ):
                        fname = os.path.join(output_folder, f"frame{frame_number:04d}.png")
                        cv2.imwrite(fname, saved_frame)
                        timestamps.append(frame_number // fps)
                        last_saved_frame_number = frame_number
                    saved_frame = frame
                else:
                    saved_frame = frame
            else:
                fname = os.path.join(output_folder, f"frame{frame_number:04d}.png")
                cv2.imwrite(fname, frame)
                timestamps.append(frame_number // fps)
                last_saved_frame_number = frame_number

            last_frame = gray

        frame_number += 1

    cap.release()
    return timestamps


# -------------------------------
# PDF GENERATION
# -------------------------------
def convert_frames_to_pdf(folder, output_pdf, timestamps):
    images = sorted(os.listdir(folder))
    pdf = FPDF("L")
    pdf.set_auto_page_break(0)

    for img_file, sec in zip(images, timestamps):
        path = os.path.join(folder, img_file)
        pdf.add_page()
        pdf.image(path, x=0, y=0, w=pdf.w, h=pdf.h)

    pdf.output(output_pdf)


# -------------------------------
# STREAMLIT
# -------------------------------
st.title("📌 Extract PPT Slides from YouTube Video")
st.write("Upload a YouTube link and extract slides into a downloadable PDF.")

url = st.text_input("🎥 Enter YouTube Video or Playlist URL")

if st.button("Start"):
    if not url:
        st.error("Please enter a URL.")
        st.stop()

    with st.spinner("Downloading video..."):
        video_file = download_video(url, "video.mp4")

    if video_file is None:
        st.error("Failed to download video.")
        st.stop()

    with tempfile.TemporaryDirectory() as temp_dir:
        st.info("Extracting unique frames (slides)...")
        timestamps = extract_unique_frames(video_file, temp_dir)

        if len(os.listdir(temp_dir)) == 0:
            st.error("No slides detected. Try adjusting threshold.")
            st.stop()

        pdf_file = "slides.pdf"
        convert_frames_to_pdf(temp_dir, pdf_file, timestamps)

        with open(pdf_file, "rb") as f:
            st.download_button(
                label="⬇ Download Slides PDF",
                data=f,
                file_name="slides.pdf",
                mime="application/pdf"
            )

    os.remove(video_file)
    st.success("Done!")
