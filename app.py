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
1.  **Be Human-Like & Conversational:** Your language should be slightly more wordy, natural, and flowing. Use smooth transitions between topics. For example, instead of just asking the next question, say things like, "Thank you for sharing that with me. If it's okay, the next thing I'd like to ask about is..."
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
* **Referral Information:** Ask who referred them and for the referrer's contact details.
* **Support Needs (Required):** Ask what kind of support they need and for a brief description of the costs or budget.

**Final Step:**
* Only after every single **required** topic above has been covered, you may end the interview by saying the exact phrase: "This concludes our interview. The submission buttons are now available below."

**Jotform Integration Rules (Internal monologue):**
* The "dateAnd" field will be the current submission time. The "CaseNo" field will be blank. The "referralReceived" and "caseAssigned" fields will be "Alex Ssemambo".
* The "CaseDescription" field for Jotform will be the full narrative story I generate.
"""

# --- 4. Robust Data Validation Function ---
def validate_input(input_text, field_type):
    if field_type == "age":
        return bool(re.fullmatch(r'\d{1,3}', input_text.strip()))
    if field_type == "phone":
        # This is a simple check for digits and common characters, can be improved
        return bool(re.fullmatch(r'[\d\s\+\-\(\)]+', input_text.strip()))
    return True # Default to true for non-validated fields

# --- 5. Initialize Chat History and Key Index ---
if "messages" not in st.session_state:
    # Try to load from local storage first
    stored_history = localS.getItem("chat_history")
    if stored_history:
        st.session_state.messages = stored_history
    else:
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

    # --- Code-Based Validation for specific fields ---
    last_question = st.session_state.messages[-2]['content'].lower() if len(st.session_state.messages) > 1 else ""
    validation_error = None
    if "age" in last_question and not validate_input(prompt, "age"):
        validation_error = "That doesn't seem to be a valid age. Please provide your age using only numbers (e.g., 26)."
    elif "phone number" in last_question and not validate_input(prompt, "phone"):
        validation_error = "That doesn't seem to be a valid phone number. Please check the format and try again."
    
    if validation_error:
        with st.chat_message("assistant"):
            st.markdown(validation_error)
        st.session_state.messages.append({"role": "assistant", "content": validation_error})
    else:
        # --- Generate AI Response with Key Rotation ---
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
                st.warning("Daily limit reached. Switching to the next API key...")
                st.rerun()
            else:
                error_message = "All available API keys have reached their daily free limit. Please try again tomorrow."
                st.error(error_message)
                
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")

    # --- Automatic Conversation Saving ---
    localS.setItem("chat_history", st.session_state.messages)

# --- 8. Final Submission & Summary Section ---
if st.session_state.messages and "This concludes our interview" in st.session_state.messages[-1]["content"]:
    st.write("---")
    
    st.subheader("Finalize and Submit Report")
    st.write("The interview is complete. Click the button below to save the full report to our secure database.")
    
    if st.button("Submit Full Report"):
        try:
            with st.spinner("Analyzing conversation and preparing report..."):
                full_transcript = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
                
                all_keys_needed = ["name", "age", "phoneNumber", "sexualOrientation", "genderIdentity", "consentToStore", "consentToUse", "dateOfIncident", "typeOfViolation", "charges", "perpetrators", "caseDescription", "nameOfReferrer", "phoneOfReferrer", "emailOfReferrer", "supportNeeded", "supportBudget", "reportingForSelf"]
                json_prompt = f"""Analyze the following transcript and extract information for these keys: {', '.join(all_keys_needed)}. For 'reportingForSelf', return True if they are reporting for themself, and False otherwise. Format as a clean JSON object. Transcript: {full_transcript}"""
                
                final_model = genai.GenerativeModel('gemini-1.5-flash')
                final_response = final_model.generate_content(json_prompt)
                clean_json_text = final_response.text.strip().replace("```json", "").replace("```", "")
                extracted_data = json.loads(clean_json_text)
                
                final_report_data = {}
                for key, value in extracted_data.items():
                    if key in JOTFORM_FIELD_MAPPING and value:
                        if isinstance(value, list):
                            final_report_data[JOTFORM_FIELD_MAPPING[key]] = ", ".join(map(str, value))
                        else:
                            final_report_data[JOTFORM_FIELD_MAPPING[key]] = str(value)

                final_report_data[JOTFORM_FIELD_MAPPING["dateAndTime"]] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                final_report_data[JOTFORM_FIELD_MAPPING["caseAssignedTo"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["referralReceivedBy"]] = "Alex Ssemambo"
                
                summary_prompt = f"You are a skilled human rights report writer... Transcript: {full_transcript}"
                summary_model = genai.GenerativeModel('gemini-1.5-flash')
                summary_response = summary_model.generate_content(summary_prompt)
                narrative_story = summary_response.text
                final_report_data[JOTFORM_FIELD_MAPPING["caseDescription"]] = narrative_story

            with st.spinner("Submitting to Jotform..."):
                submission_payload = {f'submission[{key}]': value for key, value in final_report_data.items()}
                url = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/submissions?apiKey={JOTFORM_API_KEY}"
                response = requests.post(url, data=submission_payload)

                if response.status_code in [200, 201]:
                    st.success("Success! Your report has been securely submitted.")
                    # --- Post-Submission Experience ---
                    st.subheader("Final Narrative Report")
                    st.markdown(narrative_story)
                    
                    is_reporting_for_self = extracted_data.get("reportingForSelf", True)
                    if not is_reporting_for_self:
                        st.download_button(
                            label="📥 Download Narrative Report",
                            data=narrative_story.encode('utf-8'),
                            file_name="narrative_report.txt",
                            mime="text/plain"
                        )
                else:
                    st.error(f"Submission failed. Status: {response.status_code} - {response.text}")
        
        except Exception as e:
            st.error(f"An error occurred during submission: {e}")
