# app.py
# Main application for the Human Rights Violation Interview Agent

import streamlit as st
import google.generativeai as genai
import requests
import json
import ast
import time
from datetime import datetime

# --- Configuration & Initialization ---

# Set page configuration
st.set_page_config(
    page_title="Human Rights Interview Agent",
    page_icon="🕊️",
    layout="centered"
)

# --- Secret & Credential Loading ---

# Load credentials from Streamlit's secrets manager
try:
    JOTFORM_API_KEY = st.secrets["JOTFORM_API_KEY"]
    JOTFORM_FORM_ID = st.secrets["JOTFORM_FORM_ID"]
    GEMINI_API_KEYS = [key.strip() for key in st.secrets["GEMINI_API_KEYS"].split(',')]
    
    # Use ast.literal_eval for safely parsing the string dictionary
    JOTFORM_FIELD_MAPPING_STR = st.secrets["JOTFORM_FIELD_MAPPING"]
    JOTFORM_FIELD_MAPPING = ast.literal_eval(JOTFORM_FIELD_MAPPING_STR)

except (KeyError, FileNotFoundError) as e:
    st.error(f"🚨 **Critical Error:** A required secret is missing. Please check your Streamlit secrets configuration. Missing key: `{e.args[0]}`")
    st.stop()


# --- System Prompts for AI Personas ---

# Persona 1: The "Interviewer" AI
# This AI conducts the live, empathetic conversation.
interviewer_system_instruction = """
You are a highly skilled, empathetic, and investigative AI assistant from a human rights organization. You are a very good writer and a warm, natural conversationalist. Your primary goal is to make the user feel heard, safe, and comfortable while gently guiding them through a detailed interview. Your ultimate objective is to gather enough rich, detailed information to write a clear and compelling narrative of the user's experience.

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

# Persona 2: The "Documenter" AI
# This AI analyzes the transcript and creates the final structured report.
documenter_system_instruction = """
You are a ruthlessly efficient data processing AI. Your sole purpose is to analyze the provided conversation transcript and extract specific information into a structured format.

**Your Task:**
1.  Read the entire conversation between the 'assistant' (the interviewer) and the 'user' (the respondent).
2.  Generate a single, valid JSON object as your output. **Do not output anything else, not even markdown backticks or the word "json".**
3.  The JSON object must have two top-level keys: "narrative" and "data".

**"narrative" Key:**
* The value must be a string containing a clear, coherent, third-person narrative of the incident.
* Synthesize the details from the entire conversation into a comprehensive story.

**"data" Key:**
* The value must be another JSON object containing the extracted data points.
* Use the following keys EXACTLY.
* If a piece of information is not mentioned in the transcript, use `null` as its value.

