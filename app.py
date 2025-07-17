import streamlit as st
import pandas as pd
import tempfile
import os
import zipfile
import re
import logging
from utils.db import get_engine
from utils.ai import get_openai_client
import base64
from st_audiorec import st_audiorec
import datetime

# --- Q&A Text Validation ---
def is_valid_qa_text(text):
    import re
    # Accepts either Q1:/A1: or Q:/A: style
    has_q = re.search(r"^Q(\d*)\:", text, re.MULTILINE)
    has_a = re.search(r"^A(\d*)\:", text, re.MULTILINE)
    return bool(has_q and has_a)

# --- Session State Initialization ---
if 'processing' not in st.session_state:
    st.session_state['processing'] = False
if 'transcribed' not in st.session_state:
    st.session_state['transcribed'] = False
if 'submitted' not in st.session_state:
    st.session_state['submitted'] = False
if 'submission_data' not in st.session_state:
    st.session_state['submission_data'] = {}

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- DB and OpenAI Setup ---
try:
    engine = get_engine()
except Exception as e:
    logger.error(f"Database connection failed: {e}")
    st.error("Database connection failed. Please check your credentials and network.")
    st.stop()

try:
    client = get_openai_client()
except Exception as e:
    logger.error(f"OpenAI client setup failed: {e}")
    st.error("OpenAI client setup failed. Please check your API key.")
    st.stop()

# Set Streamlit page metadata for DykScribe with custom logo
st.set_page_config(
    page_title="DykScribe",
    page_icon="📝",
    layout="centered",
    initial_sidebar_state="auto",
    menu_items={
        'Get Help': 'mailto:FJamal@vdrs.com',
        'About': 'DykScribe: A streamlined QA and information capture form for Van Dyk Service Techs.'
    }
)
# Show logo above the title for best compatibility
st.image("VDRS Logo.png", width=96)
st.markdown("<div style='height: 0.5em'></div>", unsafe_allow_html=True)
st.markdown("<span style='font-size:2.2em; font-weight:800; color:#15487d;'>DykScribe 📝</span>", unsafe_allow_html=True)
st.markdown("<div style='font-size:1.1em; color:#666; margin-bottom:1.5em;'>DykScribe is a streamlined QA and information capture form for Van Dyk users. It allows you to <span style='color:#d66638;'>🎤 record</span> or <span style='color:#d66638;'>⬆️ upload</span> audio, transcribe responses, and submit detailed <span style='color:#15487d;'>🏭 equipment</span> and <span style='color:#15487d;'>🧑‍💼 user</span> information for review and analysis.</div>", unsafe_allow_html=True)

# --- Data Fetch Functions ---
def get_users():
    try:
        df = pd.read_sql("SELECT UserName, Role FROM vw_ActivePM_FSE_Users", engine)
        if df.empty:
            st.warning("No users found in the database.")
        return df
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        st.error("Failed to load users from the database.")
        return pd.DataFrame()

def get_manufacturers():
    try:
        df = pd.read_sql("SELECT DISTINCT Manufacturer FROM vw_Manufacturers", engine)
        if df.empty:
            st.warning("No manufacturers found in the database.")
        return df
    except Exception as e:
        logger.error(f"Error fetching manufacturers: {e}")
        st.error("Failed to load manufacturers from the database.")
        return pd.DataFrame()

def get_equipment_types(manufacturer):
    try:
        df = pd.read_sql(
            "SELECT DISTINCT EquipmentType FROM vw_EquipmentTypes WHERE Manufacturer = ?",
            engine, params=[(manufacturer,)]
        )
        if df.empty:
            st.warning("No equipment types found for this manufacturer.")
        return df
    except Exception as e:
        logger.error(f"Error fetching equipment types: {e}")
        st.error("Failed to load equipment types from the database.")
        return pd.DataFrame()

def get_models(manufacturer, equipment_type):
    try:
        df = pd.read_sql(
            "SELECT DISTINCT Model FROM vw_Models WHERE Manufacturer = ? AND EquipmentType = ?",
            engine, params=[(manufacturer, equipment_type)]
        )
        if df.empty:
            st.warning("No models found for this manufacturer and equipment type.")
        return df
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        st.error("Failed to load models from the database.")
        return pd.DataFrame()

