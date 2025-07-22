import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime
import json

# Load secrets
GEMINI_KEYS = st.secrets["gemini_keys"]
JOTFORM_API_KEY = st.secrets["jotform_api_key"]
JOTFORM_FORM_ID = st.secrets["jotform_form_id"]
FIELD_MAP = st.secrets["JOTFORM_FIELD_MAPPING"]

# Session state initialization
if "conversation" not in st.session_state:
    st.session_state.conversation = []
if "current_key_index" not in st.session_state:
    st.session_state.current_key_index = 0

# Gemini API setup
def get_gemini_model():
    key = GEMINI_KEYS[st.session_state.current_key_index]
    genai.configure(api_key=key)
    return genai.GenerativeModel("gemini-1.5-flash")

def rotate_key():
    st.session_state.current_key_index += 1
    if st.session_state.current_key_index >= len(GEMINI_KEYS):
        st.error("All Gemini API keys have reached their daily limit. Please try again tomorrow.")
        st.stop()

# Interviewer AI
def ask_next_question():
    model = get_gemini_model()
    history = "\n".join([f"{x['role']}: {x['content']}" for x in st.session_state.conversation])
    prompt = f"""
You are a warm, empathetic interviewer from a human rights organization.
Your job is to gently guide the user through a detailed interview to document a human rights violation.

Conversation so far:
{history}

Your goal is to ask the next appropriate question to gather required information.
Respond with only the next question.
"""
    try:
        response = model.generate_content([{"text": prompt}])
        return response.text
    except Exception as e:
        if "ResourceExhausted" in str(e):
            rotate_key()
            return ask_next_question()
        else:
            st.error(f"Gemini API error: {e}")
            st.stop()

# Documenter AI
def generate_report_and_json():
    model = get_gemini_model()
    transcript = "\n".join([f"{x['role']}: {x['content']}" for x in st.session_state.conversation])
    prompt = f"""
You are a documentation AI. Given the following interview transcript, generate:

1. A third-person narrative of the incident.
2. A JSON object with all required and optional fields.

Transcript:
{transcript}
"""
    try:
        response = model.generate_content([{"text": prompt}])
        return response.text
    except Exception as e:
        if "ResourceExhausted" in str(e):
            rotate_key()
            return generate_report_and_json()
        else:
            st.error(f"Gemini API error: {e}")
            st.stop()

# Jotform Submission
def submit_to_jotform(json_data, narrative):
    payload = {
        FIELD_MAP["dateAnd"]: datetime.now().isoformat(),
        FIELD_MAP["referralReceived"]: "Alex Ssemambo",
        FIELD_MAP["caseAssigned"]: "Alex Ssemambo",
        FIELD_MAP["CaseDescription"]: narrative,
    }
    for key, value in json_data.items():
        if key in FIELD_MAP:
            payload[FIELD_MAP[key]] = value

    url = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/submissions?apiKey={JOTFORM_API_KEY}"
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            st.success("✅ Report submitted successfully.")
        else:
            st.error(f"❌ Submission failed: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Jotform API error: {e}")

# UI
st.title("🕊️ Human Rights Interview Agent")
st.markdown("This AI will guide you through a confidential interview to document any human rights violations you’ve experienced.")

if st.button("Start Interview") and not st.session_state.conversation:
    st.session_state.conversation.append({"role": "system", "content": "Begin interview"})
    question = ask_next_question()
    st.session_state.conversation.append({"role": "assistant", "content": question})

if st.session_state.conversation:
    last = st.session_state.conversation[-1]
    if last["role"] == "assistant":
        st.markdown(f"**{last['content']}**")
        user_input = st.text_input("Your response:", key=len(st.session_state.conversation))
        if user_input:
            st.session_state.conversation.append({"role": "user", "content": user_input})
            question = ask_next_question()
            st.session_state.conversation.append({"role": "assistant", "content": question})
            st.experimental_rerun()

if st.button("Submit Full Report"):
    result = generate_report_and_json()
    try:
        narrative, json_block = result.split("JSON:")
        json_data = json.loads(json_block.strip())
        submit_to_jotform(json_data, narrative.strip())
        st.markdown("📎 Please send any supporting evidence to **uprotectme@protonmail.com** or via WhatsApp to **+256764508050**.")
    except Exception as e:
        st.error(f"❌ Error parsing Documenter output: {e}")
