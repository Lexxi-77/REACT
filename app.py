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
# (This section is unchanged)
system_instruction = """You are a highly skilled, empathetic, and investigative AI assistant for a human rights organization. Your primary goal is to conduct a detailed interview. You **must not** conclude the conversation until you have asked a question for every single topic in all phases below. Be persistent.

**Mandatory Conversational Flow:**

**Phase 1: Getting to Know the Respondent**
* Gently and creatively ask for: **preferred name**, **official name**, **age**, **sexual orientation**, **gender identity**, and **contact details**.
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
# (This section is unchanged)
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Hello! I am a confidential AI assistant here to provide a safe space for you to share your experiences. This conversation is private. If any of my questions are unclear, please ask for clarification. To begin, what is your full, official name?"
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

# --- 8. SIMPLIFIED Submission Section for DEBUGGING ---
if st.session_state.messages and "This concludes our interview" in st.session_state.messages[-1]["content"]:
    st.write("---")
    st.subheader("Finalize and Submit Report")
    
    if st.button("Submit Full Report"):
        try:
            with st.spinner("Submitting simplified report to Jotform..."):
                # --- We will only send the full transcript to the description field ---
                full_transcript = "\n".join([f"**{msg['role'].capitalize()}:** {msg['content']}" for msg in st.session_state.messages])
                
                # Create a very simple data payload
                final_report_data = {
                    JOTFORM_FIELD_MAPPING["eventSummary"]: full_transcript
                }
                
                submission_payload = {f'submission[{key}]': str(value) for key, value in final_report_data.items()}
                url = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/submissions?apiKey={JOTFORM_API_KEY}"
                
                response = requests.post(url, data=submission_payload)

                if response.status_code in [200, 201]:
                    st.success("Test submission sent! Please check your Jotform now.")
                else:
                    st.error(f"Test submission failed. Status: {response.status_code} - {response.text}")
        
        except Exception as e:
            st.error(f"An error occurred during submission: {e}")
