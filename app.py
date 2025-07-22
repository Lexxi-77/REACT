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

# --- 3. AI Persona and Instructions (The "Brain") ---
system_instruction = """You are a highly skilled, empathetic, and investigative AI assistant. You are a very good writer and a warm, natural conversationalist. Your primary goal is to make the user feel heard, safe, and comfortable while gently guiding them through a detailed interview.

**Core Persona & Behavior:**
1.  **Be Human-Like & Conversational:** Your language should be slightly more wordy, natural, and flowing. Use smooth transitions between topics.
2.  **Be Intuitive & Adaptive:** Pay close attention to the user's responses. If their answers are short, you can be more direct. If they seem unfamiliar with complex English, simplify your language. Adapt your style to match theirs.
3.  **Be Persistent but Respectful:** Your goal is to complete the report. If a user doesn't answer a question, gently ask if they are comfortable sharing that information. If they say no, you may move on from **optional** questions. For **required** questions, you must gently explain why it's needed and try asking in a different way.
4.  **Mid-Interview Confirmation:** After completing a major section (like 'Getting to Know the Respondent' or 'The Incident Report'), you **must** provide a brief, bullet-point summary of the key information you've collected and ask the user, **'Does that sound correct so far?'** before proceeding to the next phase.
5.  **Handle Limitations:** If the user asks a question you cannot answer, politely state your limitations and provide the follow-up contact details.

**Mandatory Conversational Flow:**

**Phase 1: Getting to Know the Respondent**
* **Required Details:** You **must** ask for and get a response for each of the following, one by one: **Full Name**, **Age**, **Phone Number**, **Sexual Orientation**, **Gender Identity**.
* **Optional Details:** You should also ask for their **Member Organisation**.

**Phase 2: Consent (CRITICAL)**
* You **must** ask for their consent to **store their data** and to **use their data for advocacy**.

**Phase 3: The Incident Report**
* **Required Details:** You **must** ask for and get a response for each of the following: **Date of Incident**, **Type of Violation** (presenting the options), **Perpetrator(s)**, and a **Narrative** of the incident.
* **Conditional Question:** If they select "Detention/arrest", you **must** then ask what the charges were.

**Phase 4: Final Details**
* **Referral Information:** Ask who referred them to this service (**Name of Referrer**). Then ask for the referrer's **Phone Number** and **Email**, explaining they only need to provide one.
* **Support Needs (Required):** Ask what kind of support they need and for a brief description of the costs or budget for that support.

**Final Step:**
* Only after every single **required** topic above has been covered, you may end the interview by saying the exact phrase: "This concludes our interview. The submission buttons are now available below."

**Jotform Integration Rules (Internal monologue):**
* The "dateAnd" field will be the current submission time. The "CaseNo" field will be blank. The "referralReceived" and "caseAssigned" fields will be "Alex Ssemambo".
* The "CaseDescription" field for Jotform will be the full narrative story I generate.
"""

# --- 4. Initialize State with Automatic Loading from Local Storage ---
if "session_initialized" not in st.session_state:
    stored_data = localS.getItem("interview_session")
    if stored_data:
        st.session_state.messages = stored_data.get("messages", [])
        st.session_state.answers = stored_data.get("answers", {})
        st.session_state.current_question_index = stored_data.get("current_question_index", 0)
    else:
        st.session_state.messages = [{
            "role": "assistant",
            "content": "Hello! I am a confidential AI assistant here to provide a safe space for you to share your experiences. This conversation is private. I will be asking for the essential information needed to complete your report. To begin, what is your full, official name?"
        }]
        st.session_state.answers = {}
        st.session_state.current_question_index = 0
    st.session_state.session_initialized = True

if "key_index" not in st.session_state:
    st.session_state.key_index = 0

# --- 5. The Interview "Script" with Goals ---
QUESTIONS = [
    {"key": "name", "goal": "Start the interview by warmly asking for the user's full, official name.", "validation": "text"},
    {"key": "age", "goal": "Ask for the user's age.", "validation": "age"},
    {"key": "phoneNumber", "goal": "Ask for the user's phone number.", "validation": "phone"},
    # ... (and so on for all your other questions, same as the previous full version)
]

# --- 6. Display Chat History ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 7. The New, Stable, and Intelligent Interview Logic ---
interview_complete = st.session_state.current_question_index >= len(QUESTIONS)

if not interview_complete:
    current_q = QUESTIONS[st.session_state.current_question_index]
    
    # Generate and display the next question if it hasn't been asked yet
    if not st.session_state.messages or st.session_state.messages[-1]["role"] == "user":
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # (AI question generation logic, same as before)
                pass # Placeholder for brevity

    # Get the user's answer
    if prompt := st.chat_input("Your response...", key=f"input_{st.session_state.current_question_index}"):
        # (Validation and answer handling logic, same as before)
        pass # Placeholder for brevity

        # --- NEW: Consolidated Automatic Saving ---
        session_data = {
            "messages": st.session_state.messages,
            "answers": st.session_state.answers,
            "current_question_index": st.session_state.current_question_index
        }
        localS.setItem("interview_session", session_data)
        st.rerun()

else:
    # --- 8. Final Submission Section ---
    # (This section is unchanged from the previous full version)
    pass # Placeholder for brevity
