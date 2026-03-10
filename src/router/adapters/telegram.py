import logging
import httpx
import os
import re
import asyncio
from src.config import settings

logger = logging.getLogger(__name__)

async def send_telegram_message(chat_id: str, text: str):
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning(f"[Mock] Telegram para {chat_id}: {text}")
        return
        
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    # Mudança para HTML: mais estável que Markdown para dados da web
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=15.0)
            if resp.status_code != 200:
                logger.warning(f"[Telegram] Falha no envio HTML (Status {resp.status_code}). Tentando texto simples...")
                payload.pop("parse_mode", None)
                await client.post(url, json=payload, timeout=15.0)
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem Telegram API: {e}")

async def download_telegram_file(file_id: str, dest_filename: str) -> str:
    """Baixa um arquivo dos servidores do Telegram."""
    if not settings.TELEGRAM_BOT_TOKEN: return None
    
    async with httpx.AsyncClient() as client:
        # 1. Get File Path
        get_file_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
        resp = await client.get(get_file_url)
        if resp.status_code != 200: return None
        
        file_path = resp.json().get("result", {}).get("file_path")
        if not file_path: return None
        
        # 2. Download
        download_url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
        dest_path = os.path.join(settings.DATA_OUTPUTS_PATH, dest_filename)
        
        resp_file = await client.get(download_url)
        if resp_file.status_code == 200:
            with open(dest_path, "wb") as f:
                f.write(resp_file.content)
            return dest_path
    return None

async def safe_send_file(chat_id: str, file_path: str, caption: str = ""):
    """Envia arquivo apenas se existir e não estiver vazio, com retry interno blindado."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return False
        
    if not file_path:
        logger.error("[Telegram] safe_send_file: caminho nulo.")
        return False

    # Verificação de integridade com retry (Orion Wait)
    file_ready = False
    for attempt in range(5):
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            logger.info(f"[Telegram] ✅ Arquivo pronto para envio (tentativa {attempt+1}): {file_path} ({os.path.getsize(file_path)} bytes)")
            file_ready = True
            break
        else:
            logger.warning(f"[Telegram] ⏳ Arquivo não encontrado ou vazio (tentativa {attempt+1}/5). Aguardando disco...")
            await asyncio.sleep(0.6)
            
    if not file_ready:
        logger.error(f"[Telegram] ❌ Abortando envio: Arquivo não apareceu no disco: {file_path}")
        await send_telegram_message(chat_id, "❌ O arquivo solicitado não pôde ser gerado (falha de escrita). Tente novamente.")
        return False
        
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendDocument"
    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"document": (os.path.basename(file_path), f)}
                data = {"chat_id": str(chat_id), "caption": caption or f"✅ Documento Gerado ({os.path.getsize(file_path)} bytes)"}
                resp = await client.post(url, data=data, files=files, timeout=45.0)
                if resp.status_code == 200:
                    logger.info(f"[Telegram] ✅ Arquivo entregue com sucesso: {file_path}")
                    return True
                else:
                    logger.error(f"[Telegram] ❌ Erro API Telegram ({resp.status_code}): {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"[Telegram] ❌ Erro no envio: {str(e)}")
            return False

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
                resp = await client.post(url, data=data, files=files, timeout=30.0)
                if resp.status_code != 200:
                    logger.error(f"[Telegram] sendPhoto falhou: {resp.status_code} - {resp.text[:300]}")
                else:
                    logger.info(f"[Telegram] Foto enviada com sucesso para {chat_id}")
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
            await safe_send_file(chat_id, full_path)

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

