# DykScribe 📝

**Author:** Ajith Srikanth  
**Version:** 2.0.0  
**Last Updated:** December 2024

---

## Overview
DykScribe is a **streamlined QA and information capture form** designed specifically for **Van Dyk Service Technicians**. It enables field service engineers to document their work through structured Q&A pairs, either by typing or recording audio, with AI-powered transcription and intelligent Q&A extraction.

### Key Capabilities
- 🎤 **Audio Recording & Upload**: Record directly or upload MP3/WAV files
- 📝 **Manual Q&A Entry**: Type structured Q&A pairs with real-time validation
- 🤖 **AI-Powered Processing**: OpenAI Whisper for transcription + GPT-4 for Q&A extraction
- 🏭 **Equipment Management**: Dynamic equipment type, manufacturer, and model selection
- 📊 **Points System**: Automatic calculation based on valid Q&A pairs
- 💾 **Database Integration**: Secure storage with duplicate prevention
- 📄 **PDF Manual Upload**: Attach equipment manuals and documentation

---

## ✨ Features

### **Core Functionality**
- **Dual Input Methods**: Type out Q&A pairs OR record/upload audio (mutually exclusive)
- **Smart Validation**: Real-time Q&A format validation with helpful error messages
- **AI Transcription**: Enhanced Whisper-1 with technical terminology optimization
- **Intelligent Q&A Extraction**: GPT-4 powered extraction from transcripts
- **Equipment Database**: Dynamic dropdowns for equipment types, manufacturers, and models
- **PDF Documentation**: Upload equipment manuals (up to 25MB)
- **Points System**: 1 point per valid question with automatic calculation

### **Enhanced User Experience**
- **Responsive UI**: Clean, modern interface with loading states and progress indicators
- **Input Validation**: Comprehensive file size and format validation
- **Error Handling**: Graceful error recovery with user-friendly messages
- **Session Management**: Smart session state handling with duplicate prevention
- **Performance**: Cached database queries and optimized resource usage

### **Security & Reliability**
- **Input Sanitization**: Protection against malicious input
- **Duplicate Prevention**: Hash-based duplicate submission detection
- **Secure Storage**: Environment variable based configuration
- **Error Logging**: Comprehensive logging for debugging and monitoring

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Node.js 16+ (for audio recorder frontend)
- Microsoft SQL Server database access
- OpenAI API key

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd DykScribe
```

### 2. Install Python Dependencies
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Install Frontend Dependencies
```bash
cd st_audiorec/frontend
npm install
npm run build
cd ../..
```

### 4. Configure Environment Variables

#### Option A: Streamlit Secrets (Recommended for Production)
Create `.streamlit/secrets.toml`:
```toml
db_server = "your_server.database.windows.net"
db_user = "your_db_user"
db_password = "your_db_password"
db_name = "PowerAppsDatabase"
openai_api_key = "sk-your-openai-key"
```

#### Option B: Environment Variables (Local Development)
Create `.env` file or set system variables:
```bash
export OPENAI_API_KEY="sk-your-openai-key"
export DB_SERVER="your_server.database.windows.net"
export DB_USER="your_db_user"
export DB_PASSWORD="your_db_password"
export DB_NAME="PowerAppsDatabase"
```

### 5. Run the Application
```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`

---

## 📖 Usage Guide

### Step-by-Step Process

1. **👤 User Selection**
   - Select your username from the dropdown
   - Your role will be automatically populated

2. **🏭 Equipment Information**
   - **Equipment Type**: Choose from database or add new
   - **Manufacturer**: Select from filtered list or add new
   - **Model**: Choose from available models or enter custom
   - **Specifications**: Dynamic fields based on equipment type

3. **📝 Input Method Selection**
   - **Type Out Tab**: Manually enter Q&A pairs
     - Format: `Q1: Your question\nA1: Your answer\nQ2: Next question\nA2: Next answer`
     - Or: `Q: Question\nA: Answer`
   - **Audio Tab**: Record or upload audio
     - Click record button for live recording
     - Or upload MP3/WAV files (max 200MB)

4. **📄 Optional Documentation**
   - Upload PDF manuals (max 25MB)
   - Add notes or additional information

5. **🚀 Processing & Submission**
   - Click "Submit" to process your input
   - AI will transcribe audio and extract Q&A pairs
   - Review the generated Q&A pairs
   - Click "Submit to Database" to save

### Q&A Format Requirements
```
Q1: What is the main issue with the equipment?
A1: The motor is overheating due to insufficient lubrication.

