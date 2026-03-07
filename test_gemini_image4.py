import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
try:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    result = client.models.generate_images(
        model='imagen-4.0-generate-001',
        prompt='A dog',
        config=dict(number_of_images=1)
    )
    print("Success! Got bytes:", len(result.generated_images[0].image.image_bytes))
except Exception as e:
    print("Error:", e)
