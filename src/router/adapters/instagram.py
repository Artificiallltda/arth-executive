import logging
import httpx
import os
import re
from src.config import settings

logger = logging.getLogger(__name__)

async def send_instagram_message(recipient_id: str, text: str):
    """Envia mensagem de texto via Instagram Messaging API (Meta Direct)."""
    if not settings.INSTAGRAM_ACCESS_TOKEN:
        logger.warning(f"[Mock] Instagram Direct para {recipient_id}: {text}")
        return
        
    url = f"https://graph.facebook.com/{settings.META_API_VERSION}/me/messages"
    headers = {"Authorization": f"Bearer {settings.INSTAGRAM_ACCESS_TOKEN}"}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=15.0)
            if response.status_code != 200:
                logger.error(f"Erro Meta API Instagram ({response.status_code}): {response.text}")
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem Instagram Meta API: {e}")

async def process_instagram_reply(recipient_id: str, ai_response: str):
    """Processa a resposta da IA e envia para o usuário no Instagram via Meta."""
    # Remove tags especiais caso existam
    clean_text = re.sub(r'`?<SEND_FILE:[^>]+>`?', '', ai_response)
    clean_text = re.sub(r'`?<SEND_AUDIO:[^>]+>`?', '', clean_text).strip()
    
    if clean_text:
        await send_instagram_message(recipient_id, clean_text)
    
    # Nota: O envio de mídias via Graph API exige que o arquivo esteja em um link público (URL) 
    # ou enviado via pipeline de upload específico. Por hora, focamos no texto.
