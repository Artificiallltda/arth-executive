import logging
import httpx
import os
import re
from src.config import settings

logger = logging.getLogger(__name__)

async def send_telegram_message(chat_id: str, text: str):
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning(f"[Mock] Telegram para {chat_id}: {text}")
        return
        
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=payload, timeout=10.0)
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem Telegram API: {e}")

async def send_telegram_document(chat_id: str, file_path: str):
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    if not os.path.exists(file_path):
        logger.error(f"Documento n\u00e3o encontrado para envio: {file_path}")
        return
        
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendDocument"
    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"document": (os.path.basename(file_path), f)}
                data = {"chat_id": chat_id}
                await client.post(url, data=data, files=files, timeout=30.0)
        except Exception as e:
            logger.error(f"Falha ao enviar documento Telegram API: {e}")

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

async def send_telegram_photo(chat_id: str, file_path: str):
    """Envia imagem com preview nativo via sendPhoto API."""
    if not settings.TELEGRAM_BOT_TOKEN: return
    if not os.path.exists(file_path):
        logger.error(f"Imagem não encontrada para envio: {file_path}")
        return

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPhoto"
    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"photo": (os.path.basename(file_path), f)}
                data = {"chat_id": chat_id}
                await client.post(url, data=data, files=files, timeout=30.0)
        except Exception as e:
            logger.error(f"Falha ao enviar foto Telegram: {e}")

async def process_telegram_reply(chat_id: str, ai_response: str):
    file_matches = re.findall(r'<SEND_FILE:([^>]+)>', ai_response)
    audio_matches = re.findall(r'<SEND_AUDIO:([^>]+)>', ai_response)

    clean_text = re.sub(r'`?<SEND_FILE:[^>]+>`?', '', ai_response)
    clean_text = re.sub(r'`?<SEND_AUDIO:[^>]+>`?', '', clean_text).strip()

    if clean_text:
        await send_telegram_message(chat_id, clean_text)

    for file_name in file_matches:
        full_path = os.path.join(settings.DATA_OUTPUTS_PATH, file_name.strip())
        ext = os.path.splitext(file_name.strip())[1].lower()
        if ext in IMAGE_EXTENSIONS:
            await send_telegram_photo(chat_id, full_path)
        else:
            await send_telegram_document(chat_id, full_path)

    for audio_name in audio_matches:
        full_path = os.path.join(settings.DATA_OUTPUTS_PATH, audio_name.strip())
        await send_telegram_audio(chat_id, full_path)

async def send_telegram_audio(chat_id: str, file_path: str):
    """Envia áudio: sendVoice para OGG/Opus, sendAudio para MP3 e outros formatos."""
    if not settings.TELEGRAM_BOT_TOKEN: return
    if not os.path.exists(file_path): return

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".ogg":
        endpoint = "sendVoice"
        file_key = "voice"
    else:
        # MP3, AAC, M4A, FLAC etc. → sendAudio (player de música no Telegram)
        endpoint = "sendAudio"
        file_key = "audio"

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{endpoint}"
    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {file_key: (os.path.basename(file_path), f)}
                data = {"chat_id": chat_id}
                await client.post(url, data=data, files=files, timeout=30.0)
        except Exception as e:
            logger.error(f"Falha ao enviar audio Telegram ({endpoint}): {e}")

