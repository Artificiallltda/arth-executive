import os
import uuid
import httpx
import logging
from src.config import settings

logger = logging.getLogger(__name__)

async def transcribe_audio_file(audio_path: str) -> str:
    """
    Usa o modelo Whisper da OpenAI para transcrever um \u00e1udio salvo localmente.
    """
    if not settings.OPENAI_API_KEY:
        return "Erro: Chave de API n\u00e3o configurada para transcri\u00e7\u00e3o."
        
    if not os.path.exists(audio_path):
        return "Erro: Arquivo de \u00e1udio n\u00e3o encontrado."

    try:
        url = 'https://api.openai.com/v1/audio/transcriptions'
        headers = {'Authorization': f'Bearer {settings.OPENAI_API_KEY}'}
        
        # O Whisper exige envio multipart/form-data
        ext = os.path.splitext(audio_path)[1].lower()
        mime_map = {".ogg": "audio/ogg", ".mp3": "audio/mpeg", ".mp4": "audio/mp4", ".wav": "audio/wav", ".webm": "audio/webm"}
        mime_type = mime_map.get(ext, "audio/mpeg")
        with open(audio_path, "rb") as f:
            files = {
                "file": (os.path.basename(audio_path), f, mime_type),
            }
            data = {
                "model": "whisper-1"
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, data=data, files=files)
                response.raise_for_status()
                
                result = response.json()
                return result.get("text", "")
                
    except Exception as e:
        logger.error(f"Falha ao transcrever \u00e1udio: {e}")
        return f"Falha na transcri\u00e7\u00e3o de \u00e1udio: {str(e)}"