def get_spec_options(manufacturer, equipment_type, field):
    try:
        df = pd.read_sql(
            f"SELECT DISTINCT {field} FROM vw_ModelSpecifications WHERE Manufacturer = ? AND EquipmentType = ?",
            engine, params=[(manufacturer, equipment_type)]
        )
        if df.empty:
            st.warning(f"No options found for {field}.")
            return []
        return df[field].dropna().tolist()
    except Exception as e:
        logger.error(f"Error fetching {field} options: {e}")
        st.error(f"Failed to load {field} options from the database.")
        return []

def get_model_specs(manufacturer, equipment_type, model):
    try:
        df = pd.read_sql(
            "SELECT Specifications2, Specifications3 "
            "FROM vw_ModelSpecifications WHERE Manufacturer = ? AND EquipmentType = ? AND Model = ?",
            engine, params=[(manufacturer, equipment_type, model)]
        )
        if df.empty:
            st.warning("No specifications found for this model.")
        return df
    except Exception as e:
        logger.error(f"Error fetching model specs: {e}")
        st.error("Failed to load model specifications from the database.")
        return pd.DataFrame()

# --- Fetch spec labels from SQL ---
import pandas as pd
@st.cache_data
def get_spec_labels(equipment_type):
    query = """
        SELECT Specification2Label, Specification3Label
        FROM vw_EquipmentTypeSpecLabels
        WHERE EquipmentType = ?
    """
    return pd.read_sql(query, engine, params=[(equipment_type,)])

# --- Helper: Format transcript as Q&A using ChatGPT ---
def format_transcript_as_qa(transcript, openai_client):
    prompt = (
        "Format the following transcript as a list of Question and Answer pairs. "
        "If there are no clear questions, try to infer them. Use the format:\n"
        "Q: ...\nA: ...\n\nTranscript:\n"
        f"{transcript}"
    )
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that formats transcripts as Q&A."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1024,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error formatting transcript as Q&A: {e}")
        st.error("Failed to format transcript as Q&A using OpenAI.")
        return ""

# --- Helper: Count Qs and As ---
def count_questions_answers(qa_text):
    questions = len(re.findall(r'^Q:', qa_text, re.MULTILINE))
    answers = len(re.findall(r'^A:', qa_text, re.MULTILINE))
    return questions, answers

# --- Helper: Insert submission into SQL ---
def insert_submission(engine, data, audio_bytes):
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            stmt = text("""
                INSERT INTO QAForms
                (UserName, Role, EntryDateTime, Manufacturer, EquipmentType, Model, Specifications2, Specifications3, Notes, NumQuestions, NumAnswers, PointsAwarded, QAText, Transcript, AudioBlob)
                VALUES (:UserName, :Role, :EntryDateTime, :Manufacturer, :EquipmentType, :Model, :Specifications2, :Specifications3, :Notes, :NumQuestions, :NumAnswers, :PointsAwarded, :QAText, :Transcript, :AudioBlob)
            """)
            conn.execute(stmt, {
                "UserName": data["UserName"],
                "Role": data["Role"],
                "EntryDateTime": data["EntryDateTime"],
                "Manufacturer": data["Manufacturer"],
                "EquipmentType": data["EquipmentType"],
                "Model": data["Model"],
                "Specifications2": data["Specifications2"],
                "Specifications3": data["Specifications3"],
                "Notes": data["Notes"],
                "NumQuestions": data["NumQuestions"],
                "NumAnswers": data["NumAnswers"],
                "PointsAwarded": data["PointsAwarded"],
                "QAText": data["QAText"],
                "Transcript": data["Transcript"],
                "AudioBlob": audio_bytes
            })
        st.success("Submission saved to the database.")
    except Exception as e:
        logger.error(f"Error inserting submission: {e}")
        st.error("Failed to save submission to the database.")