**Data Fields to Extract:**
`name`
`age`
`phoneNumber`
`sexualOrientation`
`genderIdentity`
`consentToStore` (must be "Yes" or "No")
`consentToUse` (must be "Yes" or "No")
`dateOfIncident`
`typeOfViolation`
`perpetrators`
`caseDescription` (This is the **same as the 'narrative' you generate** above. Copy the narrative string here.)
`nameOfReferrer`
`supportNeeded`
`supportBudget`
`memberOrganisation`
`charges`
`phoneOfReferrer`
`emailOfReferrer`
"""

# --- State Management ---

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []
if "interview_complete" not in st.session_state:
    st.session_state.interview_complete = False
if "gemini_key_index" not in st.session_state:
    st.session_state.gemini_key_index = 0
if "submission_result" not in st.session_state:
    st.session_state.submission_result = None


# --- Core AI and API Functions ---

def get_gemini_response(prompt_text, is_documenter=False):
    """
    Calls the Gemini API with automatic key rotation on ResourceExhausted errors.

    Args:
        prompt_text (str or list): The prompt or conversation history to send.
        is_documenter (bool): Flag to use the documenter persona.

    Returns:
        str: The text response from the model, or None if all keys fail.
    """
    max_retries = len(GEMINI_API_KEYS)
    for attempt in range(max_retries):
        current_key_index = (st.session_state.gemini_key_index + attempt) % max_retries
        api_key = GEMINI_API_KEYS[current_key_index]
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Construct the prompt based on the persona
            if is_documenter:
                full_prompt = [
                    {'role': 'user', 'parts': [documenter_system_instruction, "\n\n## CONVERSATION TRANSCRIPT ##\n\n" + prompt_text]}
                ]
            else:
                 full_prompt = [
                    {'role': 'user', 'parts': [interviewer_system_instruction]},
                    {'role': 'model', 'parts': ["Hello! I'm here to help. I need to gather some information to document what happened. Your safety and comfort are my top priorities. To begin, could you please tell me your full name?"]}
                ] + prompt_text

            response = model.generate_content(full_prompt)
            
            # Successfully got a response, update the primary key index for next time
            st.session_state.gemini_key_index = current_key_index
            return response.text

        except genai.types.generation_types.StopCandidateException as e:
            st.error("The model stopped generating content. This might be due to the safety policy. Please try rephrasing.")
            return None
        except Exception as e:
            # Specifically check for ResourceExhausted error to rotate key
            if "RESOURCE_EXHAUSTED" in str(e) or "rate limit" in str(e).lower():
                print(f"Key {current_key_index + 1} exhausted. Trying next key.")
                continue # Go to the next iteration of the loop to try the next key
            else:
                st.error(f"An unexpected error occurred with the AI model: {e}")
                return None
    
    # If all keys have been tried and failed
    st.error("🚨 All API keys have reached their usage limits. Please try again later or add new keys.")
    return None

def submit_to_jotform(payload):
    """
    Submits the final data payload to the Jotform API.

    Args:
        payload (dict): The data to submit, with keys matching Jotform field names.

    Returns:
        tuple: (bool, str) indicating success and a message.
    """
    url = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/submissions?apiKey={JOTFORM_API_KEY}"
    
    # Jotform API expects submissions as form-data, not raw JSON
    # Keys should look like 'submission[field_id]'
    formatted_payload = {f"submission[{key}]": value for key, value in payload.items()}
    
    try:
        response = requests.post(url, data=formatted_payload)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        if response.status_code == 200 and response.json().get("responseCode") == 200:
            return (True, "✅ Success! Your report has been securely submitted.")
        else:
            return (False, f"❌ Submission Failed. Server responded with: `{response.text}`")
            
    except requests.exceptions.RequestException as e:
        return (False, f"❌ A network error occurred while submitting the report: {e}")

# --- UI Rendering and Application Flow ---

st.title("🕊️ Human Rights Interview Agent")
st.markdown("This is a safe and confidential space to document your experience. I am an AI assistant designed to listen with empathy and guide you through the process.")
st.markdown("---")

# Initialize chat if it's the first run
if not st.session_state.messages:
    # This is a placeholder for the UI, the actual first message is prepended in the API call
    st.session_state.messages.append(
        {"role": "assistant", "content": "Hello! I'm here to help. I need to gather some information to document what happened. Your safety and comfort are my top priorities. To begin, could you please tell me your full name?"}
    )

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Main conversation loop
if not st.session_state.interview_complete:
    if prompt := st.chat_input("Type your response here..."):
        # Add user message to state and display it
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Construct conversation history for the API call
                history_for_api = [
                    {'role': msg['role'], 'parts': [msg['content']]} 
                    for msg in st.session_state.messages
                ]
                
                response_text = get_gemini_response(history_for_api)
                
                if response_text:
                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})

                    # Check for the completion phrase
                    if "This concludes our interview. The submission buttons are now available below." in response_text:
                        st.session_state.interview_complete = True
                        time.sleep(1) # Brief pause before rerun
                        st.rerun()

# --- Submission Section ---
if st.session_state.interview_complete:
    st.success("The interview part is complete. Please review and submit your report.")
    
    if st.button("Generate & Submit Final Report", type="primary"):
        with st.spinner("Analyzing transcript, generating narrative, and preparing submission..."):
            
            # 1. Create the full transcript string
            transcript = "\n".join([f"{msg['role'].title()}: {msg['content']}" for msg in st.session_state.messages])
            
            # 2. Call the "Documenter" AI
            raw_json_response = get_gemini_response(transcript, is_documenter=True)
            
            if not raw_json_response:
                st.error("Failed to generate the final report from the transcript. Please try again.")
                st.stop()
            
            # 3. Parse the JSON response
            try:
                # Clean up potential markdown backticks
                cleaned_json_str = raw_json_response.strip().replace("```json", "").replace("```", "")
                report_data = json.loads(cleaned_json_str)
                narrative = report_data.get("narrative", "Narrative could not be generated.")
                extracted_data = report_data.get("data", {})
            except json.JSONDecodeError:
                st.error("Error: The AI's analysis did not return a valid format. Cannot proceed with submission.")
                st.expander("Show Raw AI Output for Debugging").code(raw_json_response)
                st.stop()

            # 4. Construct the Jotform payload
            submission_payload = {}
            # Map extracted data to Jotform field IDs
            for internal_key, value in extracted_data.items():
                if internal_key in JOTFORM_FIELD_MAPPING:
                    jotform_key = JOTFORM_FIELD_MAPPING[internal_key]
                    submission_payload[jotform_key] = value

            # Add automated fields
            submission_payload[JOTFORM_FIELD_MAPPING["dateAnd"]] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            submission_payload[JOTFORM_FIELD_MAPPING["referralReceived"]] = "Alex Ssemambo"
            submission_payload[JOTFORM_FIELD_MAPPING["caseAssigned"]] = "Alex Ssemambo"
            # Note: CaseNo is left blank as per requirements

            # 5. Submit to Jotform
            success, message = submit_to_jotform(submission_payload)

            st.session_state.submission_result = {"success": success, "message": message}

            # 6. Display the generated report for user verification
            with st.expander("View Your Generated Report", expanded=True):
                st.subheader("Incident Narrative")
                st.write(narrative)
                st.subheader("Extracted Data")
                st.json(extracted_data)

    # Display submission status outside the button press logic to persist after rerun
    if st.session_state.submission_result:
        if st.session_state.submission_result["success"]:
            st.success(st.session_state.submission_result["message"])
            st.info(
                "**IMPORTANT: For any evidence such as photos, videos, or documents, please send them directly to:**\n\n"
                "- Email: `uprotectme@protonmail.com`\n"
                "- WhatsApp: `+256764508050`"
            )
        else:
            st.error(st.session_state.submission_result["message"])
