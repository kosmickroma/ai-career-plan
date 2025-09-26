# Resume Analyzer
# Reads a resume, finds keyword overlap,
# then uses Gemini to recommend jobs and generate career roadmaps.

import requests
import os
import json
import re
import threading
import itertools
import sys
import time
import streamlit as st
from collections import Counter
from pypdf import PdfReader



STOP_WORDS = {
    "a", "an", "at", "for", "from", "the", "and", "or", "but", "if", "to", "of", "in", "on", "with", "is", "it", "this", "that", "be", "as", "by", "are", "was", "must", "can", "able"

}

# ----------------------------------------------------
# Spinner
# ----------------------------------------------------
def _spinner (msg: str, stop_event: threading.Event):
    """Small terminal spinner that runs until stop_event is set."""
    for ch in itertools.cycle ("|/-\\"):
        if stop_event.is_set():
            break
        sys.stdout.write (f"\r{msg}...{ch}")
        sys.stdout.flush()
        time.sleep(0.12)

    # Clear the line after done
    sys.stdout.write ("\r" + " " * (len(msg) + 8) + "\r")
    sys.stdout.flush()

# ----------------------------------------------------
#  Call Gemini API with spinner
#  ---------------------------------------------------
def call_gemini_withspinner(ai_prompt: str,
                            model: str = "gemini-2.5-flash",
                            timeout: int = 60) -> dict:

    """
    Send prompt to Gemini API while showing a spinner.
    Returns a dict with keys: status, response_text (or error/status_code).
    If GOOGLE_API_KEY is not set, does a dry-run (prints the prompt).
    """

    api_key = os.getenv ("GOOGLE_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    print(f"DEBUG URL: {url}")
    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": ai_prompt}]}]}

    # Dry-run if no key
    if not api_key:
        print("\n[Dry-run] No GOOGLE_API_KEY found. Prompt that would be sent:")
        print("---")
        print(ai_prompt)
        return {"status": "dry_run", "response_text": None}

    # Start spinner thread
    stop_event = threading.Event()
    t = threading.Thread (target=_spinner, args=("Generating AI response", stop_event), daemon=True)
    t.start()

    try:
        resp = requests.post (url, headers=headers, json=data, timeout=timeout)
    except requests.RequestException as e:
        stop_event.set()
        t.join()
        return {"status": "error", "error": str(e)}
    
    # Stop spinner
    stop_event.set()
    t.join()

    if resp.status_code != 200:
        return {"status": "http_error", "status_code": resp.status_code, "response_text": resp.text}

    # Try to extract candidate text robustly
    try: 
        payload = resp.json()
        candidate_text = None
        cands = payload.get("candidates")
        if cands and isinstance(cands, list):
            first = cands[0]
            content = first.get("content")
            if content and isinstance(content, dict):
                parts = content.get("parts")
                if parts and isinstance(parts, list):
                    candidate_text = parts[0].get("text")
    
    # Fallback to full json-text if extraction fails
        if not candidate_text:
            candidate_text = json.dumps(payload, ensure_ascii=False)
        return {"status": "ok", "response_text": candidate_text}
    
    except ValueError:
        # Non-json response
        return {"status": "ok", "response_text": resp.text}

# ----------------------------------------------------
# Analyze resume vs job description
# ----------------------------------------------------
def generate_career_recommendations(my_resume_text, job_description_text):

    

    # Tokenize text
    resume_words = re.findall (r'\b\w+\b', my_resume_text.lower())
    job_words = re.findall(r'\b\w+\b', job_description_text.lower())

    # Filter out stop words
    resume_words = [w for w in resume_words if w not in STOP_WORDS]
    job_words = [w for w in job_words if w not in STOP_WORDS]

    # DEBUG: inspect tokenization
    #print ("DEBUG: resume_words sample (first 40 tokens):", resume_words[:40])
    #print ("DEBUG: job_words sample (first 40 tokens):", job_words[:40])

    # Find matching keywords
    matched_keywords = []
    for word in job_words:
        if word in resume_words:
            matched_keywords.append(word)


    # Count matched keywords
    keyword_counts = {}
    for word in matched_keywords:
        if word in keyword_counts:
            keyword_counts[word] += 1
        else:
            keyword_counts[word] = 1

    # Calculate match percentage
    total_job_keywords = len(set(job_words))
    matched_keyword_count = len(set(matched_keywords))
    match_percentage = (matched_keyword_count / total_job_keywords) * 100 if total_job_keywords else 0


    print (f"\nMatch Percentage: {match_percentage:.2f}%")

    return matched_keywords

# ---------------------------------------------------
# Recommend jobs
# ---------------------------------------------------
def recommend_jobs (matched_keywords):
    api_key = os.getenv ("GOOGLE_API_KEY")

    ai_prompt = (
        f"Act as a professional career counselor."
        f"Given a resume with the following keywords: {matched_keywords},"
        f"recommend a few related job titles for a career changer with this background."
        f"Be concise and provide a list of 3-5 titles."
    )
    result = call_gemini_withspinner(ai_prompt)
    
    if result["status"] == "ok":
        recommendations = result ["response_text"]
        print ("\nAI-Powered Job Recommendations:")
        print ("---")
        print (recommendations)
        return recommendations
    else:
        print (f"Error: Unable to get recommendations. Status: {result}")
        return None

# ------------------------------------------------
# Generate roadmap for chosen career
# ------------------------------------------------
def generate_roadmap (selected_job):
    ai_prompt = ( 
        f"Act as a professional career counselor." 
        f"Given the goal of becoming a {selected_job}, provide a step-by-step career roadmap "
        f"including the necessary skills, credentials, and projects to become qualified for the job."
    )
    result = call_gemini_withspinner(ai_prompt)

    if result["status"] == "ok":
        roadmap = result["response_text"]
        print ("\nAI-Powered Career Roadmap:")
        print ("---")
        print (roadmap)
        return roadmap
    else: 
        print (f"Error: Unable to get a roadmap. Status {result}")
        return None

# ------------------------------------------------
# Run the program
# ------------------------------------------------
if __name__ == "__main__":
    # Changed title to reflect new functionality
    st.title("Career Compass & Resume Analyzer")
    
    # 1. Initialize session state to manage widget persistence
    if 'job_options' not in st.session_state:
        st.session_state['job_options'] = []
    if 'recommendations' not in st.session_state:
        st.session_state['recommendations'] = ""
    if 'resume_analyzed' not in st.session_state:
        st.session_state['resume_analyzed'] = False 
    if 'roadmap_text' not in st.session_state:
        st.session_state['roadmap_text'] = ""
    if 'selected_job_for_roadmap' not in st.session_state:
        st.session_state['selected_job_for_roadmap'] = ""

    # ------------------------------------------------
    # 2. Implement Tab Structure (Quick option first for better UX)
    # ------------------------------------------------
    tab1, tab2 = st.tabs(["💡 Quick Roadmap Explorer", "📄 Full Resume Match & Explore"])

    # Initialize shared variables for the Resume Match logic
    resume_text = ""
    
    # ******************************************************
    # TAB 1: QUICK ROADMAP EXPLORER (The easy, first option)
    # ******************************************************
    with tab1:
        st.subheader("Generate a Roadmap for Any Career Goal")
        st.info("No resume needed! Just tell the AI what you want to be.")
        
        target_career = st.text_input("Enter your desired job title or career:", key="target_career_input")
        
        if st.button("Generate Goal Roadmap", key="goal_roadmap_button"):
            
            if not target_career.strip():
                st.error("Please enter a job title to generate a roadmap.")
                st.stop()
            
            # --- GO STRAIGHT TO ROADMAP GENERATION ---
            with st.status(f"Generating career roadmap for **{target_career}**...", expanded=True):
                roadmap = generate_roadmap(target_career) 

            if roadmap:
                # Store the results in the same state variables
                st.session_state['roadmap_text'] = roadmap
                st.session_state['selected_job_for_roadmap'] = target_career
                st.session_state['resume_analyzed'] = True # Ensures display below the tabs
                st.session_state['job_options'] = [] # Clear old job recommendations
                st.rerun()

    # ******************************************************
    # TAB 2: FULL RESUME MATCH & EXPLORE (The main analysis)
    # ******************************************************
    with tab2:
        st.subheader("Analyze Your Resume Against Job Market Trends")
        
        # --- RESUME INPUTS ---
        # 1 File uploader (Drag and Drop)
        uploaded_file = st.file_uploader(
            "Option 1: Drag and drop your resume file (.txt or .pdf):",
            type=['txt', 'pdf'], 
            accept_multiple_files=False
        )
        
        # 2 Separator and Instructions
        st.markdown("---")
        st.write("**...OR...**")

        # 3 Text Area (Paste/Type)
        pasted_text = st.text_area("Option 2: Paste or type your resume text here:")
        
        # 4 Logic to determine the final resume_text
        if uploaded_file is not None:
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()
            
            try:
                if file_extension == '.pdf':
                    pdf_reader = PdfReader(uploaded_file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() or ""
                    resume_text = text
                    st.success(f"Resume loaded and extracted from PDF: **{uploaded_file.name}**")
                    
                elif file_extension == '.txt':
                    resume_text = uploaded_file.read().decode("utf-8")
                    st.success(f"Resume loaded from file: **{uploaded_file.name}**")
                    
                else:
                    st.error("Unsupported file type uploaded. Please use .txt or .pdf.")
                    
            except Exception as e:
                st.error(f"Error reading file: {e}")
                
        elif pasted_text.strip():
            resume_text = pasted_text
            
        # This button triggers the resume analysis logic
        if st.button("Analyze Resume", key="analyze_button"):
            # Check for input
            if not resume_text:
                st.error("Please upload a file or paste your resume text to analyze.")
                st.stop()
            
            # --- This section runs when the Analyze button is clicked ---
            
            # Extract keywords 
            matched_keywords = re.findall(r'\b\w+\b', resume_text.lower())
            matched_keywords = [w for w in matched_keywords if w not in STOP_WORDS]
            st.subheader("Extracted Keywords from Resume")
            st.write(matched_keywords)

            # Prompt for job recommendations
            ai_prompt = (
                f"Act as a professional career counselor. "
                f"Here is a candidate's resume:\n\n{resume_text}\n\n"
                f"Based on this resume, recommend 5 job titles that would be a good fit. "
                f"Be concise and list them one per line."
            )
            
            result = call_gemini_withspinner(ai_prompt)

            if result["status"] == "ok":
                # 2. Store results in session state
                st.session_state['recommendations'] = result["response_text"]
                
                # Process and store job options
                job_options = [line.strip("-• ") for line in st.session_state['recommendations'].split("\n") if line.strip()]
                st.session_state['job_options'] = job_options
                
                # Set flag and force a rerun to display the subsequent widgets immediately
                st.session_state['resume_analyzed'] = True
                st.rerun() 
            else:
                st.error(f"Error: Unable to get recommendations. Status: {result}")
                st.session_state['resume_analyzed'] = False # Reset state on error

    # ------------------------------------------------
    # 3. Display Logic (Runs only after analysis/roadmap generation is complete)
    # ------------------------------------------------
    
    # This block displays job options only for the Resume Match tab
    if st.session_state['resume_analyzed'] and st.session_state['job_options']:
        st.subheader("AI-Powered Job Recommendations")
        st.write(st.session_state['recommendations'])

        selected_job = st.selectbox("Choose a job title for a roadmap:", st.session_state['job_options'], key="job_selector")

        if st.button("Generate Roadmap", key="roadmap_button"):

            with st.status(f"Generating career roadmap for **{selected_job}**...", expanded=True):
                roadmap = generate_roadmap(selected_job)

            if roadmap:
                st.session_state['roadmap_text'] = roadmap
                st.session_state['selected_job_for_roadmap'] = selected_job

                st.rerun()

    # This block displays the final roadmap for BOTH tabs
    if st.session_state['roadmap_text']:
        st.subheader(f"Roadmap for {st.session_state['selected_job_for_roadmap']}")
        
        
        # Implement download button and instructions
        download_data = st.session_state['roadmap_text'].encode('utf-8')
        st.download_button(
            label="Download Raw Text (.txt)",
            data=download_data,
            file_name=f"{st.session_state['selected_job_for_roadmap'].replace(' ','_')}_Career_Roadmap.txt",
            mime='text/plain',
            key="download_button_txt",
            type="primary"
        )
        
        st.write(st.session_state['roadmap_text'])
        
        # Image/PDF Instruction
        st.markdown("---")
        st.markdown(
            "** To save as an image or PDF for sharing (e.g., on LinkedIn):**"
            "Use your browser's print function (**Ctrl+P or Cmd+P**) and select **'Save as PDF'** or take a **screenshot**."
        )