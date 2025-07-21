import streamlit as st
import google.generativeai as genai
import requests
import json
from google.api_core.exceptions import ResourceExhausted

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
system_instruction = """You are a highly skilled, empathetic, and investigative AI assistant for a human rights organization. Your primary goal is to conduct a detailed interview. You **must not** conclude the conversation until you have asked a question for every single topic in all phases below. Be persistent.

**Mandatory Conversational Flow:**

**Phase 1: Getting to Know the Respondent**
* Your first goal is to build rapport. Gently ask for: **preferred name**, **official name**, **age**, **sexual orientation**, **gender identity**, and **contact details**.
* You must also ask for detailed location, **Tribe/Ethnicity**, **Religion**, and **Occupation**.
* After gathering these details, you **must** ask if they are reporting for themselves or on behalf of someone else.

**Phase 2: Informed Consent**
* You must ask for their consent to use their information for advocacy.

**Phase 3: The Incident Report (Analysis & Probing)**
* Ask the user to describe the incident. If they are hesitant, guide them with simple questions.
* After their initial story, you **must analyze** it for completeness. Your goal is to have a clear understanding of the **Who, What, When (including time of day), Where, Why, and How**.
* You must specifically ask for the **number of perpetrators** and if there were any **witnesses**.
* You must ask if the case was **reported to any authority**, and if so, **where**.

**Phase 4: Evidence, Support, and Categorization**
* **Evidence Instruction:** You **must** instruct the user on how to submit evidence by stating the following: "Evidence is very important for your case. If you have any evidence like photos, videos, or documents, please send it to us via email at **uprotectme@protonmail.com** or on WhatsApp at **+256764508050**."
* **Support Needs & Follow-up:** Ask about support needs and the estimated costs/budget.
* **Case Categorization (Required Field):** You **must** ask the user to categorize their case. To help them, you **must** provide these options: **Legal & Security, Socio-Economic, Health**.
* **Referral Source:** Ask who told them about this service.

**Final Step:**
* To end the interview, you **must** say the exact phrase: "This concludes our interview. The submission buttons are now available below."

**Jotform Integration Rules (Internal monologue):**
* The "Case assigned to" and "Referral received by" fields will be "Alex Ssemambo".
* The "eventSummary" field for Jotform will be the full narrative story I generate.
"""

# --- 4. Initialize Chat History and Key Index ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Hello! I am a confidential AI assistant here to provide a safe space for you to share your experiences. This conversation is private. If any of my questions are unclear, please ask for clarification. To begin, what name would you be most comfortable with me calling you?"
    })
if "key_index" not in st.session_state:
    st.session_state.key_index = 0

# --- 5. Display Chat History ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 6. Handle User Input ---
if prompt := st.chat_input("Your response..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- 7. Generate AI Response with Key Rotation ---
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
            st.session_state.messages.append({"role": "assistant", "content": error_message})
            
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

# --- 8. Final Submission Section with Self-Diagnosis ---
if st.session_state.messages and "This concludes our interview" in st.session_state.messages[-1]["content"]:
    st.write("---")
    st.subheader("Finalize and Submit Report")
    
    if st.button("Submit Full Report"):
        try:
            with st.spinner("Analyzing conversation and preparing report..."):
                full_transcript = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
                
                # --- Define the list of all keys we need, including required ones ---
                all_keys_needed = ["respondentName", "preferredName", "age", "contactDetails", "sexualOrientation", "genderIdentity", "district", "county", "village", "tribe", "religion", "occupation", "disability", "maritalStatus", "children", "dependents", "hivStatus", "onArvs", "incidentDate", "location", "perpetrator", "numberOfPerpetrators", "witnesses", "caseReported", "reportedTo", "violationType", "eventSummary", "arrestCharges", "caseCategory"]
                json_prompt = f"""Analyze the following transcript and extract information for these keys: {', '.join(all_keys_needed)}. Format as a clean JSON object. Transcript: {full_transcript}"""
                
                final_model = genai.GenerativeModel('gemini-1.5-flash')
                final_response = final_model.generate_content(json_prompt)
                clean_json_text = final_response.text.strip().replace("```json", "").replace("```", "")
                extracted_data = json.loads(clean_json_text)
                
                # --- NEW: Self-Diagnosis Step ---
                required_fields_internal = ["caseCategory", "incidentDate", "respondentName", "occupation", "district", "contactDetails", "sexualOrientation", "genderIdentity", "county", "village", "tribe", "religion", "maritalStatus", "hivStatus", "caseReported", "violationType"]
                missing_fields = [field for field in required_fields_internal if field not in extracted_data or not extracted_data[field]]
                
                if missing_fields:
                    st.error(f"Submission Failed: The AI could not extract the following required information from the conversation: {', '.join(missing_fields)}. Please try the interview again and ensure these topics are covered.")
                    st.stop() # Stop the process if required data is missing
                # --- END of Self-Diagnosis ---

                final_report_data = {}
                for key, value in extracted_data.items():
                    if key in JOTFORM_FIELD_MAPPING and value:
                        if isinstance(value, list):
                            final_report_data[JOTFORM_FIELD_MAPPING[key]] = ", ".join(map(str, value))
                        else:
                            final_report_data[JOTFORM_FIELD_MAPPING[key]] = value

                final_report_data[JOTFORM_FIELD_MAPPING["caseAssignedTo"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["referralReceivedBy"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["evidenceNotes"]] = "User was instructed to send evidence to uprotectme@protonmail.com or WhatsApp +256764508050."

            with st.spinner("Submitting to Jotform..."):
                submission_payload = {f'submission[{key}]': str(value) for key, value in final_report_data.items() if value}
                url = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/submissions?apiKey={JOTFORM_API_KEY}"
                
                response = requests.post(url, data=submission_payload)

                if response.status_code in [200, 201]:
                    st.success("Success! Your report has been securely submitted.")
                else:
                    st.error(f"Submission failed. Status: {response.status_code} - {response.text}")
        
        except Exception as e:
            st.error(f"An error occurred during submission: {e}")
