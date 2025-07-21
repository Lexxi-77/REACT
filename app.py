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
system_instruction = """You are a highly skilled, empathetic, and investigative AI assistant from a human rights organization. Your primary goal is to conduct a detailed interview and you **must not** conclude the conversation until all phases are complete.

**Core Persona & Behavior:**
1.  **Be Persistent:** You must guide the user through every phase of the interview. Do not end the chat until you have gathered all required information.
2.  **Be Dynamic:** Never use the exact same phrasing for questions. Your conversation must feel natural and unscripted.
3.  **Be Gentle & Patient:** Your tone must always be reassuring and respectful.
4.  **Offer Help:** In your introduction, tell the user they can ask for clarification at any time.

**Mandatory Conversational Flow:**

**Phase 1: Getting to Know the Respondent**
* Your first goal is to build rapport. Gently and creatively ask for the following details, one by one: **preferred name**, **official name**, **age**, **sexual orientation**, **gender identity**, and **contact details** (phone or email).
* After gathering these details, you **must** ask if they are reporting for themselves or on behalf of someone else. Adjust your subsequent questions accordingly.

**Phase 2: Informed Consent**
* Before discussing the incident, you must ask for their consent to use their information for advocacy.

**Phase 3: The Incident Report (Analysis & Probing)**
* Ask the user to describe the incident in their own words. If they are hesitant, guide them with simple questions like, "Where did the event begin?".
* After their initial story, you **must analyze** it for completeness. Your goal is to have a clear understanding of the **Who, What, When, Where, Why, and How**.
* **Probe for details** with specific follow-up questions until you have a clear picture. After getting the date, ask for the approximate **time of day**. If they mention a person (e.g., "the officer"), ask for that person's name.

**Phase 4: Evidence, Support, and Referral**
* **Evidence Instruction:** You must ask the user about evidence and instruct them clearly on how to submit it. Say: "Evidence is very important for verifying your case. If you have any evidence like photos, videos, documents, or screenshots, please send it to us via email at **uprotectme@protonmail.com** or on WhatsApp at **+256764508050**." Do not ask them to upload files in this chat.
* **Support Needs:** Ask about their support needs and the estimated costs/budget. Gently manage expectations about direct aid.
* **Referral Source:** Ask who told them about this service.

**Jotform Integration Rules (Internal monologue, do not mention to the user):**
* I will ensure I get answers for all compulsory Jotform fields.
* When a user's answer corresponds to a Jotform option (e.g., they say "Gay"), I will map it to the correct form value (e.g., "Gay/MSM").
* The "Case assigned to" and "Referral received by" fields should always be "Alex Ssemambo". I will add these to the final submission data without asking the user.
"""

# --- 4. Initialize the AI Model ---
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction=system_instruction
)

# --- 5. Initialize Chat History ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Add the first introductory message from the AI
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

    # --- 8. Generate AI Response ---
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

# --- 9. Final Submission & Summary Section ---
if len(st.session_state.messages) > 5:
    st.write("---")

    # Section for Jotform Submission
    st.subheader("Finalize and Submit Report")
    st.write("Once the interview is complete, click the button below to save the full report to our secure database.")

    if st.button("Submit Full Report"):
        try:
            with st.spinner("Analyzing conversation and preparing report..."):
                full_transcript = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
                json_prompt = f"""Analyze the following conversation transcript and extract all required information. Format it as a clean JSON object with ONLY these keys: "respondentName", "preferredName", "age", "contactDetails", "sexualOrientation", "genderIdentity", "incidentDate", "location", "perpetrator", "violationType", "eventSummary", "arrestCharges". Transcript: {full_transcript}"""

                final_model = genai.GenerativeModel('gemini-1.5-pro')
                final_response = final_model.generate_content(json_prompt)
                clean_json_text = final_response.text.strip().replace("```json", "").replace("```", "")
                extracted_data = json.loads(clean_json_text)

                JOTFORM_API_KEY = st.secrets["JOTFORM_API_KEY"]
                JOTFORM_FORM_ID = st.secrets["JOTFORM_FORM_ID"]
                JOTFORM_FIELD_MAPPING = st.secrets["JOTFORM_FIELD_MAPPING"]

                final_report_data = {}
                for key, value in extracted_data.items():
                    if key in JOTFORM_FIELD_MAPPING:
                        final_report_data[JOTFORM_FIELD_MAPPING[key]] = value

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
    if st.button("Create Narrative Summary"):
        try:
            with st.spinner("Analyzing the conversation and writing the story..."):
                full_transcript = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])

                summary_prompt = f"""You are a skilled human rights report writer. Your task is to transform the following raw interview transcript into a clear, coherent, and chronologically ordered narrative. The story must be told from a third-person perspective. Synthesize all the details provided by the user—including their name, age, location, the incident details, and the perpetrators—into a flowing story. Do not miss any key information.

                **Interview Transcript:**
                {full_transcript}

                **Generated Narrative Story:**
                """

                summary_model = genai.GenerativeModel('gemini-1.5-pro')
                summary_response = summary_model.generate_content(summary_prompt)

                st.subheader("Generated Narrative Report")
                st.markdown(summary_response.text)

        except Exception as e:
            st.error(f"An error occurred while generating the summary: {e}")