# --- Equipment Type and Manufacturer Selection (Refactored) ---
def get_all_equipment_types():
    try:
        df = pd.read_sql("SELECT DISTINCT EquipmentType FROM vw_EquipmentTypes", engine)
        if df.empty:
            st.warning("No equipment types found in the database.")
        return df
    except Exception as e:
        logger.error(f"Error fetching equipment types: {e}")
        st.error("Failed to load equipment types from the database.")
        return pd.DataFrame()

def get_manufacturers_by_equipment_type(equipment_type):
    try:
        df = pd.read_sql(
            "SELECT DISTINCT Manufacturer FROM vw_EquipmentTypes WHERE EquipmentType = ?",
            engine, params=[(equipment_type,)]
        )
        if df.empty:
            st.warning("No manufacturers found for this equipment type.")
        return df
    except Exception as e:
        logger.error(f"Error fetching manufacturers: {e}")
        st.error("Failed to load manufacturers from the database.")
        return pd.DataFrame()

# --- User Dropdown and Date/Time ---
users_df = get_users()
user_names_sorted = sorted([x for x in users_df["UserName"].unique() if x is not None]) if not users_df.empty else []
user_name = st.selectbox(
    "User Name",
    user_names_sorted
)
st.markdown("<span style='font-size: 0.85em; color: #888;'>Your role will be auto-filled based on your username.</span>", unsafe_allow_html=True)
role = users_df.loc[users_df["UserName"] == user_name, "Role"].values[0] if not users_df.empty and user_name else ""
st.text_input("Role", value=role, disabled=True)
st.markdown("<span style='font-size: 0.85em; color: #888;'>This field is auto-filled and cannot be changed. It is determined by your username.</span>", unsafe_allow_html=True)
entry_datetime = st.text_input(
    "Entry Date & Time",
    value = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    disabled=True
)
st.markdown("<span style='font-size: 0.85em; color: #888;'>This field is auto-filled with the current date and time and cannot be changed.</span>", unsafe_allow_html=True)

# --- Equipment Type First ---
equip_types_df = get_all_equipment_types()
equipment_types_sorted = sorted([x for x in equip_types_df["EquipmentType"].unique() if x is not None]) if not equip_types_df.empty else []
equipment_type = st.selectbox(
    "Select Equipment Type *",
    equipment_types_sorted + ["Other (type to add new)"]
)
if equipment_type == "Other (type to add new)":
    equipment_type = st.text_input("Enter new Equipment Type *")

