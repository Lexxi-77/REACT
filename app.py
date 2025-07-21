import streamlit as st
import google.generativeai as genai
import requests
import json

# --- 1. Page & AI Configuration ---
st.set_page_config(page_title="AI Interviewer", page_icon="🤖")
st.title("AI Interviewer 🤖")

# --- 2. Securely Get API Key ---
try:
    GEMINI_API_KEYS = st.secrets["GEMINI_API_KEYS"]
    JOTFORM_API_KEY = st.secrets["JOTFORM_API_KEY"]
    JOTFORM_FORM_ID = st.secrets["JOTFORM_FORM_ID"]
    JOTFORM_FIELD_MAPPING = st.secrets["JOTFORM_FIELD_MAPPING"]
except (KeyError, AttributeError):
    st.error("One or more secrets are missing. Please check your Streamlit Cloud secrets configuration.")
    st.stop()

# --- 3. AI Persona and Instructions (The "Brain") ---
system_instruction = """(This should be the same long, detailed instruction set from our last conversation.)""" # Abridged for clarity

# --- 4. Initialize Chat History and Key Index ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Hello! I am a confidential AI assistant..."
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
    # (This section is the same as the last version)
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
    except Exception as e:
        st.error(f"An error occurred: {e}")


# --- 8. Final Submission Section with DEBUGGING ---
if st.session_state.messages and "This concludes our interview" in st.session_state.messages[-1]["content"]:
    st.write("---")
    st.subheader("Finalize and Submit Report")
    
    if st.button("Submit Full Report"):
        try:
            with st.spinner("Analyzing conversation..."):
                full_transcript = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
                json_prompt = f"""Analyze the following transcript and extract information for these keys: "respondentName", "preferredName", "age", "contactDetails", "sexualOrientation", "genderIdentity", "district", "county", "village", "tribe", "religion", "occupation", "incidentDate", "location", "perpetrator", "numberOfPerpetrators", "witnesses", "caseReported", "reportedTo", "violationType", "eventSummary", "arrestCharges", "caseCategory". Format as a clean JSON object. Transcript: {full_transcript}"""
                
                final_model = genai.GenerativeModel('gemini-1.5-flash')
                final_response = final_model.generate_content(json_prompt)
                clean_json_text = final_response.text.strip().replace("```json", "").replace("```", "")
                extracted_data = json.loads(clean_json_text)
                
                final_report_data = {}
                for key, value in extracted_data.items():
                    if key in JOTFORM_FIELD_MAPPING and value:
                        final_report_data[JOTFORM_FIELD_MAPPING[key]] = value

                final_report_data[JOTFORM_FIELD_MAPPING["caseAssignedTo"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["referralReceivedBy"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["evidenceNotes"]] = "User was instructed to send evidence to uprotectme@protonmail.com or WhatsApp +256764508050."

            with st.spinner("Submitting to Jotform..."):
                submission_payload = {f'submission[{key}]': str(value) for key, value in final_report_data.items() if value}
                url = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/submissions?apiKey={JOTFORM_API_KEY}"
                
                # --- NEW DEBUGGING OUTPUT ---
                st.info("DEBUGGING: Information being sent to Jotform")
                st.write("Submission URL:", url)
                st.json(submission_payload)
                # --- END NEW DEBUGGING ---

                response = requests.post(url, data=submission_payload)

                # --- NEW DEBUGGING OUTPUT ---
                st.info("DEBUGGING: Response received from Jotform")
                st.write("Jotform Status Code:", response.status_code)
                st.text("Jotform Response Body:")
                st.json(response.json())
                # --- END NEW DEBUGGING ---

                if response.status_code in [200, 201]:
                    st.success("Success! Your report has been securely submitted.")
                else:
                    st.error("Submission failed. Please review the debugging information above.")
        
        except Exception as e:
            st.error(f"An error occurred during submission: {e}")
