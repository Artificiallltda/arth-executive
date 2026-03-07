import os
import uuid
import httpx
import logging
from langchain_core.tools import tool
from src.config import settings

logger = logging.getLogger(__name__)

@tool
async def generate_audio(text: str, voice: str = "alloy") -> str:
    """
    Gera um \u00e1udio (Voz Humana) a partir de um texto usando a API de TTS da OpenAI.
    
    Use esta ferramenta quando o usu\u00e1rio pedir para "enviar um \u00e1udio", "falar", 
    ou "mandar mensagem de voz".
    
    Par\u00e2metros:
    - text: O texto que ser\u00e1 falado. Deve ser curto e conversacional.
    - voice: O tipo de voz (alloy, echo, fable, onyx, nova, shimmer). Padr\u00e3o: alloy.
    """
    if not settings.OPENAI_API_KEY:
        return "Erro: Chave de API n\u00e3o configurada para TTS."

    try:
        url = 'https://api.openai.com/v1/audio/speech'
        headers = {
            'Authorization': f'Bearer {settings.OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        }
        data = {
            'model': 'tts-1',
            'input': text,
            'voice': voice
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            # Salva o \u00e1udio gerado
            filename = f"audio_{uuid.uuid4().hex[:8]}.mp3"
            filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)

            with open(filepath, "wb") as f:
                f.write(response.content)
            
        return (
            f"O \u00e1udio foi gerado e salvo com sucesso! "
            f"Diga ao usu\u00e1rio que voc\u00ea est\u00e1 enviando o \u00e1udio e cole "
            f"EXATAMENTE esta tag no final da sua resposta: <SEND_AUDIO:{filename}>"
        )
    except Exception as e:
        logger.error(f"Erro na gera\u00e7\u00e3o de \u00e1udio TTS: {e}")
        return f"Falha ao gerar \u00e1udio: {str(e)}"
