# DykScribe

DykScribe is a streamlined QA and information capture form for Van Dyk users. It allows you to record or upload audio, transcribe responses, and submit detailed equipment and user information for review and analysis.

## Features
- Record or upload audio (MP3/WAV)
- Automatic transcription and Q&A extraction
- User, equipment, and model selection
- Database integration for submissions
- Modern, user-friendly UI

## Quick Start
1. Clone the repo:
   ```sh
   git clone https://github.com/fjamalvdrs/DykScribe.git
   cd DykScribe
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Run the app:
   ```sh
   streamlit run app.py
   ```

## Deployment
- Deploy on [Streamlit Cloud](https://share.streamlit.io/) or any cloud platform supporting Python/Streamlit.
- Set up your `secrets.toml` or environment variables for API keys and DB credentials.

## Project Structure
- `app.py` — Main Streamlit app
- `utils/` — Utility modules (AI, DB)
- `requirements.txt` — Python dependencies
- `README.md` — This file

## Contact
For help, contact Faizan: [FJamal@vdrs.com](mailto:FJamal@vdrs.com) 