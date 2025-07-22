import streamlit as st
import google.generativeai as genai
import requests
import json
from google.api_core.exceptions import ResourceExhausted
from datetime import datetime

# --- 1. Page & AI Configuration ---
st.set_page_config(page_title="AI Interviewer", page_icon="🤖")
st.title("AI Interviewer 🤖")

# --- 2. Securely Get API Keys & Config ---
try:
    GEMINI_API_KEYS = st.secrets["GEMINI_API_KEYS"]
    JOTFORM_API_KEY = st.secrets["JOTFORM_API_KEY"]
    JOTFORM_FORM_ID = st.secrets["JOTFORM_FORM_ID"]
    JOTFORM_FIELD_MAPPING = st.secrets["JOTFORM_FIELD_MAPPING"]
except (KeyError, AttributeError):
    st.error("One or more secrets are missing. Please check your Streamlit Cloud secrets configuration.")
    st.stop()

# --- 3. The Interview "Script" ---
# This list now defines the GOAL for each step, not the exact question.
QUESTIONS = [
    {"key": "name", "goal": "Ask for the user's full, official name to begin the interview.", "required": True},
    {"key": "age", "goal": "Ask for the user's age.", "required": True},
    {"key": "phoneNumber", "goal": "Ask for the user's phone number.", "required": True},
    {"key": "sexualOrientation", "goal": "Ask for the user's sexual orientation, providing these options: Gay/MSM, Lesbian, Bisexual, Queer, Straight, Asexual.", "required": True},
    {"key": "genderIdentity", "goal": "Ask for the user's gender identity, providing these options: Cis Man, Cis Woman, Trans Man, Trans Woman, Non-binary, Gender non-conforming.", "required": True},
    {"key": "memberOrganisation", "goal": "Ask if the user is part of any member organisation. This is an optional question.", "required": False},
    {"key": "consentToStore", "goal": "Ask for the user's consent to store their data. They must answer 'Yes' or 'No'.", "required": True},
    {"key": "consentToUse", "goal": "Ask for the user's consent to use their data for advocacy. They must answer 'Yes' or 'No'.", "required": True},
    {"key": "dateOfIncident", "goal": "Transition to the incident report and ask for the date it happened.", "required": True},
    {"key": "typeOfViolation", "goal": "Ask for the type of violation, presenting these options: Forced eviction, Family banishment, Sexual violence, Psychological or emotional violence, Political/institutional violence, Cyber harassment/bullying, Denial of HIV services, Denial of SRHR services, Denial of employment, Fired, Detention/arrest, Blackmail.", "required": True},
    {"key": "charges", "goal": "If the user mentioned 'Detention/arrest', ask what the charges were. Otherwise, skip this.", "required": False, "depends_on": "typeOfViolation", "condition": "Detention/arrest"},
    {"key": "perpetrators", "goal": "Ask for the name or description of the perpetrator(s).", "required": True},
    {"key": "caseDescription", "goal": "Ask the user to describe the incident in their own words, encouraging them to be detailed.", "required": True},
    {"key": "nameOfReferrer", "goal": "Transition to the final questions and ask for the name of the person who referred them.", "required": True},
    {"key": "phoneOfReferrer", "goal": "Ask for the referrer's phone number.", "required": False},
    {"key": "emailOfReferrer", "goal": "Ask for the referrer's email address.", "required": False},
    {"key": "supportNeeded", "goal": "Ask what kind of immediate support would be most helpful.", "required": True},
    {"key": "supportBudget", "goal": "Ask for an estimate of the cost or budget for the support they need.", "required": True},
]

# --- 4. Initialize State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "current_question_index" not in st.session_state:
    st.session_state.current_question_index = 0
if "key_index" not in st.session_state:
    st.session_state.key_index = 0

# --- 5. Helper Function for AI Calls with Key Rotation ---
def generate_gemini_response(prompt_text):
    while st.session_state.key_index < len(GEMINI_API_KEYS):
        try:
            current_key = GEMINI_API_KEYS[st.session_state.key_index]
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt_text)
            return response.text
        except ResourceExhausted:
            st.session_state.key_index += 1
            st.warning(f"Daily limit reached for key #{st.session_state.key_index}. Switching to the next key...")
            continue
    st.error("All available API keys have reached their daily free limit. Please try again tomorrow.")
    return None

# --- 6. The New, Stable Interview Logic ---
interview_complete = st.session_state.current_question_index >= len(QUESTIONS)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if not interview_complete:
    current_q = QUESTIONS[st.session_state.current_question_index]

    # Handle conditional questions
    if "depends_on" in current_q:
        dependency_key = current_q["depends_on"]
        dependency_value = current_q["condition"]
        if dependency_key not in st.session_state.answers or dependency_value not in st.session_state.answers[dependency_key]:
            st.session_state.current_question_index += 1
            st.rerun()

    # Generate and display the next question if it hasn't been asked yet
    if not st.session_state.messages or st.session_state.messages[-1]["role"] == "user":
        conversation_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
        question_prompt = f"""You are a warm, empathetic, and conversational AI assistant. Based on the conversation history below, your current goal is to: {current_q['goal']}. Please generate the next natural, non-robotic question to ask the user.

        Conversation History:
        {conversation_history}
        """
        next_question = generate_gemini_response(question_prompt)
        if next_question:
            st.session_state.messages.append({"role": "assistant", "content": next_question})
            with st.chat_message("assistant"):
                st.markdown(next_question)

    # Get the user's answer
    if prompt := st.chat_input("Your response..."):
        st.session_state.answers[current_q["key"]] = prompt
        st.session_state.messages.append({"role": "user", "content": prompt})
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
                final_report_data = {}
                for key, value in st.session_state.answers.items():
                    if key in JOTFORM_FIELD_MAPPING and value:
                        final_report_data[JOTFORM_FIELD_MAPPING[key]] = str(value)

                final_report_data[JOTFORM_FIELD_MAPPING["dateAndTime"]] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                final_report_data[JOTFORM_FIELD_MAPPING["caseAssignedTo"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["referralReceivedBy"]] = "Alex Ssemambo"
                
                narrative_prompt = f"Based on the following interview answers, please write a clear, coherent, third-person narrative of the incident: {json.dumps(st.session_state.answers)}"
                narrative_story = generate_gemini_response(narrative_prompt)
                if narrative_story:
                    final_report_data[JOTFORM_FIELD_MAPPING["caseDescription"]] = narrative_story

                submission_payload = {f'submission[{key}]': value for key, value in final_report_data.items()}
                url = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/submissions?apiKey={JOTFORM_API_KEY}"
                response = requests.post(url, data=submission_payload)

                if response.status_code in [200, 201]:
                    st.success("Success! Your report has been securely submitted.")
                else:
                    st.error(f"Submission failed. Status: {response.status_code} - {response.text}")
        
        except Exception as e:
            st.error(f"An error occurred during submission: {e}")