Q2: What steps were taken to resolve it?
A2: Applied proper lubricant and checked temperature sensors.
```

---

## 🏗️ Architecture

### Project Structure
```
DykScribe/
├── app.py                 # Main Streamlit application
├── app_secrets.py         # Secret management utilities
├── requirements.txt       # Python dependencies
├── utils/
│   ├── ai.py             # OpenAI client configuration
│   └── db.py             # Database connection utilities
├── st_audiorec/          # Custom audio recorder component
│   ├── __init__.py
│   └── frontend/         # React-based audio recorder
└── README.md
```

### Technology Stack
- **Frontend**: Streamlit + React (audio recorder)
- **Backend**: Python + SQLAlchemy
- **Database**: Microsoft SQL Server
- **AI Services**: OpenAI (Whisper + GPT-4)
- **Audio Processing**: Web Audio API + Streamlit components

---

## 🔧 Configuration

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for transcription and Q&A extraction |
| `DB_SERVER` | Yes | SQL Server hostname |
| `DB_USER` | Yes | Database username |
| `DB_PASSWORD` | Yes | Database password |
| `DB_NAME` | Yes | Database name |

### Database Schema
The application expects the following database views:
- `vw_ActivePM_FSE_Users` - User and role information
- `vw_EquipmentTypes` - Available equipment types
- `vw_Models` - Equipment models by manufacturer
- `vw_ModelSpecifications` - Model specifications
- `vw_EquipmentTypeSpecLabels` - Dynamic spec labels
- `QAForms` - Main submission table

---

## 🐛 Troubleshooting

### Common Issues

**🔊 Audio Recording Problems**
- Ensure microphone permissions are granted
- Try Chrome browser (best compatibility)
- Check if audio device is working in other applications

**🤖 OpenAI API Issues**
- Verify API key is correct and active
- Check API usage limits and billing
- Ensure stable internet connection

**💾 Database Connection Errors**
- Verify database credentials
- Check network connectivity to SQL Server
- Ensure database server is running

**📝 Q&A Format Issues**
- Use proper format: `Q1: question\nA1: answer`
- Ensure each Q has a corresponding A
- Check for special characters that might break parsing

**📄 File Upload Problems**
- PDF files must be under 25MB
- Audio files must be under 200MB
- Ensure file formats are supported (PDF, MP3, WAV)

### Getting Help
- Check the terminal/console for detailed error messages
- Review application logs for debugging information
- Contact system administrator for database issues

---

## 📞 Support & Contact

**Development Team:**
- **Ajith Srikanth** - Lead Developer
- [LinkedIn](http://linkedin.com/in/as31)
- Email: [Contact via LinkedIn](http://linkedin.com/in/as31)

**Technical Support:**
- For database issues: Contact your system administrator
- For OpenAI API issues: Check [OpenAI Status](https://status.openai.com/)
- For general support: Create an issue in the repository

---

## 📄 License

This project is proprietary software developed for Van Dyk Service. All rights reserved.

---

## 🔄 Version History

### v2.0.0 (December 2024)
- ✨ Complete UI/UX overhaul with modern design
- 🔒 Enhanced security with input sanitization
- 🚀 Performance improvements with caching
- 🐛 Fixed critical bugs and improved error handling
- 📚 Comprehensive documentation update

### v1.0.0 (Initial Release)
- Basic Q&A capture functionality
- Audio recording and transcription
- Database integration
- Equipment management system

---

**Enjoy using DykScribe! 🎉** 