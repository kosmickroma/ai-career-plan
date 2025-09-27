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
        f"**TASK 1: INTRODUCTION** "
        f"Write a concise, encouraging introductory paragraph (2-3 sentences max) that sets the stage for the roadmap. Do not title or number this paragraph."

        f"**TASK 2: ROADMAP PHASES** " 
        f"Given the goal of becoming a {selected_job}, provide a step-by-step career roadmap "
        f"including the necessary skills, credentials, and projects to become qualified for the job."
        f"Break it into **clear phases** (Phase 1, Phase 2, Phase, 3, etc.), each with a short title and details. "
        f"Format it so each phase starts with 'Phase X: [title]'."

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

# PDF Export Function
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, ListFlowable, ListItem

def generate_pdf(roadmap_text, job_title="Career Roadmap"):
    buffer = io.BytesIO()

    # Create PDF document
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=72)

    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = styles["Title"]
    story.append(Paragraph(f"Career Roadmap for {job_title}", title_style))
    story.append(Spacer(1, 0.25 * inch))

    # Break roadmap into lines
    bullet_items = []
    for line in roadmap_text.splitlines():
        if line.strip().startswith("Phase"):
            # Flush any bullets collected so far
            if bullet_items:
                story.append(ListFlowable(bullet_items, bulletType='bullet'))
                story.append(Spacer(1, 0.1 * inch))
                bullet_items = []

            # Big bold phase header
            story.append(Paragraph(f"<b>{line.strip()}</b>", styles["Heading2"]))
            story.append(Spacer(1, 0.1 * inch))

        elif line.strip().startswith("-") or line.strip().startswith("•"):
            # Collect bullet points
            bullet_items.append(ListItem(Paragraph(line.strip().lstrip("-• ").strip(), styles["Normal"])))

        elif line.strip():
            # Flush bullets if we hit normal text
            if bullet_items:
                story.append(ListFlowable(bullet_items, bulletType='bullet'))
                story.append(Spacer(1, 0.1 * inch))
                bullet_items = []

            # Normal text
            story.append(Paragraph(line.strip(), styles["Normal"]))
            story.append(Spacer(1, 0.1 * inch))

    # Flush any leftover bullets
    if bullet_items:
        story.append(ListFlowable(bullet_items, bulletType='bullet'))
        story.append(Spacer(1, 0.1 * inch))

    # Footer
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("<i>Generated by Career Compass</i>", styles["Normal"]))

    # Build PDF
    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
# ----------------------------------------------------
# Helper: parse AI response into a skills list
# ----------------------------------------------------
def parse_required_skills(text):
    """
    Try to robustly convert an AI response into a list of skills.
    Accepts JSON arrays, JSON objects containing required_skills, or bullet/line lists.
    """
    if not text:
        return []

    # try to find a JSON array in the response
    try:
        # Look for an array like ["skill1","skill2",...]
        m = re.search(r'(\[.*?\])', text, flags=re.S)
        if m:
            arr = json.loads(m.group(1))
            if isinstance(arr, list):
                return [s.strip() for s in arr if isinstance(s, str)]

        # Look for an object with a required_skills key
        m2 = re.search(r'\{.*"required_skills".*\}', text, flags=re.S)
        if m2:
            obj = json.loads(m2.group(0))
            skills = obj.get('required_skills') or obj.get('skills') or []
            return [s.strip() for s in skills if isinstance(s, str)]
    except Exception:
        pass

    # Fallback: split into lines and clean bullets/numbering
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    skills = []
    for line in lines:
        clean = re.sub(r'^[\d\.\)\-\•\s]+', '', line)  # remove numbering/bullets
        clean = re.sub(r':\s*$', '', clean)             # trailing colon
        if ',' in clean:
            parts = [p.strip() for p in clean.split(',') if p.strip()]
            skills.extend(parts)
        else:
            skills.append(clean)
    # dedupe while preserving order
    seen = set()
    out = []
    for s in skills:
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


# ----------------------------------------------------
# Helper: ask the AI for the top skills required for a job
# ----------------------------------------------------
def get_required_skills_for_job(job_title, n=10):
    """
    Calls the Gemini helper to get a short list of required skills for job_title.
    Returns a list of skill strings (possibly empty on error/dry-run).
    """
    ai_prompt = (
        f"List the top {n} skills, tools or technologies required to be successful as a {job_title}. "
        "Reply with either a JSON array (e.g. [\"Python\", \"APIs\"]) or a plain bullet/list — nothing else is required."
    )
    result = call_gemini_withspinner(ai_prompt)
    if result.get("status") == "ok":
        text = result.get("response_text") or ""
        skills = parse_required_skills(text)
        # limit result and strip
        return [s.strip() for s in skills][:n]
    else:
        # dry-run or error: return empty and let UI inform user
        return []


