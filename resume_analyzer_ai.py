# Resume Analyzer
# Phase 1 Gathering and Pre-process 
# Open the my_resume.txt file and read its contents
import requests
import os
import json

def generate_career_recommendations():

    with open ("my_resume.txt", "r") as file:
        my_resume_text = file.read()

    #Open the job_description.txt file and read its contents
    with open ("job_description.txt", "r") as file:
        job_description_text = file.read()

    # Lower & Split text
    resume_words = my_resume_text.replace(',','').replace('.','').lower().split()
    job_words = job_description_text.replace(',','').replace('.','').lower().split()

    # Matching Keywords
    matched_keywords = []
    for word in job_words:
        if word in resume_words:
            matched_keywords.append(word)


    # Counting Keywords using a dictionary
    keyword_counts = {}
    for word in matched_keywords:
        if word in keyword_counts:
            keyword_counts[word] += 1
        else:
            keyword_counts[word] = 1

    # Step 4: Calculate the score
    total_job_keywords = len(set(job_words))
    matched_keyword_count = len(set(matched_keywords))
    match_percentage = (matched_keyword_count / total_job_keywords) * 100

    # This returns the list of keywords so we can use it later return matched_keywords
    return matched_keywords

# Recommend Jobs
def recommend_jobs (matched_keywords):
    api_key = os.getenv ("GOOGLE_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    ai_prompt = f"Act as a professional career counselor. Given a resume with the following keywords: {matched_keywords}, recommend a few related job titles for a careerchanger with this background. Be concise and provide a list of 3-5 titles."
    
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": ai_prompt
                    }
                ]
            }
        ]
    }
    response = requests.post (url, headers=headers, data=json.dumps(data))

    if response.status_code == 200:
        recommendations = response.json()['candidates'][0]['content']['parts'][0]['text']
        print ("\nAI-Powered Job Recommendations:")
        print ("---")
        print (recommendations)
    else:
        print (f"Error: Unable to get recommendations. Status code: {response.status_code}")

    return ai_prompt
#Generate Roadmap
def generate_roadmap (selected_job):
    api_key = os.getenv ("GOOGLE_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    ai_prompt = f"Act as a professional career counselor. Given the goal of becoming a {selected_job}, provide a step-by-step career roadmap including the necessary skills, credentials, and projects to become qualified for the job."

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": ai_prompt
                    }
                ]
            }
        ]
    }
                    
    response = requests.post (url, headers=headers, data=json.dumps(data))

    if response.status_code == 200:
        roadmap = response.json()['candidates'][0]['content']['parts'][0]['text']
        print ("\nAI-Powered Career Roadmap:")
        print ("---")
        print (roadmap)
    else: 
        print (f"Error: Unable to get a roadmap. Status code: {response.status_code}")
        print (response.text)

    return ai_prompt
# Get the keywords from the resume analysis
keywords = generate_career_recommendations()
# Use keywords to get job recommendations
recommendations_prompt = recommend_jobs (keywords)
# Get the job title from the user
selected_job = input ("Which career would you like a roadmap for?")
#Use the user's input to generate the roadmap prompt
roadmap_prompt = generate_roadmap (selected_job)