# Only show the rest of the form if equipment_type is filled
if equipment_type and equipment_type.strip():
    manufacturer = None
    manu_df = get_manufacturers_by_equipment_type(equipment_type)
    manufacturers_sorted = sorted([x for x in manu_df["Manufacturer"].unique() if x is not None]) if not manu_df.empty else []
    manufacturer = st.selectbox(
        "Select Manufacturer",
        manufacturers_sorted + ["Other (type to add new)"]
    )
    if manufacturer == "Other (type to add new)":
        manufacturer = st.text_input("Enter new Manufacturer")
    # --- The rest of the form logic (models, specs, etc.) should use the selected equipment_type and manufacturer as before ---

    # --- Dynamic Spec Labels ---
    spec2_label = "Specifications 2"
    spec3_label = "Specifications 3"
    if equipment_type:
        spec_labels = get_spec_labels(equipment_type)
        if not spec_labels.empty:
            spec2_label = spec_labels["Specification2Label"].iloc[0] or spec2_label
            spec3_label = spec_labels["Specification3Label"].iloc[0] or spec3_label

        st.markdown("**Select the model for the chosen manufacturer and equipment type:**")
        model_df = get_models(manufacturer, equipment_type)
        models_sorted = sorted([x for x in model_df["Model"].unique() if x is not None]) if not model_df.empty else []
        st.markdown("<span style='font-size: 0.85em; color: #888;'>Select the model for the chosen manufacturer and equipment type.</span>", unsafe_allow_html=True)
        model = st.selectbox(
            "Select Model",
            models_sorted
        )

        # --- Dynamic Spec Dropdowns ---
        spec2_options = sorted([x for x in get_spec_options(manufacturer, equipment_type, "Specifications2") if x is not None])
        spec3_options = sorted([x for x in get_spec_options(manufacturer, equipment_type, "Specifications3") if x is not None])

        # Get the default values for the selected model
        spec_df = get_model_specs(manufacturer, equipment_type, model)
        if not spec_df.empty:
            default_spec2 = spec_df.at[0, "Specifications2"]
            default_spec3 = spec_df.at[0, "Specifications3"]
        else:
            default_spec2 = default_spec3 = None

        st.markdown("<span style='font-size: 0.85em; color: #888;'>Select the value for Specifications 2. This option depends on your previous selections.</span>", unsafe_allow_html=True)
        spec2 = st.selectbox(
            spec2_label,
            spec2_options,
            index=spec2_options.index(default_spec2) if default_spec2 in spec2_options and spec2_options else 0
        )
        st.markdown("<span style='font-size: 0.85em; color: #888;'>Select the value for Specifications 3. This option depends on your previous selections.</span>", unsafe_allow_html=True)
        spec3 = st.selectbox(
            spec3_label,
            spec3_options,
            index=spec3_options.index(default_spec3) if default_spec3 in spec3_options and spec3_options else 0
        )
    else:
        spec2 = spec3 = None

    # --- Notes and Audio ---
    st.caption("Enter any additional notes or comments about this submission. This can include context, issues, or anything relevant.")
    notes = st.text_area("Remark or Additional Info")

    # --- Tabs for Transcript/Output and Audio (Mutual Exclusivity, Hide Instead of Disable) ---
    tabs = st.tabs(["Transcript / Output", "Audio"])

    qa_text = st.session_state.get('qa_text', '').strip()
    min_audio_length = 1000
    wav_audio_data = None
    file_bytes = None

    # Determine if audio is present
    with tabs[1]:
        st.subheader("Audio")
        st.markdown("""
        - Record your audio or upload an MP3/WAV file.
        - After processing, the transcript will appear in the Transcript/Output tab.
        """)
        audio_section_visible = not bool(qa_text)
        if not audio_section_visible:
            st.info("Audio input is disabled because you are submitting a typed transcript.")
        else:
            wav_audio_data = st_audiorec()
            if wav_audio_data is not None and len(wav_audio_data) > 1000:
                st.success("Recording complete!")
                st.audio(wav_audio_data, format='audio/wav')
            st.markdown("<span style='font-size: 0.80em; color: #888;'>Or upload MP3 or WAV (max 200MB).</span>", unsafe_allow_html=True)
            audio_file = st.file_uploader(
                "Upload MP3/WAV",
                type=["mp3", "wav"],
                label_visibility="collapsed"
            )
            if audio_file is not None:
                file_bytes = audio_file.read()
                if file_bytes:
                    st.audio(file_bytes, format='audio/wav')

    # Determine if Q&A is present and if audio is present
    valid_audio = (wav_audio_data is not None and len(wav_audio_data) > min_audio_length) or (file_bytes is not None and len(file_bytes) > min_audio_length)
    audio_bytes_to_save = wav_audio_data if (wav_audio_data is not None and len(wav_audio_data) > min_audio_length) else (file_bytes if (file_bytes is not None and len(file_bytes) > min_audio_length) else None)

    with tabs[0]:
        st.subheader("Transcript / Output")
        st.markdown("""
        - You can either type your Q&A in the required format below, or
        - Use the Audio tab to record/upload audio and auto-generate the transcript here.
        - **Format required:**
          - Q1: ...\nA1: ...\nQ2: ...\nA2: ...
          - or Q: ...\nA: ...
        """)
        qa_section_visible = not valid_audio
        if not qa_section_visible:
            st.info("Q&A input is disabled because you are submitting audio.")
        else:
            qa_text = st.text_area("Q&A Transcript (editable)", st.session_state.get('qa_text', ''), height=300, key="qa_text_area")
            st.session_state['qa_text'] = qa_text
            qa_valid = is_valid_qa_text(qa_text.strip()) if qa_text.strip() else False
            if qa_text.strip() and not qa_valid:
                st.warning("Please enter at least one valid Q&A pair in the required format (Q1:/A1: or Q:/A:). Submission will be enabled only when valid.")

    # --- Submit Button and Validation (Mutual Exclusivity) ---
    submit_btn = st.button("Submit")

    # Only one of the two can be submitted at a time
    qa_valid = False  # Default to False
    if 'qa_section_visible' in locals() and qa_section_visible:
        qa_valid = is_valid_qa_text(qa_text.strip()) if qa_text.strip() else False
    can_submit = (qa_valid and not valid_audio) or (valid_audio and not qa_valid)

    if submit_btn:
        if not can_submit:
            st.warning("Please provide either a valid Q&A in the required format or a valid audio file, but not both.")
        else:
            st.session_state['processing'] = True
            try:
                with st.spinner("Processing, please wait..."):
                    with tempfile.TemporaryDirectory() as tmpdir:
                        # Save form inputs
                        inputs = {
                            "UserName": user_name,
                            "Role": role,
                            "EntryDateTime": entry_datetime,
                            "Manufacturer": manufacturer,
                            "EquipmentType": equipment_type,
                            "Model": model,
                            "Specifications2": spec2,
                            "Specifications3": spec3,
                            "Notes": notes,
                            "Timestamp": datetime.datetime.now().isoformat()
                        }
                        inputs_df = pd.DataFrame([inputs])
                        inputs_path = os.path.join(tmpdir, "inputs.csv")
                        inputs_df.to_csv(inputs_path, index=False)

                        audio_path = os.path.join(tmpdir, "audio.wav")
                        audio_bytes = audio_bytes_to_save
                        audio_file_written = False
                        if audio_bytes is not None:
                            with open(audio_path, "wb") as f:
                                f.write(audio_bytes)
                            audio_file_written = True

                        transcript = ""
                        # If audio is present, transcribe as before
                        if valid_audio:
                            try:
                                with st.spinner("Transcribing audio with Whisper..."):
                                    with open(audio_path, "rb") as f:
                                        transcript = client.audio.transcriptions.create(
                                            model="whisper-1",
                                            file=f
                                        ).text
                                st.success("Audio transcribed successfully.")
                            except Exception as e:
                                logger.error(f"Transcription failed: {e}")
                                st.error(f"Transcription failed: {e}")
                                st.session_state['processing'] = False
                                st.stop()
                            # Format transcript as Q&A using OpenAI
                            try:
                                with st.spinner("Formatting transcript as Q&A with ChatGPT..."):
                                    qa_prompt = (
                                        "Extract ONLY the clear, relevant question and answer pairs from the following transcript. "
                                        "Do NOT include any unrelated, filler, or gibberish content. "
                                        "If there are no valid Q&A pairs, return nothing. "
                                        "Format strictly as:\nQ1: ...\nA1: ...\nQ2: ...\nA2: ...\n(no extra text, no explanations, no summaries).\n\nTranscript:\n"
                                        f"{transcript}"
                                    )
                                    gpt_response = client.chat.completions.create(
                                        model="gpt-3.5-turbo",
                                        messages=[{"role": "user", "content": qa_prompt}]
                                    )
                                    qa_text = gpt_response.choices[0].message.content
                                    st.session_state['qa_text'] = qa_text
                            except Exception as e:
                                logger.error(f"OpenAI Q&A formatting failed: {e}")
                                st.error(f"OpenAI Q&A formatting failed: {e}")
                                st.session_state['processing'] = False
                                st.stop()
                        # If Q&A is typed, parse it through OpenAI for formatting
                        elif qa_valid:
                            try:
                                with st.spinner("Formatting your Q&A with ChatGPT..."):
                                    qa_prompt = (
                                        "Format the following as a list of Question and Answer pairs. "
                                        "If there are no clear questions, try to infer them. Use the format:\nQ: ...\nA: ...\n\nText:\n"
                                        f"{qa_text}"
                                    )
                                    gpt_response = client.chat.completions.create(
                                        model="gpt-3.5-turbo",
                                        messages=[{"role": "user", "content": qa_prompt}]
                                    )
                                    qa_text = gpt_response.choices[0].message.content
                                    st.session_state['qa_text'] = qa_text
                            except Exception as e:
                                logger.error(f"OpenAI Q&A formatting failed: {e}")
                                st.error(f"OpenAI Q&A formatting failed: {e}")
                                st.session_state['processing'] = False
                                st.stop()

                        qa_path = os.path.join(tmpdir, "qa_transcript.txt")
                        with open(qa_path, "w", encoding="utf-8") as f:
                            f.write(qa_text)

                        # Count Qs and As, award points
                        import re
                        num_questions = len(re.findall(r"^Q\d*:", qa_text, re.MULTILINE))
                        num_answers = len(re.findall(r"^A\d*:", qa_text, re.MULTILINE))
                        points_awarded = num_questions * 1  # 1 point per question

                        # Store all relevant data in session_state for later submission
                        st.session_state["submission_data"] = {
                            "UserName": user_name,
                            "Role": role,
                            "EntryDateTime": entry_datetime,
                            "Manufacturer": manufacturer,
                            "EquipmentType": equipment_type,
                            "Model": model,
                            "Specifications2": spec2,
                            "Specifications3": spec3,
                            "Notes": notes,
                            "NumQuestions": num_questions,
                            "NumAnswers": num_answers,
                            "PointsAwarded": points_awarded,
                            "QAText": qa_text,
                            "Transcript": transcript
                        }
                        st.session_state["audio_bytes_to_save"] = audio_bytes_to_save
                        st.session_state['transcribed'] = True
                        st.session_state['processing'] = False

                        # --- ZIP creation: only add audio if it exists ---
                        # Remove the ZIP creation and download button code entirely.
                        # Do not create zip_path, do not use zipfile.ZipFile, and do not call st.download_button for the ZIP.
                        # The rest of the submission logic (saving, processing, etc.) remains unchanged.
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                st.error(f"An unexpected error occurred: {e}")
                st.session_state['processing'] = False

    # Show results and buttons if transcribed
    if st.session_state.get('transcribed', False):
        submission_data = st.session_state.get('submission_data', {})
        num_questions = submission_data.get('NumQuestions', 0)
        num_answers = submission_data.get('NumAnswers', 0)
        points_awarded = submission_data.get('PointsAwarded', 0)
        qa_text = submission_data.get('QAText', '')
        transcript = submission_data.get('Transcript', '')
        st.markdown(f"**Questions:** {num_questions}  |  **Answers:** {num_answers}  |  **Points Awarded:** {points_awarded}")
        st.subheader("Transcript")
        st.text_area("Output", transcript, height=200)
        st.subheader("Q&A Extracted")
        st.text_area("Q&A Output", qa_text, height=200)
        # Create ZIP
        # Remove the ZIP creation and download button code entirely.
        # Do not create zip_path, do not use zipfile.ZipFile, and do not call st.download_button for the ZIP.
        # The rest of the submission logic (saving, processing, etc.) remains unchanged.
        # Submit to Database button
        submit_btn = st.button("Submit to Database", disabled=st.session_state.get('processing', False))
        if submit_btn:
            st.session_state['processing'] = True
        if st.session_state.get('processing', False) and not st.session_state.get('submitted', False):
            with st.spinner("Saving submission to the database..."):
                insert_submission(engine, st.session_state["submission_data"], st.session_state["audio_bytes_to_save"])
            st.session_state['submitted'] = True
            st.session_state['processing'] = False
            # Clear form/session state after submission
            st.session_state['transcribed'] = False
            st.session_state['submission_data'] = None
            st.session_state['audio_bytes_to_save'] = None
else:
    st.info("Please provide a valid Q&A in the required format or a valid audio file to enable submission.")

# --- Van Dyk Brand Theme CSS ---
# (Removed all custom CSS to revert to default Streamlit theme)
