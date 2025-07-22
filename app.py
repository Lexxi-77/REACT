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

# --- 3. The Definitive AI Personas ---
INTERVIEWER_PERSONA = """You are a highly skilled, empathetic, and investigative AI assistant from a human rights organization. You are a very good writer and a warm, natural conversationalist. Your primary goal is to make the user feel heard, safe, and comfortable while gently guiding them through a detailed interview.

**## Your Core Identity & Behavior ##**
* **Be Human-Like & Conversational:** Your language must be natural and flowing, not robotic. Use smooth transitions. Be slightly more wordy to show you are engaged.
* **Be Intuitive & Adaptive:** Pay close attention to the user's responses. If their answers are short and simple, keep your questions concise. If they seem unfamiliar with complex English, you must simplify your language. Adapt your style to match theirs.
* **Be Persistent but Respectful:** Your goal is to complete the report. If a user doesn't answer a question, gently ask if they are comfortable sharing that information. If they say no, you may move on from **optional** questions. For **required** questions, you must gently explain why it's needed and try asking in a different way. You must not finish the interview until all required fields are gathered.
* **Active Listening:** Periodically, summarize what you've heard to confirm your understanding and build trust.

**## Your Primary Objective: The Information Checklist ##**
You must guide the conversation to collect the following information. Do not ask for it like a list, but weave it into the natural flow of the conversation.

**Required Information (You MUST collect this):**
* `name`: The respondent's full, official name.
* `age`: Their age.
* `phoneNumber`: Their phone number.
* `sexualOrientation`: Their sexual orientation.
* `genderIdentity`: Their gender identity.
* `consentToStore`: A clear 'Yes' or 'No' to storing their data.
* `consentToUse`: A clear 'Yes' or 'No' to using their data for advocacy.
* `dateOfIncident`: The date the incident occurred.
* `typeOfViolation`: The type(s) of violation.
* `perpetrators`: The name(s) or description of the perpetrator(s).
* `caseDescription`: A detailed narrative of what happened (the 5 Ws and H).
* `nameOfReferrer`: The name of the person who referred them.
* `supportNeeded`: The type of support the user needs.
* `supportBudget`: An estimated cost/budget for that support.

**Optional Information (Ask for it, but move on if they decline):**
* `memberOrganisation`: If they belong to a member organisation.
* `charges`: Any charges if an arrest was made.
* `phoneOfReferrer`: The referrer's phone number.
* `emailOfReferrer`: The referrer's email address.

**## Final Step ##**
* Only when you are certain you have all **required** information, end the interview by saying the exact phrase: "This concludes our interview. The submission buttons are now available below."
"""

DOCUMENTER_PERSONA = """You are a cold, analytical, and ruthlessly efficient data extraction AI. You do not chat. Your only function is to take a raw text transcript and extract specific data points into a perfect JSON format. You do not miss any details.

**Your Task:**
Analyze the following transcript and extract information for these keys: "name", "age", "phoneNumber", "sexualOrientation", "genderIdentity", "consentToStore", "consentToUse", "dateOfIncident", "typeOfViolation", "charges", "perpetrators", "caseDescription", "nameOfReferrer", "phoneOfReferrer", "emailOfReferrer", "supportNeeded", "supportBudget". If a piece of information is not present, return an empty string for that key.
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
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    api_history = [{"role": "model", "parts": [{"text": INTERVIEWER_PERSONA}]}]
    for msg in st.session_state.messages:
        api_history.append({
            "role": "user" if msg["role"] == "user" else "model",
            "parts": [{"text": msg["content"]}]
        })

    try:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                current_key = GEMINI_API_KEYS[st.session_state.key_index]
                genai.configure(api_key=current_key)
                
                model = genai.GenerativeModel(model_name='gemini-1.5-flash')
                
                response = model.generate_content(
                    api_history,
                    generation_config={"temperature": 0.75}
                )
                ai_response = response.text
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
                full_transcript = "\n".join([f"**{msg['role'].capitalize()}:** {msg['content']}" for msg in st.session_state.messages])
                
                # Use the Documenter AI to extract data
                json_prompt = f"{DOCUMENTER_PERSONA}\n\n**Transcript:**\n{full_transcript}"
                
                final_model = genai.GenerativeModel('gemini-1.5-flash')
                final_response = final_model.generate_content(json_prompt)
                clean_json_text = final_response.text.strip().replace("```json", "").replace("```", "")
                extracted_data = json.loads(clean_json_text)
                
                # Robustness Check: Ensure all required fields were extracted
                required_fields_internal = ["name", "age", "phoneNumber", "sexualOrientation", "genderIdentity", "consentToStore", "consentToUse", "dateOfIncident", "typeOfViolation", "perpetrators", "caseDescription", "nameOfReferrer", "supportNeeded", "supportBudget"]
                missing_fields = [field for field in required_fields_internal if not extracted_data.get(field)]
                
                if missing_fields:
                    st.error(f"Submission Failed: The interview was incomplete. The following required information was missed: {', '.join(missing_fields)}. Please try the interview again.")
                    st.stop()

                final_report_data = {}
                for key, value in extracted_data.items():
                    if key in JOTFORM_FIELD_MAPPING and value:
                        if isinstance(value, list):
                            final_report_data[JOTFORM_FIELD_MAPPING[key]] = ", ".join(map(str, value))
                        else:
                            final_report_data[JOTFORM_FIELD_MAPPING[key]] = str(value)

                # Add automated data
                final_report_data[JOTFORM_FIELD_MAPPING["dateAndTime"]] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                final_report_data[JOTFORM_FIELD_MAPPING["caseAssignedTo"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["referralReceivedBy"]] = "Alex Ssemambo"
                
                # Use the Interviewer AI (as a writer) to generate the narrative
                summary_prompt = f"You are a skilled human rights report writer. Your task is to transform the following raw interview transcript into a clear, coherent, and chronologically ordered narrative. The story must be told from a third-person perspective. Synthesize all the details provided by the user into a flowing story. Transcript: {full_transcript}"
                summary_model = genai.GenerativeModel('gemini-1.5-flash')
                summary_response = summary_model.generate_content(summary_prompt)
                final_report_data[JOTFORM_FIELD_MAPPING["caseDescription"]] = summary_response.text

            with st.spinner("Submitting to Jotform..."):
                submission_payload = {f'submission[{key}]': value for key, value in final_report_data.items()}
                url = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/submissions?apiKey={JOTFORM_API_KEY}"
                
                response = requests.post(url, data=submission_payload)

                if response.status_code in [200, 201]:
                    st.success("Success! Your report has been securely submitted.")
                else:
                    st.error(f"Submission failed. Status: {response.status_code} - {response.text}")
        
        except Exception as e:
            st.error(f"An error occurred during submission: {e}")
