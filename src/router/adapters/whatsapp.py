import logging
import httpx
import base64
import os
import re
from src.config import settings

logger = logging.getLogger(__name__)

async def send_whatsapp_message(remote_jid: str, text: str):
    if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_API_KEY:
        logger.warning(f"[Mock] Whatsapp para {remote_jid}: {text}")
        return
        
    url = f"{settings.EVOLUTION_API_URL}/message/sendText/{settings.INSTANCE_NAME}"
    headers = {"apikey": settings.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"number": remote_jid, "options": {"delay": 1200, "presence": "composing"}, "textMessage": {"text": text}}
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=payload, headers=headers, timeout=10.0)
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem Evolution API: {e}")

async def send_whatsapp_media(remote_jid: str, file_path: str, caption: str = ""):
    if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_API_KEY:
        return
    if not os.path.exists(file_path):
        logger.error(f"Arquivo não encontrado para envio: {file_path}")
        return
        
    is_image = file_path.lower().endswith((".png", ".jpg", ".jpeg"))
    endpoint = "sendImage" if is_image else "sendMedia"
    
    url = f"{settings.EVOLUTION_API_URL}/message/{endpoint}/{settings.INSTANCE_NAME}"
    headers = {"apikey": settings.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    
    with open(file_path, "rb") as f:
        media_base64 = base64.b64encode(f.read()).decode("utf-8")
        
    if is_image:
        ext = os.path.splitext(file_path)[1].lower()
        img_mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
        payload = {
            "number": remote_jid,
            "options": {"delay": 1200, "presence": "composing"},
            "imageMessage": {
                "image": f"data:{img_mime};base64,{media_base64}",
                "caption": caption
            }
        }
    else:
        payload = {
            "number": remote_jid,
            "options": {"delay": 1200, "presence": "composing"},
            "mediaMessage": {
                "mediatype": "document",
                "fileName": os.path.basename(file_path),
                "caption": caption,
                "media": f"data:application/octet-stream;base64,{media_base64}"
            }
        }
        
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload, headers=headers, timeout=30.0)
            logger.info(f"Evolution API {endpoint} result: {r.status_code}")
        except Exception as e:
            logger.error(f"Falha ao enviar mídia Evolution: {e}")

async def process_whatsapp_reply(remote_jid: str, ai_response: str):
    # Extrai tags de envio de arquivo e limpa o texto
    file_matches = re.findall(r'<SEND_FILE:([^>]+)>', ai_response)
    audio_matches = re.findall(r'<SEND_AUDIO:([^>]+)>', ai_response)
    
    clean_text = re.sub(r'`?<SEND_FILE:[^>]+>`?', '', ai_response)
    clean_text = re.sub(r'`?<SEND_AUDIO:[^>]+>`?', '', clean_text).strip()
    
    if clean_text:
        await send_whatsapp_message(remote_jid, clean_text)
        
    for file_name in file_matches:
        full_path = os.path.join(settings.DATA_OUTPUTS_PATH, file_name.strip())
        await send_whatsapp_media(remote_jid, full_path)
        
    for audio_name in audio_matches:
        full_path = os.path.join(settings.DATA_OUTPUTS_PATH, audio_name.strip())
        # Para WhatsApp, enviamos o \u00e1udio como mensagem de voz ptt (push-to-talk)
        await send_whatsapp_audio(remote_jid, full_path)

async def send_whatsapp_audio(remote_jid: str, file_path: str):
    if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_API_KEY: return
    if not os.path.exists(file_path): return
        
    with open(file_path, "rb") as f:
        media_base64 = base64.b64encode(f.read()).decode("utf-8")
        
    url = f"{settings.EVOLUTION_API_URL}/message/sendWhatsAppAudio/{settings.INSTANCE_NAME}"
    headers = {"apikey": settings.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {
        "number": remote_jid,
        "options": {"delay": 1500, "presence": "recording"},
        "audioMessage": {
            "audio": f"data:audio/mpeg;base64,{media_base64}"
        }
    }
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=payload, headers=headers, timeout=30.0)
        except Exception as e:
            logger.error(f"Falha ao enviar audio Evolution: {e}")

