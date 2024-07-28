import streamlit as st
from dotenv import load_dotenv
import os
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
import requests
import re
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Load environment variables
load_dotenv()

# Configure the Google Generative AI model
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Define the prompts for different types of content
summary_prompt = """You are a YouTube video summarizer. Provide a concise summary of the following transcript within 250 words: """
key_points_prompt = """Extract and list the key points from the following video transcript: """
qa_prompt = """Based on the following video transcript, generate 5 relevant questions and their answers. Format each as 'Question: [question]' followed by 'Answer: [answer]' without any asterisks or additional formatting: """
code_explanation_prompt = """Extract the code snippets from the following video transcript and provide a detailed explanation for each code snippet: """

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
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=4))  # 4 means justified
    
    flowables = []
    
    # Add title
    flowables.append(Paragraph(f"Video Title: {video_title}", styles['Heading1']))
    flowables.append(Spacer(1, 0.25*inch))
    
    # Process content
    sections = content.split("## ")
    for section in sections[1:]:  # Skip the first empty split
        lines = section.split("\n", 1)
        title = lines[0]
        body = lines[1] if len(lines) > 1 else ""
        
        flowables.append(Paragraph(title, styles['Heading2']))
        flowables.append(Spacer(1, 0.1*inch))
        
        for paragraph in body.split("\n"):
            if paragraph.startswith("Question:"):
                flowables.append(Paragraph(paragraph, styles['Heading3']))
            elif paragraph.startswith("Answer:"):
                flowables.append(Paragraph(paragraph, styles['BodyText']))
            elif paragraph.strip().startswith("```"):
                code = paragraph.strip("```").strip()
                flowables.append(Paragraph(code, styles['Code']))
            else:
                flowables.append(Paragraph(paragraph, styles['Justify']))
            flowables.append(Spacer(1, 0.1*inch))
        
        flowables.append(Spacer(1, 0.2*inch))
    
    doc.build(flowables)
    buffer.seek(0)
    return buffer

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
st.title("YouTube Insight Generator")
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
                content += "## Summary\n" + summary + "\n\n"

            if include_key_points:
                key_points = generate_gemini_content(transcript_text, key_points_prompt)
                if key_points:
                    content += "## Key Points\n" + key_points + "\n\n"

            if include_qa:
                qa = generate_gemini_content(transcript_text, qa_prompt)
                if qa:
                    content += "## Questions and Answers\n" + qa + "\n\n"
            
            if include_code_explanation:
                code_explanation = generate_gemini_content(transcript_text, code_explanation_prompt)
                if code_explanation:
                    content += "## Code Explanation\n" + code_explanation + "\n\n"

            if content.strip():
                st.markdown(content)

                try:
                    pdf_buffer = create_pdf(content, video_title)
                    st.download_button(
                        label="Download Content as PDF",
                        data=pdf_buffer,
                        file_name=f"{sanitize_filename(video_title)}_summary.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Error creating PDF: {str(e)}")
            else:
                st.error("No content generated to create PDF.")
    else:
        st.error("Unable to fetch transcript. This video might not have any available transcripts.")
