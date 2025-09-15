import streamlit as st
import pandas as pd
import os
import re
import logging
from utils.db import get_engine
from utils.ai import get_openai_client
import base64
from st_audiorec import st_audiorec
import datetime
import io
import time
import hashlib

# --- Q&A Text Validation ---
def is_valid_qa_text(text):
    if not text or not isinstance(text, str):
        return False
    # Accepts either Q1:/A1: or Q:/A: style
    has_q = re.search(r"^Q(\d*)\:", text, re.MULTILINE)
    has_a = re.search(r"^A(\d*)\:", text, re.MULTILINE)
    return bool(has_q and has_a)

# --- Input Validation Functions ---
def validate_pdf_file(file_bytes):
    """Validate PDF file size and format"""
    if not file_bytes:
        return False, "No file data"
    
    # Check file size (25MB limit)
    max_size = 25 * 1024 * 1024  # 25MB in bytes
    if len(file_bytes) > max_size:
        return False, f"File too large: {len(file_bytes) / (1024*1024):.1f}MB. Maximum allowed: 25MB"
    
    # Basic PDF format validation
    if not file_bytes.startswith(b'%PDF-'):
        return False, "File is not a valid PDF"
    
    return True, "Valid PDF file"

def validate_audio_file(file_bytes):
    """Validate audio file size and basic format"""
    if not file_bytes:
        return False, "No audio data"
    
    # Check file size (200MB limit)
    max_size = 200 * 1024 * 1024  # 200MB in bytes
    if len(file_bytes) > max_size:
        return False, f"Audio file too large: {len(file_bytes) / (1024*1024):.1f}MB. Maximum allowed: 200MB"
    
    # Minimum audio length check
    if len(file_bytes) < 1000:
        return False, "Audio file too short"
    
    return True, "Valid audio file"

def sanitize_input(text):
    """Basic input sanitization"""
    if not text or not isinstance(text, str):
        return ""
    # Remove potentially dangerous characters
    return re.sub(r'[<>"\';]', '', text.strip())

