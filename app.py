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
system_instruction = """You are a highly skilled, empathetic, and investigative AI assistant. You are a very good writer and a warm, natural conversationalist. Your primary goal is to make the user feel heard, safe, and comfortable while gently guiding them through a detailed interview. Your ultimate objective is to gather enough rich, detailed information to be able to write a clear and compelling narrative of the user's experience.

**Core Persona & Behavior:**
1.  **Be Human-Like & Conversational:** Your language must be natural and flowing, not robotic. Use smooth transitions between topics. For example, instead of just asking the next question, say things like, "Thank you for sharing that with me. If it's okay, the next thing I'd like to ask about is..." or "That gives me a clearer picture, thank you. Let's move on to..."
2.  **Be Intuitive & Adaptive:** Pay close attention to the user's responses. If their answers are short and simple, keep your questions concise. If they seem unfamiliar with complex English, you must simplify your language. Adapt your style to match theirs to make them feel comfortable.
3.  **Be Persistent but Respectful:** Your goal is to complete the report. If a user doesn't answer a question, gently ask if they are comfortable sharing that information. If they say no, you may move on from **optional** questions. For **required** questions, you must gently explain why it's needed and try asking in a different way.
4.  **Handle Limitations:** If the user asks a question you cannot answer, politely state your limitations and provide the follow-up contact details: email **uprotectme@protonmail.com** or call/WhatsApp **+256764508050**.

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

# --- 4. Initialize Chat History and Key Index ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Hello! I am a confidential AI assistant here to provide a safe space for you to share your experiences. This conversation is private. I will be asking for the essential information needed to complete your report. To begin, what is your full, official name?"
    })
if "key_index" not in st.session_state:
    st.session_state.key_index = 0

# --- 5. Display Chat History ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 6. The New, Stable Chat Logic ---
if prompt := st.chat_input("Your response..."):
    # Add user message to history and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Prepare the conversation history for the API
    api_history = []
    for msg in st.session_state.messages:
        api_history.append({
            "role": "user" if msg["role"] == "user" else "model",
            "parts": [{"text": msg["content"]}]
        })

    # Generate AI response with key rotation
    try:
        current_key = GEMINI_API_KEYS[st.session_state.key_index]
        genai.configure(api_key=current_key)
        
        model = genai.GenerativeModel(model_name='gemini-1.5-flash')
        
        # Use the simpler, more stable generate_content method with the full history
        response = model.generate_content(
            api_history,
            generation_config={"temperature": 0.75}, # Increase creativity
            system_instruction=system_instruction
        )
        ai_response = response.text

        with st.chat_message("assistant"):
            st.markdown(ai_response)
        st.session_state.messages.append({"role": "assistant", "content": ai_response})
        st.rerun()

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
        st.rerun()

# --- 7. Final Submission & Summary Section ---
if st.session_state.messages and "This concludes our interview" in st.session_state.messages[-1]["content"]:
    st.write("---")
    
    st.subheader("Finalize and Submit Report")
    st.write("The interview is complete. Click the button below to save the full report to our secure database.")
    
    if st.button("Submit Full Report"):
        try:
            with st.spinner("Analyzing conversation and preparing report..."):
                full_transcript = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
                
                all_keys_needed = ["name", "age", "phoneNumber", "sexualOrientation", "genderIdentity", "consentToStore", "consentToUse", "dateOfIncident", "typeOfViolation", "charges", "perpetrators", "caseDescription", "nameOfReferrer", "phoneOfReferrer", "emailOfReferrer", "supportNeeded", "supportBudget"]
                json_prompt = f"""Analyze the following transcript and extract information for these keys: {', '.join(all_keys_needed)}. Format as a clean JSON object. Transcript: {full_transcript}"""
                
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
                final_report_data[JOTFORM_FIELD_MAPPING["caseDescription"]] = summary_response.text

            with st.spinner("Submitting to Jotform..."):
                submission_payload = {f'submission[{key}]': value for key, value in final_report_data.items()}
                url = f"https.api.jotform.com/form/{JOTFORM_FORM_ID}/submissions?apiKey={JOTFORM_API_KEY}"
                
                response = requests.post(url, data=submission_payload)

                if response.status_code in [200, 201]:
                    st.success("Success! Your report has been securely submitted.")
                else:
                    st.error(f"Submission failed. Status: {response.status_code} - {response.text}")
        
        except Exception as e:
            st.error(f"An error occurred during submission: {e}")
