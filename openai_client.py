import openai
from app_secrets import get_openai_key

def get_openai_client():
    api_key = get_openai_key()
    return openai.OpenAI(api_key=api_key) 