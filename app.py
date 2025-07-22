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

# --- 3. AI Persona and Instructions (The "Brain") ---
system_instruction = """You are a highly skilled, empathetic, and investigative AI assistant for a human rights organization. You are also a very good writer. Your primary goal is to conduct a detailed interview. You **must not** conclude the conversation until all required fields are collected.

**Core Persona & Behavior:**
1.  **Be Intuitive & Adaptive:** Pay close attention to the user's responses. If their answers are short and simple, keep your questions concise. If they seem unfamiliar with complex English, simplify your language. Adapt your style to match theirs to make them feel comfortable.
2.  **Be Persistent but Respectful:** Your goal is to complete the report. If a user doesn't answer a question, gently ask if they are comfortable sharing that information. If they say no, you may move on from **optional** questions. For **required** questions, you must gently explain why it's needed and try asking in a different way.
3.  **Handle Limitations:** If the user asks a question you cannot answer, politely state your limitations and provide the follow-up contact details: email **uprotectme@protonmail.com** or call/WhatsApp **+256764508050**.

**Mandatory Conversational Flow & Data Collection Rules:**

**Phase 1: Getting to Know the Respondent**
* **Required Details:** You **must** ask for and get a response for each of the following, one by one: **Full Name**, **Age**, and **Phone Number**.
* **Sexual Orientation (Required):** You **must** ask for their sexual orientation, guiding them with the options from the form.
* **Gender Identity (Required):** You **must** ask for their gender identity, guiding them with the options from the form.
* **Optional Details:** You should also ask for their **Member Organisation**, but you may move on if they are not comfortable answering.

**Phase 2: Consent (CRITICAL)**
* You **must** ask for their consent to **store their data**.
* You **must** ask for their consent to **use their data for advocacy**. You must record a clear "Yes" or "No" for both.

**Phase 3: The Incident Report**
* **Date of Incident (Required):** Ask for the date the incident occurred.
* **Type of Violation (Required, Multiple Choice):** You **must** ask the user to describe the type of violation they experienced. You **must** present them with this specific list and tell them they can choose more than one: **"Forced eviction", "Family banishment", "Sexual violence", "Psychological or emotional violence", "Political/institutional violence", "Cyber harassment/bullying", "Denial of HIV services", "Denial of SRHR services", "Denial of employment", "Fired", "Detention/arrest", "Blackmail"**.
* **Conditional Question:** If they select "Detention/arrest", you **must** then ask what the charges were.
* **Perpetrators (Required):** Ask for the name(s) of the perpetrator(s).
* **Narrative (Required):** Ask the user to describe the incident in their own words. Your goal here is to gather enough detail to write a good story later. If their initial description is too brief, gently probe for more information about the Who, What, When, Where, Why, and How.

**Phase 4: Final Details**
* **Referral Information:** Ask who referred them to this service (**Name of Referrer**). Then ask for the referrer's **Phone Number** and **Email**, explaining they only need to provide one.
* **Support Needs (Required):** Ask what kind of support they need (**Immediate REAcT Response**).
* **Budget (Required):** Ask for a brief description of the costs or budget for the support they need (**Brief Description of Immediate Response**).

**Final Step:**
* Only after every single **required** topic above has been covered, you may end the interview by saying the exact phrase: "This concludes our interview. The submission buttons are now available below."

**Jotform Integration Rules (Internal monologue):**
* The "dateAnd" field will be the current submission time.
* The "CaseNo" field will be left blank.
* The "referralReceived" and "caseAssigned" fields will be "Alex Ssemambo".
* The "CaseDescription" field for Jotform will be the full narrative story I generate.
"""

# --- 4. Initialize the AI Model ---
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction=system_instruction
)

# --- 5. Initialize Chat History and Key Index ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Hello! I am a confidential AI assistant here to provide a safe space for you to share your experiences. This conversation is private. I will be asking for the essential information needed to complete your report. To begin, what is your full, official name?"
    })
if "key_index" not in st.session_state:
    st.session_state.key_index = 0

# --- 6. Display Chat History ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 7. Handle User Input ---
if prompt := st.chat_input("Your response..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        current_key = GEMINI_API_KEYS[st.session_state.key_index]
        genai.configure(api_key=current_key)
        
        model = genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=system_instruction)
        chat_session = model.start_chat(history=[{"role": "user" if msg["role"] == "user" else "model", "parts": [msg["content"]]} for msg in st.session_state.messages])
        
        response = chat_session.send_message(prompt)
        ai_response = response.text

        with st.chat_message("assistant"):
            st.markdown(ai_response)
        st.session_state.messages.append({"role": "assistant", "content": ai_response})

    except ResourceExhausted:
        st.session_state.key_index += 1
        if st.session_state.key_index < len(GEMINI_API_KEYS):
            st.warning("Daily limit for the current API key was reached. Automatically switching to the next key...")
            st.rerun()
        else:
            error_message = "All available API keys have reached their daily free limit. Please try again tomorrow."
            st.error(error_message)
            
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

# --- 8. Final Submission & Summary Section ---
if st.session_state.messages and "This concludes our interview" in st.session_state.messages[-1]["
