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

# DykScribe

**Author:** Ajith Srikanth

---

## Overview
DykScribe is a streamlined QA and information capture form for Van Dyk users. It allows you to:
- Type out or record/upload audio responses
- Transcribe audio to text
- Extract and format Q&A pairs
- Submit detailed equipment and user information for review and analysis

The app is built with Streamlit and integrates with OpenAI for robust audio transcription and Q&A extraction.

---

## Features
- **Type Out Tab:** Manually enter Q&A pairs in a simple, structured format.
- **Audio Tab:** Record or upload audio, which is transcribed and processed into Q&A pairs.
- **Mutual Exclusivity:** Only one input method (typed or audio) can be used per submission.
- **Automatic Points Calculation:** Points are awarded based on the number of valid Q&A pairs.
- **Responsive UI:** Clear feedback, spinners during processing, and error messages for any issues.
- **Database Integration:** Submissions can be saved to a backend database (if configured).

---

## Usage
1. **Select Equipment Type** (required). The rest of the form will appear after this selection.
2. **Fill in other fields** as needed (Manufacturer, Model, etc.).
3. **Choose your input method:**
   - **Type Out:** Enter Q&A pairs in the required format (e.g., `Q1: ...\nA1: ...`).
   - **Audio:** Record or upload an audio file. The app will transcribe and extract Q&A pairs.
4. **Submit:** Click the Submit button. The app will process your input, calculate points, and display results.
5. **Submit to Database:** (If enabled) Save your submission for review and analysis.

---

## Environment Variables
- `OPENAI_API_KEY` – Required for audio transcription and Q&A extraction.
- Database variables (if using DB):
  - `DB_SERVER`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`

---

## Troubleshooting
- **Audio not recording?**
  - Check browser permissions for microphone access.
  - Try a different browser (Chrome recommended).
- **OpenAI errors?**
  - Ensure your API key is set and valid.
  - Check your usage limits/quota on OpenAI.
- **Points not awarded?**
  - Make sure your Q&A follows the required format (`Q: ...`, `A: ...` or `Q1: ...`, `A1: ...`).
- **Other issues?**
  - Check the terminal/console for error messages.
  - Review the app logs for more details.

---

## Contact
For help, contact Faizan: [FJamal@vdrs.com](mailto:FJamal@vdrs.com) 

## Author
Ajith Srikanth
=======
For questions, support, or feedback, contact:
- **Ajith Srikanth** (Author)
- [LinkedIn](http://linkedin.com/in/as31)
- Email: asrikanth@vandykbaler.com

---