# --- Enhanced Audio Transcription (No Temp Files) ---
def transcribe_audio_enhanced(client, audio_bytes, max_retries=3):
    """Enhanced transcription without any temporary files"""
    for attempt in range(max_retries):
        try:
            # Create in-memory buffer
            audio_buffer = io.BytesIO(audio_bytes)
            audio_buffer.name = "audio.wav"
            audio_buffer.seek(0)
            
            # Enhanced Whisper call with better prompt
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_buffer,
                language="en",
                temperature=0.2,
                prompt="This is a technical Q&A session about industrial equipment, machinery, and service procedures. Please transcribe accurately including technical terms, model numbers, and specific equipment details."
            )
            
            return response.text
            
        except Exception as e:
            logger.warning(f"Transcription attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(1 + attempt)
                continue
            else:
                raise e

# --- Session State Initialization ---
def init_session_state():
    """Initialize session state with proper defaults"""
    defaults = {
        'processing': False,
        'transcribed': False,
        'submitted': False,
        'submission_data': {},
        'manual_pdf': None,
        'qa_text': '',
        'submission_hash': None  # For duplicate prevention
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- DB and OpenAI Setup with Better Error Handling ---
@st.cache_resource
def get_database_connection():
    """Get database connection with proper error handling"""
    try:
        engine = get_engine()
        # Test connection with SQLAlchemy 2.0+ compatible syntax
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        st.error("Database connection failed. Please check your configuration.")
        return None

@st.cache_resource
def cleanup_connections():
    """Cleanup database connections"""
    try:
        if 'engine' in globals():
            engine.dispose()
    except:
        pass

@st.cache_resource
def get_openai_connection():
    """Get OpenAI client with proper error handling"""
    try:
        client = get_openai_client()
        logger.info("OpenAI client ready. Using enhanced transcription (no temp files).")
        return client
    except Exception as e:
        logger.error(f"OpenAI client setup failed: {e}")
        st.error("OpenAI client setup failed. Please check your API key.")
        return None

engine = get_database_connection()
client = get_openai_connection()

if not engine or not client:
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
if os.path.exists("VDRS Logo.png"):
    st.image("VDRS Logo.png", width=96)
st.markdown("<div style='height: 0.5em'></div>", unsafe_allow_html=True)
st.markdown("<span style='font-size:2.2em; font-weight:800; color:#15487d;'>DykScribe 📝</span>", unsafe_allow_html=True)
st.markdown("<div style='font-size:1.1em; color:#666; margin-bottom:1.5em;'>DykScribe is a streamlined QA and information capture form for Van Dyk users. It allows you to <span style='color:#d66638;'>🎤 record</span> or <span style='color:#d66638;'>⬆️ upload</span> audio, transcribe responses, and submit detailed <span style='color:#15487d;'>🏭 equipment</span> and <span style='color:#15487d;'>🧑‍💼 user</span> information for review and analysis.</div>", unsafe_allow_html=True)

# --- Data Fetch Functions with Caching and Error Handling ---
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_users():
    try:
        df = pd.read_sql("SELECT UserName, Role FROM vw_ActivePM_FSE_Users", engine)
        if df.empty:
            logger.warning("No users found in the database.")
            return pd.DataFrame()
        return df
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        st.error("Failed to load users from the database.")
        return pd.DataFrame()

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_all_equipment_types():
    try:
        df = pd.read_sql("SELECT DISTINCT EquipmentType FROM vw_EquipmentTypes", engine)
        if df.empty:
            logger.warning("No equipment types found in the database.")
            return pd.DataFrame()
        return df
    except Exception as e:
        logger.error(f"Error fetching equipment types: {e}")
        st.error("Failed to load equipment types from the database.")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_manufacturers_by_equipment_type(equipment_type):
    try:
        df = pd.read_sql(
            "SELECT DISTINCT Manufacturer FROM vw_EquipmentTypes WHERE EquipmentType = ?",
            engine, params=(equipment_type,)  # Fixed: Use tuple instead of list
        )
        if df.empty:
            logger.warning(f"No manufacturers found for equipment type: {equipment_type}")
            return pd.DataFrame()
        return df
    except Exception as e:
        logger.error(f"Error fetching manufacturers: {e}")
        st.error("Failed to load manufacturers from the database.")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_models(manufacturer, equipment_type):
    try:
        df = pd.read_sql(
            "SELECT DISTINCT Model FROM vw_Models WHERE Manufacturer = ? AND EquipmentType = ?",
            engine, params=(manufacturer, equipment_type)  # Fixed: Use tuple instead of list
        )
        if df.empty:
            logger.warning(f"No models found for {manufacturer} - {equipment_type}")
            return pd.DataFrame()
        return df
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        st.error("Failed to load models from the database.")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_spec_options(manufacturer, equipment_type, field):
    try:
        df = pd.read_sql(
            f"SELECT DISTINCT {field} FROM vw_ModelSpecifications WHERE Manufacturer = ? AND EquipmentType = ?",
            engine, params=(manufacturer, equipment_type)  # Fixed: Use tuple instead of list
        )
        if df.empty:
            return []
        return df[field].dropna().tolist()
    except Exception as e:
        logger.error(f"Error fetching {field} options: {e}")
        return []

@st.cache_data(ttl=3600)
def get_spec_labels(equipment_type):
    try:
        query = """
            SELECT Specification2Label, Specification3Label
            FROM vw_EquipmentTypeSpecLabels
            WHERE EquipmentType = ?
        """
        return pd.read_sql(query, engine, params=(equipment_type,))  # Fixed: Use tuple instead of list
    except Exception as e:
        logger.error(f"Error fetching spec labels: {e}")
        return pd.DataFrame()

# --- Helper: Insert submission into SQL with PDF support ---
def insert_submission(engine, data, audio_bytes, pdf_bytes=None):
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            stmt = text("""
                INSERT INTO QAForms
                (UserName, Role, EntryDateTime, Manufacturer, EquipmentType, Model, Specifications2, Specifications3, Notes, NumQuestions, NumAnswers, PointsAwarded, QAText, Transcript, AudioBlob, ManualPDF)
                VALUES (:UserName, :Role, :EntryDateTime, :Manufacturer, :EquipmentType, :Model, :Specifications2, :Specifications3, :Notes, :NumQuestions, :NumAnswers, :PointsAwarded, :QAText, :Transcript, :AudioBlob, :ManualPDF)
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
                "AudioBlob": audio_bytes,
                "ManualPDF": pdf_bytes
            })
        st.success("Submission saved to the database.")
        return True
    except Exception as e:
        logger.error(f"Error inserting submission: {e}")
        st.error("Failed to save submission to the database.")
        return False

# --- User Dropdown and Date/Time with Better Error Handling ---
users_df = get_users()
user_names_sorted = []

if not users_df.empty:
    user_names_sorted = sorted([x for x in users_df["UserName"].unique() if x is not None])

if user_names_sorted:
    user_name = st.selectbox("User Name", user_names_sorted)
    st.markdown("<span style='font-size: 0.85em; color: #888;'>Your role will be auto-filled based on your username.</span>", unsafe_allow_html=True)
    
    # Fixed: Better error handling for role lookup
    try:
        role_matches = users_df.loc[users_df["UserName"] == user_name, "Role"]
        role = role_matches.values[0] if len(role_matches) > 0 else ""
    except (IndexError, KeyError):
        role = ""
        logger.warning(f"Role not found for user: {user_name}")
    
    st.text_input("Role", value=role, disabled=True)
    st.markdown("<span style='font-size: 0.85em; color: #888;'>This field is auto-filled and cannot be changed. It is determined by your username.</span>", unsafe_allow_html=True)
else:
    st.error("❌ No users found in the database. Please contact your administrator.")
    st.stop()

entry_datetime = st.text_input(
    "Entry Date & Time",
    value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    disabled=True
)
st.markdown("<span style='font-size: 0.85em; color: #888;'>This field is auto-filled with the current date and time and cannot be changed.</span>", unsafe_allow_html=True)

# --- Equipment Type First ---
equip_types_df = get_all_equipment_types()
equipment_types_sorted = []

if not equip_types_df.empty:
    equipment_types_sorted = sorted([x for x in equip_types_df["EquipmentType"].unique() if x is not None])

if equipment_types_sorted:
    equipment_type = st.selectbox(
        "Select Equipment Type *",
        equipment_types_sorted + ["Other (type to add new)"]
    )
    if equipment_type == "Other (type to add new)":
        equipment_type = st.text_input("Enter new Equipment Type *")
        equipment_type = sanitize_input(equipment_type)
else:
    st.error("❌ No equipment types found in the database.")
    st.stop()

# Only show the rest of the form if equipment_type is filled
if equipment_type and equipment_type.strip():
    manu_df = get_manufacturers_by_equipment_type(equipment_type)
    manufacturers_sorted = []
    
    if not manu_df.empty:
        manufacturers_sorted = sorted([x for x in manu_df["Manufacturer"].unique() if x is not None])
    
    if manufacturers_sorted:
        manufacturer = st.selectbox(
            "Select Manufacturer",
            manufacturers_sorted + ["Other (type to add new)"]
        )
        if manufacturer == "Other (type to add new)":
            manufacturer = st.text_input("Enter new Manufacturer")
            manufacturer = sanitize_input(manufacturer)
    else:
        st.warning("⚠️ No manufacturers found for this equipment type.")
        manufacturer = st.text_input("Enter Manufacturer")
        manufacturer = sanitize_input(manufacturer)

    # --- Dynamic Spec Labels ---
    spec2_label = "Specifications 2"
    spec3_label = "Specifications 3"
    
    spec_labels = get_spec_labels(equipment_type)
    if not spec_labels.empty:
        spec2_label = spec_labels["Specification2Label"].iloc[0] or spec2_label
        spec3_label = spec_labels["Specification3Label"].iloc[0] or spec3_label

    st.markdown("**Select the model for the chosen manufacturer and equipment type:**")
    model_df = get_models(manufacturer, equipment_type)
    models_sorted = []
    
    if not model_df.empty:
        models_sorted = sorted([x for x in model_df["Model"].unique() if x is not None])
    
    if models_sorted:
        model = st.selectbox("Select Model", models_sorted)
    else:
        st.warning("⚠️ No models found for this combination.")
        model = st.text_input("Enter Model")
        model = sanitize_input(model)

    # --- Dynamic Spec Dropdowns ---
    spec2_options = get_spec_options(manufacturer, equipment_type, "Specifications2")
    spec3_options = get_spec_options(manufacturer, equipment_type, "Specifications3")

    if spec2_options:
        spec2 = st.selectbox(spec2_label, spec2_options)
    else:
        spec2 = st.text_input(spec2_label)
        spec2 = sanitize_input(spec2)
    
    if spec3_options:
        spec3 = st.selectbox(spec3_label, spec3_options)
    else:
        spec3 = st.text_input(spec3_label)
        spec3 = sanitize_input(spec3)

    # --- Notes and Additional Info ---
    st.caption("Enter any additional notes or comments about this submission. This can include context, issues, or anything relevant.")
    notes = st.text_area("Remark or Additional Info")
    notes = sanitize_input(notes)

    # --- PDF Manual Upload Section ---
    st.subheader("📖 Equipment Manual Upload")
    st.markdown("Upload the equipment manual or any relevant PDF documentation.")
    
    uploaded_pdf = st.file_uploader(
        "Select PDF Manual",
        type=["pdf"],
        help="Upload equipment manual, service documentation, or any relevant PDF files (max 25MB)"
    )
    
    if uploaded_pdf is not None:
        pdf_bytes = uploaded_pdf.read()
        is_valid, message = validate_pdf_file(pdf_bytes)
        
        if is_valid:
            st.session_state['manual_pdf'] = pdf_bytes
            st.success(f"✅ PDF uploaded: {uploaded_pdf.name} ({len(pdf_bytes) / (1024*1024):.2f} MB)")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("File Size", f"{len(pdf_bytes) / (1024*1024):.2f} MB")
            with col2:
                st.metric("File Name", uploaded_pdf.name)
        else:
            st.error(f"❌ {message}")
            st.session_state['manual_pdf'] = None
    elif st.session_state.get('manual_pdf') is not None:
        st.info("📄 PDF manual is ready for submission")

    # --- Tabs for Transcript/Output and Audio ---
    tabs = st.tabs(["Type Out", "Audio"])

    qa_text = st.session_state.get('qa_text', '').strip()
    min_audio_length = 1000
    wav_audio_data = None
    file_bytes = None
    
    # Fixed: Define variables outside tab context to avoid scope issues
    qa_section_visible = True
    audio_section_visible = True
    qa_valid = False
    valid_audio = False

    # Determine if audio is present
    with tabs[1]:
        st.subheader("Audio")
        st.markdown("""
        - Record your audio or upload an MP3/WAV file.
        - After processing, the transcript will appear in the Transcript/Output tab.
        - **Enhanced transcription** with improved technical terminology recognition.
        """)
        
        audio_section_visible = not bool(qa_text)
        if not audio_section_visible:
            st.info("Audio input is disabled because you are submitting a typed transcript.")
        else:
            wav_audio_data = st_audiorec()
            if wav_audio_data is not None and len(wav_audio_data) > min_audio_length:
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
                is_valid, message = validate_audio_file(file_bytes)
                
                if is_valid:
                    st.audio(file_bytes, format='audio/wav')
                else:
                    st.error(f"❌ {message}")
                    file_bytes = None

    # Determine if Q&A is present and if audio is present
    valid_audio = (wav_audio_data is not None and len(wav_audio_data) > min_audio_length) or (file_bytes is not None and len(file_bytes) > min_audio_length)
    audio_bytes_to_save = wav_audio_data if (wav_audio_data is not None and len(wav_audio_data) > min_audio_length) else (file_bytes if (file_bytes is not None and len(file_bytes) > min_audio_length) else None)

    with tabs[0]:
        st.subheader("Type Out")
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
            qa_text = st.text_area(
                "Q&A Transcript (editable)", 
                st.session_state.get('qa_text', ''), 
                height=300, 
                key="qa_text_area"
            )
            st.session_state['qa_text'] = qa_text
            qa_valid = is_valid_qa_text(qa_text.strip()) if qa_text.strip() else False
            if qa_text.strip() and not qa_valid:
                st.warning("Please enter at least one valid Q&A pair in the required format (Q1:/A1: or Q:/A:). Submission will be enabled only when valid.")

    # Fixed: Variable scope - define qa_valid outside tab context
    if qa_section_visible:
        qa_valid = is_valid_qa_text(qa_text.strip()) if qa_text.strip() else False

    # --- Submit Button and Validation ---
    can_submit = (qa_valid and not valid_audio) or (valid_audio and not qa_valid)
    
    # Form validation before submission
    if not can_submit:
        if qa_valid and valid_audio:
            st.warning("⚠️ Please provide either a valid Q&A in the required format OR a valid audio file, but not both.")
        elif not qa_valid and not valid_audio:
            st.info("ℹ️ Please provide either a valid Q&A in the required format or a valid audio file to enable submission.")
    
    submit_btn = st.button("Submit", disabled=not can_submit or st.session_state.get('processing', False))

    if submit_btn and can_submit:
        st.session_state['processing'] = True
        
        try:
            with st.spinner("Processing, please wait..."):
                transcript = ""
                
                # If audio is present, transcribe with enhanced method (NO TEMP FILES)
                if valid_audio:
                    try:
                        with st.spinner("Transcribing audio with enhanced Whisper (no temp files)..."):
                            transcript = transcribe_audio_enhanced(client, audio_bytes_to_save)
                        st.success("✅ Audio transcribed successfully.")
                    except Exception as e:
                        logger.error(f"Transcription failed: {e}")
                        st.error(f"❌ Transcription failed: {str(e)}")
                        st.session_state['processing'] = False
                        st.stop()
                    
                    # Format transcript as Q&A using OpenAI with enhanced prompt
                    try:
                        with st.spinner("Formatting transcript as Q&A with enhanced ChatGPT prompt..."):
                            qa_prompt = (
                                "You are an expert at extracting structured Q&A from technical service conversations. "
                                "Extract ONLY clear, relevant question and answer pairs from the following transcript. "
                                "Focus on technical discussions about equipment, troubleshooting, maintenance procedures, and specific technical details. "
                                "Ignore filler words, small talk, greetings, and irrelevant content. "
                                "Include technical terms, model numbers, part numbers, and specific procedures accurately. "
                                "If there are no valid technical Q&A pairs, return 'No clear technical Q&A pairs found.' "
                                "Format strictly as:\nQ1: [Clear, specific technical question]\nA1: [Complete, detailed technical answer]\nQ2: [Next question]\nA2: [Next answer]\n"
                                "Do not add explanations, summaries, or extra text.\n\nTranscript:\n"
                                f"{transcript}"
                            )
                            gpt_response = client.chat.completions.create(
                                model="gpt-4",
                                messages=[
                                    {
                                        "role": "system", 
                                        "content": "You are an expert at extracting structured technical Q&A from service and maintenance transcripts. Focus on accuracy, technical precision, and clarity."
                                    },
                                    {"role": "user", "content": qa_prompt}
                                ],
                                temperature=0.1,
                                max_tokens=2000
                            )
                            qa_text = gpt_response.choices[0].message.content
                            st.session_state['qa_text'] = qa_text
                    except Exception as e:
                        logger.error(f"OpenAI Q&A formatting failed: {e}")
                        st.error(f"❌ OpenAI Q&A formatting failed: {str(e)}")
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
                        st.error(f"❌ OpenAI Q&A formatting failed: {str(e)}")
                        st.session_state['processing'] = False
                        st.stop()

                # Count Qs and As, award points (no file operations)
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

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            st.error(f"❌ Processing failed: {str(e)}")
            st.session_state['processing'] = False

    # Show results and buttons if transcribed
    if st.session_state.get('transcribed', False):
        submission_data = st.session_state.get('submission_data', {})
        num_questions = submission_data.get('NumQuestions', 0)
        num_answers = submission_data.get('NumAnswers', 0)
        points_awarded = submission_data.get('PointsAwarded', 0)
        qa_text = submission_data.get('QAText', '')
        transcript = submission_data.get('Transcript', '')
        
        # Enhanced results display
        st.markdown("---")
        st.subheader("📊 Processing Results")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Questions", num_questions)
        with col2:
            st.metric("Answers", num_answers)
        with col3:
            st.metric("Points Awarded", points_awarded)
        
        st.subheader("📝 Transcript")
        st.text_area("Raw Transcript", transcript, height=200, help="This is the raw transcription from the audio")
        
        st.subheader("❓ Q&A Extracted")
        st.text_area("Formatted Q&A", qa_text, height=200, help="This is the extracted and formatted Q&A pairs")
        
        # Show PDF status if available
        if st.session_state.get('manual_pdf') is not None:
            st.info(f"📄 PDF Manual ready for submission ({len(st.session_state['manual_pdf']) / 1024:.1f} KB)")
        
        # Submit to Database button with confirmation
        col1, col2 = st.columns([3, 1])
        with col1:
            submit_to_db = st.button("💾 Submit to Database", disabled=st.session_state.get('processing', False))
        with col2:
            if st.button("🔄 Start Over"):
                # Clear all session state for new submission
                for key in ['transcribed', 'submission_data', 'audio_bytes_to_save', 'manual_pdf', 'qa_text']:
                    st.session_state[key] = {} if key == 'submission_data' else None if key != 'qa_text' else ''
                st.rerun()
        
        if submit_to_db:
            st.session_state['processing'] = True
            
            with st.spinner("Saving submission to the database..."):
                pdf_bytes = st.session_state.get('manual_pdf')
                success = insert_submission(
                    engine, 
                    st.session_state["submission_data"], 
                    st.session_state["audio_bytes_to_save"], 
                    pdf_bytes
                )
            
            if success:
                st.session_state['submitted'] = True
                st.session_state['processing'] = False
                
                # Fixed: Clear session state only after successful submission
                time.sleep(2)  # Give user time to see success message
                for key in ['transcribed', 'submission_data', 'audio_bytes_to_save', 'manual_pdf', 'qa_text']:
                    st.session_state[key] = {} if key == 'submission_data' else None if key != 'qa_text' else ''
                
                st.success("🎉 Submission completed! You can now start a new submission.")
                time.sleep(3)
                st.rerun()
            else:
                st.session_state['processing'] = False

else:
    st.info("Please select an equipment type to continue with the form.")