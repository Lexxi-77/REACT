import streamlit as st
import google.generativeai as genai
import requests
import json
import re
from google.api_core.exceptions import ResourceExhausted
from datetime import datetime
from streamlit_local_storage import LocalStorage

# --- 1. Page & AI Configuration ---
st.set_page_config(page_title="AI Interviewer", page_icon="🤖", layout="centered")
st.title("AI Interviewer 🤖")

# --- 2. Securely Get API Keys & Config ---
try:
    GEMINI_API_KEYS = st.secrets["GEMINI_API_KEYS"]
    JOTFORM_API_KEY = st.secrets["JOTFORM_API_KEY"]
    JOTFORM_FORM_ID = st.secrets["JOTFORM_FORM_ID"]
    JOTFORM_FIELD_MAPPING = st.secrets["JOTFORM_FIELD_MAPPING"]
    localS = LocalStorage()
except (KeyError, AttributeError):
    st.error("One or more secrets are missing. Please check your Streamlit Cloud secrets configuration.")
    st.stop()

# --- 3. The Interview "Script" with Goals ---
# This list now defines the GOAL for each step, not the exact question.
QUESTIONS = [
    {"key": "name", "goal": "Start the interview by warmly asking for the user's full, official name.", "required": True, "validation": "text"},
    {"key": "age", "goal": "Ask for the user's age.", "required": True, "validation": "age"},
    {"key": "phoneNumber", "goal": "Ask for the user's phone number.", "required": True, "validation": "phone"},
    {"key": "sexualOrientation", "goal": "Ask for the user's sexual orientation, providing these options: Gay/MSM, Lesbian, Bisexual, Queer, Straight, Asexual.", "required": True, "validation": "text"},
    {"key": "genderIdentity", "goal": "Ask for the user's gender identity, providing these options: Cis Man, Cis Woman, Trans Man, Trans Woman, Non-binary, Gender non-conforming.", "required": True, "validation": "text"},
    {"key": "memberOrganisation", "goal": "Ask if the user is part of any member organisation. This is an optional question.", "required": False, "validation": "text"},
    {"key": "summary1", "goal": "Provide a brief, bullet-point summary of the personal details collected so far and ask the user, 'Does that sound correct so far?' to confirm.", "is_summary": True},
    {"key": "consentToStore", "goal": "Transition to consent. Ask for the user's consent to store their data. They must answer 'Yes' or 'No'.", "required": True, "validation": "yes_no"},
    {"key": "consentToUse", "goal": "Ask for the user's consent to use their data for advocacy. They must answer 'Yes' or 'No'.", "required": True, "validation": "yes_no"},
    {"key": "dateOfIncident", "goal": "Transition to the incident report and ask for the date it happened.", "required": True, "validation": "date"},
    {"key": "typeOfViolation", "goal": "Ask for the type of violation, presenting these options: Forced eviction, Family banishment, Sexual violence, Psychological or emotional violence, Political/institutional violence, Cyber harassment/bullying, Denial of HIV services, Denial of SRHR services, Denial of employment, Fired, Detention/arrest, Blackmail.", "required": True, "validation": "text"},
    {"key": "charges", "goal": "If the user mentioned 'Detention/arrest' in their last answer, ask what the charges were. Otherwise, skip this by responding with 'N/A'.", "required": False, "validation": "text", "depends_on": "typeOfViolation", "condition": "Detention/arrest"},
    {"key": "perpetrators", "goal": "Ask for the name or description of the perpetrator(s).", "required": True, "validation": "text"},
    {"key": "caseDescription", "goal": "Ask the user to describe the incident in their own words, encouraging them to be detailed so you can write a good story.", "required": True, "validation": "text"},
    {"key": "summary2", "goal": "Provide a brief, bullet-point summary of the incident details collected so far and ask the user, 'Have I captured the key details correctly?' to confirm.", "is_summary": True},
    {"key": "nameOfReferrer", "goal": "Transition to the final questions and ask for the name of the person who referred them.", "required": True, "validation": "text"},
    {"key": "phoneOfReferrer", "goal": "Ask for the referrer's phone number.", "required": False, "validation": "phone"},
    {"key": "emailOfReferrer", "goal": "Ask for the referrer's email address.", "required": False, "validation": "email"},
    {"key": "supportNeeded", "goal": "Ask what kind of immediate support would be most helpful.", "required": True, "validation": "text"},
    {"key": "supportBudget", "goal": "Ask for an estimate of the cost or budget for the support they need.", "required": True, "validation": "text"},
]

# --- 4. Initialize State ---
if "messages" not in st.session_state:
    stored_history = localS.getItem("chat_history")
    st.session_state.messages = stored_history if stored_history else []
if "answers" not in st.session_state:
    stored_answers = localS.getItem("chat_answers")
    st.session_state.answers = stored_answers if stored_answers else {}
if "current_question_index" not in st.session_state:
    stored_index = localS.getItem("chat_index")
    st.session_state.current_question_index = stored_index if stored_index else 0
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

# --- 6. The New, Stable, and Intelligent Interview Logic ---
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
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                conversation_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
                answers_so_far = json.dumps(st.session_state.answers)
                
                question_prompt = f"""You are a warm, empathetic, and conversational AI assistant. Based on the conversation history and the answers collected so far, your current goal is to: {current_q['goal']}. Please generate the next natural, non-robotic question to ask the user.

                Conversation History:
                {conversation_history}

                Answers Collected So Far:
                {answers_so_far}
                """
                next_question = generate_gemini_response(question_prompt)
                if next_question:
                    st.session_state.messages.append({"role": "assistant", "content": next_question})
                    st.markdown(next_question)
                    localS.setItem("chat_history", st.session_state.messages)

    # Get the user's answer
    if prompt := st.chat_input("Your response..."):
        # Code-based validation
        validation_passed = True
        if "validation" in current_q:
            if current_q["validation"] == "age" and not re.fullmatch(r'\d{1,3}', prompt.strip()):
                validation_passed = False
                st.session_state.messages.append({"role": "assistant", "content": "That doesn't seem to be a valid age. Please provide your age using only numbers (e.g., 26)."})
            elif current_q["validation"] == "phone" and not re.fullmatch(r'[\d\s\+\-\(\)]+', prompt.strip()):
                validation_passed = False
                st.session_state.messages.append({"role": "assistant", "content": "That doesn't seem to be a valid phone number. Please check the format and try again."})

        if validation_passed:
            st.session_state.answers[current_q["key"]] = prompt
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.current_question_index += 1
            localS.setItem("chat_history", st.session_state.messages)
            localS.setItem("chat_answers", st.session_state.answers)
            localS.setItem("chat_index", st.session_state.current_question_index)
        
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
                    # Post-Submission Experience
                    st.subheader("Final Narrative Report")
                    st.markdown(narrative_story)
                    if "reportingForSelf" in st.session_state.answers and st.session_state.answers["reportingForSelf"].lower() != 'yes':
                        st.download_button(label="📥 Download Narrative Report", data=narrative_story.encode('utf-8'), file_name="narrative_report.txt", mime="text/plain")
                else:
                    st.error(f"Submission failed. Status: {response.status_code} - {response.text}")
        
        except Exception as e:
            st.error(f"An error occurred during submission: {e}")
