import logging
import httpx
import base64
import os
import re
from src.config import settings

logger = logging.getLogger(__name__)

async def send_instagram_message(remote_jid: str, text: str):
    """Envia mensagem de texto para Instagram via Evolution API."""
    if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_API_KEY:
        logger.warning(f"[Mock] Instagram para {remote_jid}: {text}")
        return
        
    url = f"{settings.EVOLUTION_API_URL}/chat/sendInstagramText/{settings.INSTANCE_NAME}"
    headers = {"apikey": settings.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {
        "number": remote_jid, 
        "text": text
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=10.0)
            if response.status_code != 201:
                logger.error(f"Erro Evolution API Instagram ({response.status_code}): {response.text}")
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem Instagram Evolution API: {e}")

async def process_instagram_reply(remote_jid: str, ai_response: str):
    """Processa a resposta da IA e envia para o usuário no Instagram."""
    # Como Instagram via Evolution API pode ter limitações com arquivos/áudio em algumas versões, 
    # por enquanto focaremos no envio de texto limpo.
    
    file_matches = re.findall(r'<SEND_FILE:([^>]+)>', ai_response)
    audio_matches = re.findall(r'<SEND_AUDIO:([^>]+)>', ai_response)
    
    clean_text = re.sub(r'`?<SEND_FILE:[^>]+>`?', '', ai_response)
    clean_text = re.sub(r'`?<SEND_AUDIO:[^>]+>`?', '', clean_text).strip()
    
    if clean_text:
        await send_instagram_message(remote_jid, clean_text)
        
    if file_matches or audio_matches:
        logger.warning(f"[Instagram] Envio de arquivos/áudio ainda não suportado nativamente. Ignorando attachments.")
