import streamlit as st
from dotenv import load_dotenv
import os
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from fpdf import FPDF
import io

# Load environment variables
load_dotenv()

# Configure the Google Generative AI model
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Define the prompt for summarization
prompt = """You are a YouTube video summarizer. You will be taking the transcript text
and summarizing the entire video, providing the important summary in points
within 250 words. Please provide the summary of the text given here: """

def extract_video_id(youtube_url):
    """Extracts video ID from YouTube URL."""
    if "youtu.be/" in youtube_url:
        return youtube_url.split("youtu.be/")[1].split("?")[0]
    elif "youtube.com/watch?v=" in youtube_url:
        return youtube_url.split("v=")[1].split("&")[0]
    else:
        raise ValueError("Invalid YouTube URL")

def extract_transcript_details(youtube_video_url):
    """Fetches transcript from YouTube video using video ID."""
    try:
        video_id = extract_video_id(youtube_video_url)
        try:
            # Try to get English transcript first
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id, languages=['en'])
        except TranscriptsDisabled:
            # If English is not available, get any available transcript
            transcript = YouTubeTranscriptApi.get_transcript(video_id)

        transcript_text = " ".join([entry["text"] for entry in transcript])
        return transcript_text
    except Exception as e:
        st.error(f"Error fetching transcript: {str(e)}")
        return None

def generate_gemini_content(transcript_text, prompt):
    """Generates content using Google Gemini Pro."""
    try:
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt + transcript_text)
        return response.text
    except Exception as e:
        st.error(f"Error generating summary: {e}")
        return None

def create_pdf(summary_text):
    """Creates a PDF file from the summary text."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, summary_text)

    # Generate PDF data as bytes
    pdf_output = pdf.output(dest='S')  # Get the PDF as bytearray
    return bytes(pdf_output)  # Convert bytearray to bytes

# Streamlit UI
st.title("YouTube Transcript to Detailed Notes Converter")
youtube_link = st.text_input("Enter YouTube Video Link:")

if youtube_link:
    try:
        video_id = extract_video_id(youtube_link)
        st.image(
            f"http://img.youtube.com/vi/{video_id}/0.jpg", use_column_width=True)
    except ValueError as e:
        st.error(f"Invalid URL: {e}")

if st.button("Get Detailed Notes"):
    with st.spinner('Extracting transcript...'):
        transcript_text = extract_transcript_details(youtube_link)

    if transcript_text:
        with st.spinner('Generating summary...'):
            summary = generate_gemini_content(transcript_text, prompt)
        if summary:
            st.markdown("## Detailed Notes:")
            st.write(summary)

            # Create PDF and provide download link
            pdf = create_pdf(summary)
            st.download_button(
                label="Download Summary as PDF",
                data=pdf,
                file_name="summary.pdf",
                mime="application/pdf"
            )
    else:
        st.error(
            "Unable to fetch transcript. This video might not have any available transcripts.")
