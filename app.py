import streamlit as st
import pandas as pd
from st_audiorec import st_audiorec
import tempfile
import os
import zipfile
from datetime import datetime
import re
import logging
from utils.db import get_engine
from utils.ai import get_openai_client

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
    value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    disabled=True
)
st.markdown("<span style='font-size: 0.85em; color: #888;'>This field is auto-filled with the current date and time and cannot be changed.</span>", unsafe_allow_html=True)

# --- Dynamic Dropdowns ---
st.markdown("**Select the manufacturer of the equipment:**")
manu_df = get_manufacturers()
manufacturers_sorted = sorted([x for x in manu_df["Manufacturer"].unique() if x is not None]) if not manu_df.empty else []
st.markdown("<span style='font-size: 0.85em; color: #888;'>Choose the manufacturer of the equipment you are working with.</span>", unsafe_allow_html=True)
manufacturer = st.selectbox(
    "Select Manufacturer",
    manufacturers_sorted
)

equipment_type = model = None
spec_df = pd.DataFrame()

if manufacturer:
    st.markdown("**Select the equipment type for the chosen manufacturer:**")
    equip_df = get_equipment_types(manufacturer)
    equipment_types_sorted = sorted([x for x in equip_df["EquipmentType"].unique() if x is not None]) if not equip_df.empty else []
    st.markdown("<span style='font-size: 0.85em; color: #888;'>Select the type of equipment for the chosen manufacturer.</span>", unsafe_allow_html=True)
    equipment_type = st.selectbox(
        "Select Equipment Type",
        equipment_types_sorted
    )

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
else:
    equipment_type = model = spec2 = spec3 = None

# --- Notes and Audio ---
st.caption("Enter any additional notes or comments about this submission. This can include context, issues, or anything relevant.")
notes = st.text_area("Remark or Additional Info")

