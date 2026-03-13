import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google import genai
from config import settings

load_dotenv()

def list_models():
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    print("=== MODELOS DISPONÍVEIS ===")
    for model in client.models.list():
        print(f"- {model.name}")

if __name__ == "__main__":
    list_models()
