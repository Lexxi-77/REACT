import streamlit as st
import google.generativeai as genai
import requests
import json
from datetime import datetime

# --- 1. Page & AI Configuration ---
st.set_page_config(page_title="AI Interviewer", page_icon="🤖")
st.title("AI Interviewer 🤖")

# --- 2. Securely Get API Keys & Config ---
try:
    JOTFORM_API_KEY = st.secrets["JOTFORM_API_KEY"]
    JOTFORM_FORM_ID = st.secrets["JOTFORM_FORM_ID"]
    JOTFORM_FIELD_MAPPING = st.secrets["JOTFORM_FIELD_MAPPING"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 
    genai.configure(api_key=GEMINI_API_KEY)
except (KeyError, AttributeError):
    st.error("One or more secrets are missing. Please check your Streamlit Cloud secrets configuration.")
    st.stop()

# --- 3. The Interview "Script" ---
# This is the list of all questions the app will ask, in order.
QUESTIONS = [
    {"key": "name", "question": "To begin, what is your full, official name?", "required": True},
    {"key": "age", "question": "Thank you. And what is your age?", "required": True},
    {"key": "phoneNumber", "question": "What is the best phone number to reach you at?", "required": True},
    {"key": "sexualOrientation", "question": "To help me understand your situation, would you be comfortable sharing your sexual orientation? The options are Gay/MSM, Lesbian, Bisexual, Queer, Straight, or Asexual.", "required": True},
    {"key": "genderIdentity", "question": "Thank you. And how do you identify in terms of your gender? The options are Cis Man, Cis Woman, Trans Man, Trans Woman, Non-binary, or Gender non-conforming.", "required": True},
    {"key": "memberOrganisation", "question": "Are you part of any member organisation? This is optional.", "required": False},
    {"key": "consentToStore", "question": "Before we continue, I need to ask for your consent. Are you comfortable with me storing the information you provide today? Please answer with 'Yes' or 'No'.", "required": True},
    {"key": "consentToUse", "question": "Thank you. And are you comfortable with this information being used anonymously for advocacy purposes to help others? Please answer with 'Yes' or 'No'.", "required": True},
    {"key": "dateOfIncident", "question": "Now, let's talk about the incident itself. Can you please tell me the date when this happened?", "required": True},
    {"key": "typeOfViolation", "question": "How would you describe the type of violation you experienced? You can choose more than one from this list: Forced eviction, Family banishment, Sexual violence, Psychological or emotional violence, Political/institutional violence, Cyber harassment/bullying, Denial of HIV services, Denial of SRHR services, Denial of employment, Fired, Detention/arrest, Blackmail.", "required": True},
    {"key": "charges", "question": "If you were detained or arrested, what were the charges against you? If this doesn't apply, you can just say 'N/A'.", "required": False},
    {"key": "perpetrators", "question": "Could you please provide the name or a description of the person or people responsible?", "required": True},
    {"key": "caseDescription", "question": "Thank you for providing those details. Now, please take as much time as you need to describe what happened in your own words. The more detail you can provide, the better.", "required": True},
    {"key": "nameOfReferrer", "question": "We're almost done. To help us understand how people are finding us, could you tell me the name of the person who referred you to this service?", "required": True},
    {"key": "phoneOfReferrer", "question": "What is the referrer's phone number? If you don't have it, you can provide their email in the next question.", "required": False},
    {"key": "emailOfReferrer", "question": "And what is the referrer's email address?", "required": False},
    {"key": "supportNeeded", "question": "To help us understand your situation, what kind of immediate support would be most helpful to you right now?", "required": True},
    {"key": "supportBudget", "question": "Thank you. And do you have an estimate of the cost or budget for the support you need?", "required": True},
]

# --- 4. Initialize State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "current_question_index" not in st.session_state:
    st.session_state.current_question_index = 0

# --- 5. Display Chat History ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 6. The New, Stable Interview Logic ---
interview_complete = st.session_state.current_question_index >= len(QUESTIONS)

if not interview_complete:
    # Get the current question
    current_q = QUESTIONS[st.session_state.current_question_index]
    
    # Display the current question if it's not already the last message
    if not st.session_state.messages or st.session_state.messages[-1]["content"] != current_q["question"]:
        st.session_state.messages.append({"role": "assistant", "content": current_q["question"]})
        with st.chat_message("assistant"):
            st.markdown(current_q["question"])

    # Get the user's answer
    if prompt := st.chat_input("Your response..."):
        # Save the answer
        st.session_state.answers[current_q["key"]] = prompt
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Move to the next question
        st.session_state.current_question_index += 1
        st.rerun()

else:
    # --- 7. Final Submission Section ---
    if not st.session_state.messages or "This concludes our interview" not in st.session_state.messages[-1]["content"]:
        final_message = "Thank you. This concludes our interview. The submission button is now available below."
        st.session_state.messages.append({"role": "assistant", "content": final_message})
        with st.chat_message("assistant"):
            st.markdown(final_message)

    st.write("---")
    st.subheader("Finalize and Submit Report")
    
    if st.button("Submit Full Report"):
        try:
            with st.spinner("Preparing and submitting your report..."):
                # Prepare the data payload from the collected answers
                final_report_data = {}
                for key, value in st.session_state.answers.items():
                    if key in JOTFORM_FIELD_MAPPING and value:
                        final_report_data[JOTFORM_FIELD_MAPPING[key]] = str(value)

                # Add automated data
                final_report_data[JOTFORM_FIELD_MAPPING["dateAndTime"]] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                final_report_data[JOTFORM_FIELD_MAPPING["caseAssignedTo"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["referralReceivedBy"]] = "Alex Ssemambo"
                
                # Use AI to generate the narrative for the case description
                narrative_prompt = f"Based on the following interview answers, please write a clear, coherent, third-person narrative of the incident: {json.dumps(st.session_state.answers)}"
                summary_model = genai.GenerativeModel('gemini-1.5-flash')
                summary_response = summary_model.generate_content(narrative_prompt)
                final_report_data[JOTFORM_FIELD_MAPPING["caseDescription"]] = summary_response.text

                # Submit to Jotform
                submission_payload = {f'submission[{key}]': value for key, value in final_report_data.items()}
                url = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/submissions?apiKey={JOTFORM_API_KEY}"
                response = requests.post(url, data=submission_payload)

                if response.status_code in [200, 201]:
                    st.success("Success! Your report has been securely submitted.")
                else:
                    st.error(f"Submission failed. Status: {response.status_code} - {response.text}")
        
        except Exception as e:
            st.error(f"An error occurred during submission: {e}")