# ----------------------------------------------------
# Helper: check whether a resume contains evidence of a skill
# ----------------------------------------------------
def skill_covered(skill, resume_text):
    """
    Return True if resume_text appears to cover the skill phrase.
    Strategy:
      - exact phrase match (word boundaries)
      - OR any non-stopword token of the skill appears (simple fallback)
    """
    if not skill or not resume_text:
        return False
    s = skill.lower()
    r = resume_text.lower()

    # exact phrase
    if re.search(r'\b' + re.escape(s) + r'\b', r):
        return True

    # check for any important token
    tokens = [t for t in re.findall(r'\w+', s) if t not in STOP_WORDS]
    for t in tokens:
        if re.search(r'\b' + re.escape(t) + r'\b', r):
            return True
    return False


#############################################################
#############################################################

if __name__ == "__main__":
    # Changed title to reflect new functionality
    st.title("Career Compass & Resume Analyzer")
    
    #-------------------------------------------------
    # 1. Initialize session state to manage widget persistence
    # ------------------------------------------------
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

    # NEW: Keep inputs persistent
    if "resume_text" not in st.session_state:
        st.session_state["resume_text"] = ""
    if "pasted_text" not in st.session_state:
        st.session_state["pasted_text"] = ""
    if "target_career_input" not in st.session_state:
        st.session_state["target_career_input"] = ""

    if  'required_skills_map' not in st.session_state:
        st.session_state['required_skills_map'] = {}

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
            # Persist resume info for metrics feedback loop
            st.session_state['resume_keywords'] = matched_keywords
            st.session_state['resume_text'] = resume_text

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
        # ------------------------------------------------------
        # Metrics Feedback Loop: Progress ticker (Testing Phase)
        # ------------------------------------------------------
        # Get cached skills for this job (or fetch if not cached)
        required_skills = st.session_state['required_skills_map'].get(selected_job)

        if required_skills is None:
            #fetch on demand (& cache). Wrap in spinner so user sees activity.
            with st.spinner(f"Fetching top skills for '{selected_job}'..."):
                required_skills = get_required_skills_for_job(selected_job, n=10)
                st.session_state['required_skills_map'][selected_job] = required_skills

        # Get resume text we saved earlier
        resume_text_for_matching = st.session_state.get('resume_text', ' ') or ' '

        if required_skills:
            #Count coverage
            covered = sum(1 for sk in required_skills if skill_covered(sk, resume_text_for_matching))
            total = len(required_skills)

            # Display count and progress bar
            st.markdown(f"**You've got {covered}/{total} recommended skills covered for _{selected_job}_**")
            try: 
                st.progress(covered / total)
            except Exception:
                    # In case of a division or odd values (defensive)
                    pass
                # Show checklist of skills (simple)
            for sk in required_skills:
                    mark = "✅" if skill_covered(sk, resume_text_for_matching) else "❌"
                    st.write(f"{mark} {sk}")
        else:
            # No skills available (dry-run / API failure)
            st.info("No skills list available for this job (API may be in dry-run mode or the lookup failed). ")

    #Roadmap button (only shows after job rec in tab 2)
    if st.session_state['resume_analyzed'] and st.session_state['job_options']:
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

    roadmap_text = st.session_state['roadmap_text']

    # Split roadmap into phases based on "Phase X:"
    phases = re.split(r'(Phase\s+\d+:)', roadmap_text)

    if len(phases) > 1:
        # Capture the initial text (The introduction is in phases[0])
        intro_text = phases[0].strip()
        if intro_text:
            st.markdown(intro_text)
            st.markdown("---") 

        structured_phases = []
        for i in range(1, len(phases), 2):
            title = phases[i].strip()
            content = phases[i+1].strip() if i+1 < len(phases) else ""
            structured_phases.append((title, content))
        
        # Loop through phases
        for idx, (title, content) in enumerate(structured_phases):
            with st.expander(title, expanded=(idx == 0)):  # Phase 1 auto-open
                st.markdown(content)

            # Add reminder in Phase 1 only
            if idx == 0:
                st.markdown("👉 *Scroll down for a full roadmap download option.*")

    else:
        # Fallback: single expander if no phases detected
        with st.expander("📜 View Career Roadmap", expanded=True):
            st.markdown(roadmap_text)

    # --- Global Download Option at the bottom ---
    st.markdown("---")
    st.download_button(
        label="⬇️ Download Full Roadmap",
        data=roadmap_text.encode("utf-8"),
        file_name=f"{st.session_state['selected_job_for_roadmap'].replace(' ','_')}_Career_Roadmap.txt",
        mime="text/plain",
        key="download_button_full"
    )

    # --- PDF Download Option ---
    pdf_bytes = generate_pdf(
        roadmap_text,
        job_title=st.session_state['selected_job_for_roadmap']
    )
    col1, col2 = st.columns (2)

    with col1:
        st.download_button(
            label="📥 Download Full Roadmap as PDF",
            data=pdf_bytes,
            file_name=f"{st.session_state['selected_job_for_roadmap'].replace(' ', '_')}_Career_Roadmap.pdf",
            mime="application/pdf",
            key="download_button_pdf"
    )
    with col2:
        if st.button("🔄 Start Over"):
            # Clear only the keys we care about
            keys_to_clear = [
                "job_options",
                "recommendations",
                "resume_analyzed",
                "roadmap_text",
                "resume_keywords",
                "required_skills_map",
                "selected_job_for_roadmap",
                "resume_text",
                "pasted_text",
                "target_career_input",
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()