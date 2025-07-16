import streamlit as st
import os

def get_db_credentials():
    db_server = st.secrets.get("db_server", os.getenv("DB_SERVER", "vdrsapps.database.windows.net"))
    db_user = st.secrets.get("db_user", os.getenv("DB_USER", "VDRSAdmin"))
    db_password = st.secrets.get("db_password", os.getenv("DB_PASSWORD", "Oz01%O0wi"))
    db_name = st.secrets.get("db_name", os.getenv("DB_NAME", "PowerAppsDatabase"))
    return db_server, db_user, db_password, db_name

def get_openai_key():
    return os.getenv("OPENAI_API_KEY") 