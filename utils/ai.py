import openai
import os
import streamlit as st

def get_openai_client():
    api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
    return openai.OpenAI(api_key=api_key) 