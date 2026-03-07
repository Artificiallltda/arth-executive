import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
try:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    result = client.models.generate_content(
        model='nano-banana-pro-preview',
        contents='Hello'
    )
    print("Text response:", result.text)
except Exception as e:
    print("Text Error:", e)

try:
    result = client.models.generate_images(
        model='nano-banana-pro-preview',
        prompt='A dog',
        config=dict(number_of_images=1)
    )
    print("Image response:", len(result.generated_images))
except Exception as e:
    print("Image Error:", e)
