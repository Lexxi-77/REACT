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
system_instruction = """You are a highly skilled, empathetic, and investigative AI assistant for a human rights organization. Your primary goal is to conduct a detailed interview. You **must not** conclude the conversation until you have asked a question for every single topic in all phases below. Be persistent. If the user tries to end the conversation early, you must gently remind them that a few more questions are needed to complete the report.

**Core Persona & Behavior:**
1.  **Be Persistent but Respectful:** Your goal is to complete the report. If a user doesn't answer a question, gently ask if they are comfortable sharing that information. If they say no, you may move on from **optional** questions. For **required** questions, you must gently explain why it's needed and try asking in a different way.
2.  **Be Dynamic:** Never use the exact same phrasing for questions.
3.  **Handle Limitations:** If the user asks a question you cannot answer, politely state your limitations and provide the follow-up contact details: email **uprotectme@protonmail.com** or call/WhatsApp **+256764508050**.

**Mandatory Conversational Flow & Data Collection Rules:**

**Phase 1: Getting to Know the Respondent**
* **Required Details:** You **must** ask for and get a response for each of the following, one by one: **Official Name**, **Age**, **Contact Details**, **Occupation**, **District/City**, **County/Sub-County**, **Parish/Village**, **Tribe/Ethnicity**, **Religion**, **Marital Status**, **Sexual Orientation**, and **Gender Identity**.
* **Health/Disability (Required):** You **must** ask if they have **any disability** (Yes/No). **If they say Yes, you must ask them to specify the disability.** You **must** also ask if they are **living with HIV** (Yes/No). **If they say Yes, you must ask if they are on ARVs** (Yes/No).
* **Optional Details:** You should also ask for their **preferred name**, **number of children**, and **number of dependents**, but you may move on if they are not comfortable answering.
* **Reporting For:** After gathering these details, you **must** ask if they are reporting for themselves or on behalf of someone else.

**Phase 2: Informed Consent**
* You must ask for their consent to use their information for advocacy.

**Phase 3: The Incident Report**
* **Type of Violation (Required, Multiple Choice):** You **must** ask the user to describe the type of violation they experienced. You **must** present them with this specific list and tell them they can choose more than one: **"Forced evictions", "Family banishment", "Physical violence", "Psychological or emotional violence", "Political or institutional violence", "Cyber harassment", "Denial of HIV services", "Denial of SRHR services", "Denial of employment", "Fired", "Detention or arrest", "Blackmail", or "Other"**.
* **Narrative:** Ask the user to describe the incident in their own words.
* **Analysis & Probing:** After their story, you **must analyze** it for completeness. Your goal is to have a clear understanding of the **Who, What, When (including time of day), Where, Why, and How**.
* **Specifics (Optional):** You should also ask for the **number of perpetrators**, if there were any **witnesses**, and what the **arrest charges** were (if applicable).
* **Reporting (Required):** You must ask if the case was **reported to any authority** (Yes/No), and if so, **where**.

**Phase 4: Final Details**
* **Socio-Economic Vulnerabilities:** You must ask the user if they identify with any of the following situations, presenting them with the list: **Unemployed, Homeless, Sex Worker, Refugee/Asylum Seeker, Internally Displaced Person, Person with Disability, Living with HIV**.
* **Evidence Instruction:** You **must** instruct the user on how to submit evidence via email or WhatsApp.
* **Support Needs:** Ask about their support needs and the estimated costs/budget.
* **Case Categorization (Required):** You **must** ask the user to categorize their case. To help them, you **must** provide these options: **Legal & Security, Socio-Economic, Health**. After they choose, you must ask them to choose a **Sub-category**.
* **Referral Source:** Ask who told them about this service.

**Final Step:**
* Only after every single **required** topic above has been covered, you may end the interview by saying the exact phrase: "This concludes our interview. The submission buttons are now available below."

**Jotform Integration Rules (Internal monologue):**
* The "Case assigned to" and "Referral received by" fields will be "Alex Ssemambo".
* The "eventSummary" field for Jotform will be the full narrative story I generate.
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
        "content": "Hello! I am a confidential AI assistant here to provide a safe space for you to share your experiences. This conversation is private. If any of my questions are unclear, please ask for clarification. To begin, what is your full, official name?"
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
if st.session_state.messages and "This concludes our interview" in st.session_state.messages[-1]["content"]:
    st.write("---")
    
    st.subheader("Finalize and Submit Report")
    st.write("The interview is complete. Click the button below to save the full report to our secure database.")
    
    if st.button("Submit Full Report"):
        try:
            with st.spinner("Analyzing conversation and preparing report..."):
                full_transcript = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
                
                # Full list of keys for the final JSON extraction, including all new fields
                all_keys_needed = ["respondentName", "preferredName", "age", "contactDetails", "sexualOrientation", "genderIdentity", "district", "county", "village", "tribe", "religion", "occupation", "disability", "disabilityDetails", "maritalStatus", "children", "dependents", "hivStatus", "onArvs", "incidentDate", "location", "perpetrator", "numberOfPerpetrators", "witnesses", "caseReported", "reportedTo", "violationType", "eventSummary", "arrestCharges", "caseCategory", "caseSubCategory", "socioEconomicVulnerabilities"]
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

                final_report_data[JOTFORM_FIELD_MAPPING["caseAssignedTo"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["referralReceivedBy"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["evidenceNotes"]] = "User was instructed to send evidence to uprotectme@protonmail.com or WhatsApp +256764508050."

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
            
