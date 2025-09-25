# Resume Analyzer
# Phase 1 Gathering and Pre-process 
# Open the my_resume.txt file and read its contents

def generate_career_recommendations():

    with open ("my_resume.txt", "r") as file:
        my_resume_text = file.read()

#Open the job_description.txt file and read its contents
    with open ("job_description.txt", "r") as file:
        job_description_text = file.read()

# Lower & Split text
    resume_words = my_resume_text.replace(',','').replace('.','').lower().split()
    job_words = job_description_text.replace(',','').replace('.','').lower().split()

# Step 2: Matching Keywords
    matched_keywords = []
    for word in job_words:
        if word in resume_words:
            matched_keywords.append(word)


# Step 3: Counting Keywords using a dictionary
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

# Call function
generate_career_recommendations()

# Recommend Jobs
def recommend_jobs (matched_keywords):
    ai_prompt = f"Act as a professional career counselor. Given a resume with the following keywords: {matched_keywords}, recommend a few related job titles for a careerchanger with this background. Be concise and provide a list of 3-5 titles."

    print ("Sending this prompt to the AI...")
    print ("---")
    print (ai_prompt)

# First get the keywords from the resume analysis
keywords = generate_career_recommendations()

# Second, use those keywords to get job recommendations
recommend_jobs (keywords)

# Get the job title from the user
selected_job = input ("Which Career Would You Like A Roadmap For?")

# For now, just print the selected job to see that it works
print (f"You selected: {selected_job}")

# Phase 3 Building the Career Roadmap Function
#Generate Roadmap
def generate_roadmap (selected_job):
    ai_prompt = f"Act as a professional career counselor. Given the goal of becoming a {selected_job}, provide a step-by-step career roadmap including the necessary skills, credentials, and projects to become qualified for the job."
    print ("Generating a roadmap for...")
    print ("---")
    print (ai_prompt)
generate_roadmap (selected_job)
