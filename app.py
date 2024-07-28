import streamlit as st
from dotenv import load_dotenv
import os
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from fpdf import FPDF
import requests
import re

# Load environment variables
load_dotenv()

# Configure the Google Generative AI model
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Define the prompts for different types of content
summary_prompt = """You are a YouTube video summarizer. Provide a concise summary of the following transcript within 250 words: """
key_points_prompt = """Extract and list the key points from the following video transcript: """
qa_prompt = """Based on the following video transcript, generate 5 relevant questions and their answers. Format each as 'Question: [question]' followed by 'Answer: [answer]' without any asterisks or additional formatting: """
code_explanation_prompt = """Extract the code snippets from the following video transcript and provide a detailed explanation for each code snippet: """

class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.first_page = True  # Flag to track if it's the first page

    def header(self):
        if self.first_page:
            self.set_font('DejaVu', 'B', 15)
            self.cell(0, 10, 'YouTube Video Content Summary', new_x='LMARGIN', new_y='TOP')
            self.ln(15)  # Add space after header
            self.first_page = False  # Set flag to False after first page

    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', '', 8)
        self.cell(0, 10, f'Page {self.page_no()}', new_x='RIGHT', new_y='TOP', align='C')

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
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        except TranscriptsDisabled:
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
        st.error(f"Error generating content: {e}")
        return None

def create_pdf(content, video_title):
    pdf = PDF()
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf', uni=True)
    pdf.add_font('DejaVu', 'I', 'DejaVuSans-Oblique.ttf', uni=True)
    
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 10, f"Video Title: {video_title}", new_x='LMARGIN', new_y='TOP')
    pdf.ln(10)

    sections = content.split("## ")

    for section in sections:
        if section.strip() != "":
            lines = section.split("\n", 1)
            title = lines[0]
            body = lines[1] if len(lines) > 1 else ""

            pdf.set_font("DejaVu", "B", 12)
            pdf.set_fill_color(200, 220, 255)

            if title == "Summary:":
                pdf.ln(20)
            elif title == "Questions and Answers:":
                pdf.ln(20)

            pdf.cell(0, 10, title, new_x='LMARGIN', new_y='TOP', fill=True)
            pdf.ln(15)

            pdf.set_font("DejaVu", "", 11)
            for paragraph in body.split("\n"):
                if paragraph.startswith("Question:"):
                    pdf.set_font("DejaVu", "B", 11)
                    pdf.multi_cell(0, 5, paragraph)
                    pdf.set_font("DejaVu", "", 11)
                elif paragraph.startswith("Answer:"):
                    pdf.set_font("DejaVu", "I", 11)
                    pdf.multi_cell(0, 5, paragraph)
                    pdf.set_font("DejaVu", "", 11)
                elif paragraph.startswith(""):
                    # If paragraph is a code block, extract code and add to PDF
                    pdf.set_font("DejaVu", "", 11)
                    pdf.set_fill_color(230, 230, 230)
                    pdf.multi_cell(0, 5, paragraph.strip(""), fill=True)
                else:
                    pdf.multi_cell(0, 5, paragraph)
                pdf.ln(5)

            pdf.ln(15)

            if pdf.get_y() > 250:
                pdf.add_page()

    return bytes(pdf.output())

def get_video_title(video_id):
    try:
        api_key = os.getenv("YOUTUBE_DATA_API_KEY")
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={api_key}"
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful
        data = response.json()
        
        if 'items' in data and len(data['items']) > 0:
            title = data['items'][0]['snippet']['title']
            return title
        else:
            st.error("No items found in API response.")
            return 'Video Title Not Available'
    except Exception as e:
        st.error(f"Error fetching video title: {str(e)}")
        return 'Video Title Not Available'

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

# Streamlit UI
st.title("YouTube Video Content Generator")
youtube_link = st.text_input("Enter YouTube Video Link:")

include_key_points = st.checkbox("Include Key Points")
include_qa = st.checkbox("Include Questions and Answers")
include_code_explanation = st.checkbox("Include Code Explanation")

video_title = "Video Title Not Available"

if youtube_link:
    try:
        video_id = extract_video_id(youtube_link)
        st.image(f"http://img.youtube.com/vi/{video_id}/0.jpg", use_column_width=True)

        video_title = get_video_title(video_id)
        st.write(f"Video Title: {video_title}")
    except Exception as e:
        st.error(f"Error: {str(e)}")

if st.button("Generate Content"):
    with st.spinner('Extracting transcript...'):
        transcript_text = extract_transcript_details(youtube_link)

    if transcript_text:
        content = ""
        with st.spinner('Generating content...'):
            summary = generate_gemini_content(transcript_text, summary_prompt)
            if summary:
                content += "## Summary:\n" + summary + "\n\n"

            if include_key_points:
                key_points = generate_gemini_content(transcript_text, key_points_prompt)
                if key_points:
                    content += "## Key Points:\n" + key_points + "\n\n"

            if include_qa:
                qa = generate_gemini_content(transcript_text, qa_prompt)
                if qa:
                    content += "## Questions and Answers:\n" + qa + "\n\n"
            
            if include_code_explanation:
                code_explanation = generate_gemini_content(transcript_text, code_explanation_prompt)
                if code_explanation:
                    content += "## Code Explanation:\n" + code_explanation + "\n\n"

            if content.strip():
                st.markdown(content)

                try:
                    pdf_data = create_pdf(content, video_title)
                    if len(pdf_data) > 200 * 1024 * 1024:  # 200 MB limit
                        st.error("PDF file is too large to download.")
                    else:
                        st.download_button(
                            label="Download Content as PDF",
                            data=pdf_data,
                            file_name=f"{sanitize_filename(video_title)}_summary.pdf",
                            mime="application/pdf"
                        )
                except Exception as e:
                    st.error(f"Error creating PDF: {str(e)}")
            else:
                st.error("No content generated to create PDF.")
    else:
        st.error("Unable to fetch transcript. This video might not have any available transcripts.")