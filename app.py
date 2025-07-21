import streamlit as st
import google.generativeai as genai
import requests
import json

# --- 1. Page & AI Configuration ---
st.set_page_config(page_title="AI Interviewer", page_icon="🤖")
st.title("AI Interviewer 🤖")

# --- 2. Securely Get API Key ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except (KeyError, AttributeError):
    st.error("API Key not found. Please add it to your Streamlit Cloud secrets.")
    st.stop()

# --- 3. AI Persona and Instructions (The "Brain") ---
system_instruction = """You are a highly skilled, empathetic, and investigative AI assistant for a human rights organization. Your primary goal is to conduct a detailed interview and you **must not** conclude the conversation until all phases are complete. Your ultimate objective is to gather enough rich, detailed information to be able to write a clear and compelling narrative of the user's experience.

**Core Persona & Behavior:**
1.  **Be Persistent:** You must guide the user through every phase of the interview. Do not end the chat until you have gathered all required information.
2.  **Be Dynamic:** Never use the exact same phrasing for questions.
3.  **Handle Limitations:** If the user asks a question you cannot answer or a request you cannot fulfill, you must politely state your limitations and provide the follow-up contact details by saying: "As an AI, I have some limitations and cannot help with that. For further assistance, please email **uprotectme@protonmail.com** or call/WhatsApp **+256764508050**."

**Mandatory Conversational Flow:**

**Phase 1: Getting to Know the Respondent**
* Gently and creatively ask for: **preferred name**, **official name**, **age**, **sexual orientation**, **gender identity**, and **contact details**.
* You must also ask for detailed location, **Tribe/Ethnicity**, **Religion**, and **Occupation**.
* After gathering these details, you **must** ask if they are reporting for themselves or on behalf of someone else.

**Phase 2: Informed Consent**
* You must ask for their consent to use their information for advocacy.

**Phase 3: The Incident Report (Analysis & Probing)**
* Ask the user to describe the incident. If they are hesitant, guide them with simple questions.
* After their initial story, you **must analyze** it for completeness and "mirror" key points back for confirmation. Your goal is to have a clear understanding of the **Who, What, When (including time of day), Where, Why, and How**.
* You must specifically ask for the **number of perpetrators** and if there were any **witnesses**.
* You must ask if the case was **reported to any authority**, and if so, **where**.

**Phase 4: Evidence, Support, and Categorization**
* **Evidence Instruction:** You **must** instruct the user on how to submit evidence by stating the following: "Evidence is very important for your case. If you have any evidence like photos, videos, or documents, please send it to us via email at **uprotectme@protonmail.com** or on WhatsApp at **+256764508050**."
* **Support Needs & Follow-up:** Ask about support needs. Then, inform them about the follow-up contacts again.
* **Case Categorization (Required Field):** You **must** ask the user to categorize their case. Guide them by presenting these options: **Legal & Security, Socio-Economic, Health**.
* **Referral Source:** Ask who told them about this service.

**Final Step:**
* To end the interview, you **must** say the exact phrase: "This concludes our interview. The submission buttons are now available below."

**Jotform Integration Rules (Internal monologue):**
* The "Case assigned to" and "Referral received by" fields will be "Alex Ssemambo".
* The "eventSummary" field for Jotform will be the full narrative story I generate.
"""

# --- 4. Initialize the AI Model ---
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction=system_instruction
)

# --- 5. Initialize Chat History ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Hello! I am a confidential AI assistant here to provide a safe space for you to share your experiences. This conversation is private. If any of my questions are unclear, please ask for clarification. To begin, what name would you be most comfortable with me calling you?"
    })

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
        chat_session = model.start_chat(
            history=[
                {"role": "user" if msg["role"] == "user" else "model", "parts": [msg["content"]]}
                for msg in st.session_state.messages
            ]
        )
        response = chat_session.send_message(prompt)
        ai_response = response.text

        with st.chat_message("assistant"):
            st.markdown(ai_response)
        st.session_state.messages.append({"role": "assistant", "content": ai_response})

    except Exception as e:
        st.error(f"An error occurred: {e}")

