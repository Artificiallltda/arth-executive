import os
import uuid
import base64
import httpx
import logging
import re
from typing import Optional
from langchain_core.tools import tool
from src.config import settings

logger = logging.getLogger(__name__)

@tool
async def generate_image(prompt: str, orientation: Optional[str] = "square") -> str:
    """
    Gera uma imagem de alt\u00edssima qualidade usando o modelo gpt-image-1.5.
    
    O modelo gpt-image-1.5 retorna dados em base64 por padr\u00e3o e n\u00e3o aceita 
    par\u00e2metros de 'quality' ou 'response_format'.
    """
    if not settings.OPENAI_API_KEY:
        return "Erro: OpenAI API Key n\u00e3o configurada."
        
    # --- 1. L\u00f3gica de Orientacao e Frases (No Prompt) ---
    # Como o modelo pode rejeitar o par\u00e2metro 'size' customizado, 
    # injetamos a inten\u00e7\u00e3o de orienta\u00e7\u00e3o no prompt.
    aspect_ratio = "square (1024x1024)"
    if "vertical" in prompt.lower() or orientation == "vertical":
        aspect_ratio = "vertical / portrait (1024x1792)"
    elif "horizontal" in prompt.lower() or orientation == "horizontal":
        aspect_ratio = "horizontal / landscape (1792x1024)"

    # Captura frases entre aspas para destaque
    phrases = re.findall(r'"([^"]*)"', prompt)
    text_context = f" Include the specific text: '{', '.join(phrases)}'." if phrases else ""

    # Prompt Embelezado (Executive Enhancement)
    enhanced_prompt = (
        f"{prompt}. {text_context} Orientation: {aspect_ratio}. "
        "High-end professional photography, cinematic lighting, ultra-detailed, 8k, "
        "executive and modern aesthetic, sharp focus."
    )

    try:    
        url = 'https://api.openai.com/v1/images/generations'
        headers = {
            'Authorization': f'Bearer {settings.OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Payload Simplificado conforme orienta\u00e7\u00e3o da comunidade para gpt-image-1.5
        data = {
            'model': 'gpt-image-1.5',
            'prompt': enhanced_prompt,
            'n': 1
            # Removidos: size, quality, response_format (causam Erro 400 neste modelo)
        }

        logger.info(f"[\ud83d\udca1] Chamando gpt-image-1.5 com prompt: {enhanced_prompt[:50]}...")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=data)
            
            if response.status_code != 200:
                logger.error(f"Erro API OpenAI: {response.text}")
                return f"Falha na API (Status {response.status_code}): {response.text}"
            
            resp_data = response.json()
            # O gpt-image-1.5 retorna base64 por padr\u00e3o no campo b64_json ou url
            img_entry = resp_data["data"][0]
            b64_data = img_entry.get("b64_json") or img_entry.get("url") # Fallback se mudar
            
            if not b64_data:
                return "Falha: O modelo n\u00e3o retornou dados de imagem."

            filename = f"img_{uuid.uuid4().hex[:8]}.png"
            filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)

            # Se for uma URL (raro no 1.5), precisamos baixar. Se for b64, salvamos direto.
            if b64_data.startswith("http"):
                img_res = await client.get(b64_data)
                with open(filepath, "wb") as f:
                    f.write(img_res.content)
            else:
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(b64_data))
            
        return (
            f"Imagem profissional gerada com sucesso via gpt-image-1.5. "
            f"Tag de envio: <SEND_FILE:{filename}>"
        )
    except Exception as e:
        logger.error(f"Erro Cr\u00edtico na Skill de Imagem: {e}")
        return f"Erro na gera\u00e7\u00e3o visual: {str(e)}"
