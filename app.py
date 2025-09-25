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
                            model: str = "gemini-1.5-flash",
                            timeout: int = 60) -> dict:

    """
    Send prompt to Gemini API while showing a spinner.
    Returns a dict with keys: status, response_text (or error/status_code).
    If GOOGLE_API_KEY is not set, does a dry-run (prints the prompt).
    """

    api_key = os.getenv ("GOOGLE_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
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
    st.title("Resume Analyzer")

    resume_text = st.text_area("Paste your resume text here:")

    if st.button("Analyze Resume"):
        # Extract keywords just from the resume
        matched_keywords = re.findall(r'\b\w+\b', resume_text.lower())
        matched_keywords = [w for w in matched_keywords if w not in STOP_WORDS]

        st.subheader("Extracted Keywords from Resume")
        st.write(matched_keywords)

        recommendations = recommend_jobs(matched_keywords)
        if recommendations:
            st.subheader("Job Recommendations")
            st.write(recommendations)

            # Split recommendations into lines for dropdown
            job_options = [line.strip("-• ") for line in recommendations.split("\n") if line.strip()]

            selected_job = st.selectbox("Choose a job title for a roadmap:", job_options)

            if st.button("Generate Roadmap"):
                roadmap = generate_roadmap(selected_job)
                if roadmap:
                    st.subheader(f"Roadmap for {selected_job}")
                    st.write(roadmap)
