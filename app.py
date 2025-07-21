import streamlit as st
import google.generativeai as genai
import requests
import json
from google.api_core.exceptions import ResourceExhausted
import jotform # <-- NEW: Import the official library

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
# (This section is unchanged)
system_instruction = """You are a highly skilled, empathetic, and investigative AI assistant...""" # Abridged for clarity

# --- 4. Initialize Chat History and Key Index ---
# (This section is unchanged)
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Hello! I am a confidential AI assistant..."
    })
if "key_index" not in st.session_state:
    st.session_state.key_index = 0

# --- 5. Display Chat History ---
# (This section is unchanged)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 6. Handle User Input ---
# (This section is unchanged)
if prompt := st.chat_input("Your response..."):
    # (The logic for the chat conversation remains the same)
    pass # Placeholder for the chat logic

# --- 8. Final Submission Section (Upgraded to use pyjotform) ---
if st.session_state.messages and "This concludes our interview" in st.session_state.messages[-1]["content"]:
    st.write("---")
    st.subheader("Finalize and Submit Report")
    
    if st.button("Submit Full Report"):
        try:
            with st.spinner("Analyzing conversation and preparing report..."):
                full_transcript = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
                
                json_prompt = f"""Analyze the following transcript and extract information for these keys: "respondentName", "preferredName", "age", "contactDetails", "sexualOrientation", "genderIdentity", "district", "county", "village", "tribe", "religion", "occupation", "incidentDate", "location", "perpetrator", "numberOfPerpetrators", "witnesses", "caseReported", "reportedTo", "violationType", "eventSummary", "arrestCharges", "caseCategory". Format as a clean JSON object. Transcript: {full_transcript}"""
                
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
                            final_report_data[JOTFORM_FIELD_MAPPING[key]] = value

                final_report_data[JOTFORM_FIELD_MAPPING["caseAssignedTo"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["referralReceivedBy"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["evidenceNotes"]] = "User was instructed to send evidence to uprotectme@protonmail.com or WhatsApp +256764508050."

            with st.spinner("Submitting report to secure database..."):
                # --- NEW: Using the official pyjotform library ---
                jotform_client = jotform.JotformAPIClient(JOTFORM_API_KEY)
                
                # The library expects a simple dictionary
                submission = final_report_data
                
                # Create the submission
                result = jotform_client.create_form_submission(JOTFORM_FORM_ID, submission)
                
                st.success("Success! Your report has been securely submitted.")
                st.info("DEBUGGING: Jotform Library Response")
                st.json(result)
                # --- END OF NEW SECTION ---

        except Exception as e:
            st.error(f"An error occurred during submission: {e}")
