import streamlit as st
from dotenv import load_dotenv
import os
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from fpdf import FPDF
import requests

# Load environment variables
load_dotenv()

# Configure the Google Generative AI model
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Define the prompts for different types of content
summary_prompt = """You are a YouTube video summarizer. Provide a concise summary of the following transcript within 250 words: """
key_points_prompt = """Extract and list the key points from the following video transcript: """
qa_prompt = """Based on the following video transcript, generate 5 relevant questions and their answers. Format each as 'Question: [question]' followed by 'Answer: [answer]' without any asterisks or additional formatting: """
code_explanation_prompt = """Extract the code snippets from the following video transcript and provide a detailed explanation for each code snippet: """

class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            self.set_font('DejaVu', 'B', 15)
            self.cell(0, 10, 'YouTube Video Content Summary', ln=True)
            self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', '', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

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

    # Check if font files exist
    if not os.path.isfile('DejaVuSans.ttf') or not os.path.isfile('DejaVuSans-Bold.ttf') or not os.path.isfile('DejaVuSans-Oblique.ttf'):
        st.error("Font files not found. Please make sure the DejaVu font files are present in the same directory as this script.")
        return None
    
    try:
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf', uni=True)
        pdf.add_font('DejaVu', 'I', 'DejaVuSans-Oblique.ttf', uni=True)
    except Exception as e:
        st.error(f"Error loading fonts: {e}")
        return None

    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Video Title
    pdf.set_font("DejaVu", "B", 14)
    pdf.multi_cell(0, 10, f"Video Title: {video_title}")
    pdf.ln(5)

    sections = content.split("## ")

    for section in sections[1:]:  # Skip the first empty split
        if section.strip() != "":
            lines = section.split("\n", 1)
            title = lines[0]
            body = lines[1] if len(lines) > 1 else ""

            # Section Title
            pdf.set_font("DejaVu", "B", 12)
            pdf.set_fill_color(200, 220, 255)
            pdf.cell(0, 10, title, ln=True, fill=True)
            pdf.ln(5)

            # Section Content
            pdf.set_font("DejaVu", "", 11)
            in_code_block = False
            code_buffer = []
            
            for paragraph in body.split("\n"):
                if paragraph.strip().startswith("```"):
                    if in_code_block:
                        # End of code block, print the buffered code
                        pdf.set_font("Courier", "", 10)
                        pdf.set_fill_color(240, 240, 240)
                        for code_line in code_buffer:
                            pdf.cell(0, 5, code_line, ln=True, fill=True)
                        code_buffer = []
                        pdf.ln(5)
                        pdf.set_font("DejaVu", "", 11)
                    in_code_block = not in_code_block
                    continue

                if in_code_block:
                    code_buffer.append(paragraph)
                elif paragraph.startswith("Question:"):
                    # Make questions bold
                    pdf.set_font("DejaVu", "B", 11)
                    pdf.multi_cell(0, 5, paragraph)
                    pdf.set_font("DejaVu", "", 11)
                elif paragraph.startswith("Answer:"):
                    pdf.multi_cell(0, 5, paragraph)
                elif paragraph.startswith("*"):
                    # Format key points
                    if paragraph.startswith("* Key Points:"):
                        continue
                    pdf.set_font("DejaVu", "", 11)
                    pdf.multi_cell(0, 5, "• " + paragraph[1:].strip())
                else:
                    pdf.multi_cell(0, 5, paragraph)
                
                if not in_code_block:
                    pdf.ln(2)

            pdf.ln(5)

    return bytes(pdf.output())

def get_video_title(video_id):
    try:
        api_key = st.secrets["YOUTUBE_DATA_API_KEY"]
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

            if content:
                st.markdown(content)

                pdf_data = create_pdf(content, video_title)
                st.download_button(
                    label="Download Content as PDF",
                    data=pdf_data,
                    file_name=f"{video_title}_summary.pdf",
                    mime="application/pdf"
                )
            else:
                st.error("Failed to generate content.")
    else:
        st.error("Unable to fetch transcript. This video might not have any available transcripts.")