# --- Unified Audio Block (Fully Grouped) ---
with st.container():
    st.markdown("""
    <div style='display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0.5em 0 0 0;'>
        <h6 style='margin-bottom: 0.3em; text-align: center; font-weight: 600; font-size: 1.05em;'>Audio Response</h6>
        <p style='font-size: 0.88em; color: #aaa; text-align: center; margin-bottom: 0.7em;'>Click the mic to record, or upload a file below. Uploaded file takes priority.</p>
        <div style='width: 100%; display: flex; flex-direction: column; align-items: center;'>
    """, unsafe_allow_html=True)

    # Minimal caption
    audio_bytes = st_audiorec()
    st.markdown("<span style='font-size: 0.80em; color: #888;'>Upload MP3 or WAV (max 200MB).</span>", unsafe_allow_html=True)
    audio_file = st.file_uploader(
        "Upload MP3/WAV",
        type=["mp3", "wav"],
        label_visibility="collapsed"
    )
    # Only show one audio player: uploaded file takes priority, else recorded audio
    audio_to_play = None
    if audio_file is not None:
        file_bytes = audio_file.read()
        if file_bytes:
            audio_to_play = file_bytes
    elif audio_bytes is not None:
        audio_to_play = audio_bytes
    if audio_to_play is not None:
        st.audio(audio_to_play, format="audio/wav")

    st.markdown("<div style='margin: 0.3em 0; text-align: center; color: #888; font-size: 0.85em;'>or</div>", unsafe_allow_html=True)

    st.markdown("""
        </div>
    </div>
    <style>
    section[data-testid="stFileUploader"] {
        margin-left: auto !important;
        margin-right: auto !important;
        display: flex;
        flex-direction: column;
        align-items: center;
        background: none !important;
        box-shadow: none !important;
        border: none !important;
        padding: 0 !important;
        max-width: 320px !important;
    }
    section[data-testid="stAudio"] {
        margin-left: auto !important;
        margin-right: auto !important;
        display: flex;
        justify-content: center;
        background: none !important;
        box-shadow: none !important;
        border: none !important;
        padding: 0 !important;
        max-width: 320px !important;
    }
    /* Make st_audiorec buttons smaller */
    button, .stButton > button {
        font-size: 0.92em !important;
        padding: 0.25em 0.8em !important;
        min-width: 70px !important;
        min-height: 28px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Custom Loading Video Path ---
# loading_video_path = "Loading_Symbol_Video_Generated.mp4"  # No longer needed

# --- Grey Out UI if Processing (No Stop) ---
if 'processing' not in st.session_state:
    st.session_state['processing'] = False
if st.session_state.get('processing', False):
    st.markdown('''
        <div id="greyout-overlay" style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.4); z-index: 9998;"></div>
        <style>body { overflow: hidden !important; }</style>
    ''', unsafe_allow_html=True)

# --- Submit and Save ---
audio_ready = (audio_bytes is not None) or (audio_file is not None)

if audio_ready:
    transcribe_btn = st.button(
        "Transcribe and Calculate Points",
        disabled=st.session_state['processing']
    )
    if transcribe_btn:
        st.session_state['processing'] = True
        # st.experimental_rerun()  # REMOVED

    if st.session_state['processing'] and not st.session_state.get('transcribed', False):
        # Only run processing if not already done
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
                    "Timestamp": datetime.now().isoformat()
                }
                inputs_df = pd.DataFrame([inputs])
                inputs_path = os.path.join(tmpdir, "inputs.csv")
                inputs_df.to_csv(inputs_path, index=False)

                audio_path = None
                audio_bytes_to_save = None
                if audio_bytes is not None:
                    audio_path = os.path.join(tmpdir, "audio.wav")
                    with open(audio_path, "wb") as f:
                        f.write(audio_bytes)
                    audio_bytes_to_save = audio_bytes
                elif audio_file:
                    audio_path = os.path.join(tmpdir, audio_file.name)
                    file_bytes = audio_file.read()
                    with open(audio_path, "wb") as f:
                        f.write(file_bytes)
                    audio_bytes_to_save = file_bytes
                else:
                    st.error("No audio found. Please record or upload.")
                    logger.warning("No audio found on submission.")
                    st.session_state['processing'] = False
                    st.stop()

                # Transcribe audio using new OpenAI API
                try:
                    with st.spinner("Transcribing audio with Whisper..."):
                        # st.video(loading_video_path)  # Overlay now handles loading video
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

                transcript_path = os.path.join(tmpdir, "transcript.txt")
                with open(transcript_path, "w", encoding="utf-8") as f:
                    f.write(transcript)

                # Format transcript as Q&A using ChatGPT
                with st.spinner("Formatting transcript as Q&A with ChatGPT..."):
                    # st.video(loading_video_path)  # Overlay now handles loading video
                    qa_text = format_transcript_as_qa(transcript, client)
                qa_text = st.text_area("Q&A Transcript (editable)", qa_text, height=300)
                qa_path = os.path.join(tmpdir, "qa_transcript.txt")
                with open(qa_path, "w", encoding="utf-8") as f:
                    f.write(qa_text)

                # Count Qs and As, award points
                num_questions, num_answers = count_questions_answers(qa_text)
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
                # st.experimental_rerun()  # REMOVED

    # Show results and buttons if transcribed
    if st.session_state.get('transcribed', False):
        st.markdown(f"**Questions:** {st.session_state['submission_data']['NumQuestions']}  |  **Answers:** {st.session_state['submission_data']['NumAnswers']}  |  **Points Awarded:** {st.session_state['submission_data']['PointsAwarded']}")
        st.subheader("Transcript")
        st.text_area("Output", st.session_state['submission_data']['Transcript'], height=200)
        # Create ZIP
        with tempfile.TemporaryDirectory() as tmpdir:
            inputs_df = pd.DataFrame([st.session_state['submission_data']])
            inputs_path = os.path.join(tmpdir, "inputs.csv")
            inputs_df.to_csv(inputs_path, index=False)
            audio_path = os.path.join(tmpdir, "audio.wav")
            with open(audio_path, "wb") as f:
                f.write(st.session_state['audio_bytes_to_save'])
            transcript_path = os.path.join(tmpdir, "transcript.txt")
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(st.session_state['submission_data']['Transcript'])
            qa_path = os.path.join(tmpdir, "qa_transcript.txt")
            with open(qa_path, "w", encoding="utf-8") as f:
                f.write(st.session_state['submission_data']['QAText'])
            zip_path = os.path.join(tmpdir, "package.zip")
            with zipfile.ZipFile(zip_path, "w") as zipf:
                zipf.write(inputs_path, "inputs.csv")
                zipf.write(audio_path, os.path.basename(audio_path))
                zipf.write(transcript_path, "transcript.txt")
                zipf.write(qa_path, "qa_transcript.txt")
            with open(zip_path, "rb") as zf:
                st.download_button("Download ZIP", zf, file_name="package.zip")
        # Submit to Database button
        submit_btn = st.button("Submit to Database", disabled=st.session_state['processing'])
        if submit_btn:
            st.session_state['processing'] = True
            # st.experimental_rerun()  # REMOVED
        if st.session_state['processing'] and not st.session_state.get('submitted', False):
            with st.spinner("Saving submission to the database..."):
                insert_submission(engine, st.session_state["submission_data"], st.session_state["audio_bytes_to_save"])
            st.session_state['submitted'] = True
            st.session_state['processing'] = False
            # Clear form/session state after submission
            st.session_state['transcribed'] = False
            st.session_state['submission_data'] = None
            st.session_state['audio_bytes_to_save'] = None
            st.experimental_rerun()
else:
    st.info("Please record or upload an audio file to enable transcription and points calculation.")

# --- Van Dyk Brand Theme CSS ---
# (Removed all custom CSS to revert to default Streamlit theme)
