import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.image_generator import generate_image
from config import settings

load_dotenv()

async def test_image():
    print(f"Testando API Key terminada em... {settings.GEMINI_API_KEY[-4:] if settings.GEMINI_API_KEY else 'NÃO DEFINIDA'}")
    print("Tentando gerar imagem...")
    
    try:
        resultado = await generate_image.ainvoke({"prompt": "Um gato programador de terno no esporte"})
        print("\n\n=== RESULTADO ===")
        print(resultado)
        print("=================")
    except Exception as e:
        print(f"\n\n=== ERRO NO TESTE ===")
        print(str(e))
        print("=====================")

if __name__ == "__main__":
    asyncio.run(test_image())