# --- 8. Final Submission & Summary Section ---
# Only show the buttons if the AI has concluded the interview.
if st.session_state.messages and "This concludes our interview" in st.session_state.messages[-1]["content"]:
    st.write("---")
    
    st.subheader("Finalize and Submit Report")
    st.write("The interview is complete. Click the button below to save the full report to our secure database.")
    
    if st.button("Submit Full Report"):
        try:
            with st.spinner("Analyzing conversation and preparing report..."):
                full_transcript = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
                
                # --- Generate the Narrative Story First ---
                summary_prompt = f"You are a skilled human rights report writer. Your task is to transform the following raw interview transcript into a clear, coherent, and chronologically ordered narrative. The story must be told from a third-person perspective. Synthesize all the details provided by the user into a flowing story. Transcript: {full_transcript}"
                summary_model = genai.GenerativeModel('gemini-1.5-flash') # <-- CHANGED TO FLASH
                summary_response = summary_model.generate_content(summary_prompt)
                narrative_story = summary_response.text

                # --- Extract Other Data for Jotform ---
                json_prompt = f"""Analyze the following conversation transcript and extract all required information. Format it as a clean JSON object with ONLY these keys: "respondentName", "preferredName", "age", "contactDetails", "sexualOrientation", "genderIdentity", "district", "county", "village", "tribe", "religion", "occupation", "incidentDate", "location", "perpetrator", "numberOfPerpetrators", "witnesses", "caseReported", "reportedTo", "violationType", "eventSummary", "arrestCharges", "caseCategory". Transcript: {full_transcript}"""
                final_model = genai.GenerativeModel('gemini-1.5-flash') # <-- CHANGED TO FLASH
                final_response = final_model.generate_content(json_prompt)
                clean_json_text = final_response.text.strip().replace("```json", "").replace("```", "")
                extracted_data = json.loads(clean_json_text)

                # --- Prepare data for Jotform ---
                JOTFORM_API_KEY = st.secrets["JOTFORM_API_KEY"]
                JOTFORM_FORM_ID = st.secrets["JOTFORM_FORM_ID"]
                JOTFORM_FIELD_MAPPING = st.secrets["JOTFORM_FIELD_MAPPING"]

                final_report_data = {}
                for key, value in extracted_data.items():
                    if key in JOTFORM_FIELD_MAPPING and value:
                        final_report_data[JOTFORM_FIELD_MAPPING[key]] = value

                # --- Add the Narrative Story and Fixed Data ---
                final_report_data[JOTFORM_FIELD_MAPPING["eventSummary"]] = narrative_story
                final_report_data[JOTFORM_FIELD_MAPPING["caseAssignedTo"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["referralReceivedBy"]] = "Alex Ssemambo"
                final_report_data[JOTFORM_FIELD_MAPPING["evidenceNotes"]] = "User was instructed to send evidence to uprotectme@protonmail.com or WhatsApp +256764508050."

            with st.spinner("Submitting report to secure database..."):
                submission_payload = {f'submission[{key}]': value for key, value in final_report_data.items()}
                url = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/submissions?apiKey={JOTFORM_API_KEY}"
                response = requests.post(url, data=submission_payload)

                if response.status_code in [200, 201]:
                    st.success("Success! Your report has been securely submitted.")
                else:
                    st.error(f"Submission failed. Status: {response.status_code} - {response.text}")
        
        except Exception as e:
            st.error(f"An error occurred during submission: {e}")

    # Section for Narrative Summary
    st.subheader("Generate Narrative Story")
    st.write("You can also generate a narrative summary of the report for advocacy purposes.")
    if st.button("Create Narrative Story"):
        try:
            with st.spinner("Analyzing the conversation and writing the story..."):
                full_transcript = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
                summary_prompt = f"You are a skilled human rights report writer... Transcript: {full_transcript}"
                summary_model = genai.GenerativeModel('gemini-1.5-flash') # <-- CHANGED TO FLASH
                summary_response = summary_model.generate_content(summary_prompt)
                
                st.subheader("Generated Narrative Report")
                st.markdown(summary_response.text)

        except Exception as e:
            st.error(f"An error occurred while generating the summary: {e}")
