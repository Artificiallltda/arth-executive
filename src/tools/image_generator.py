import os
import uuid
import base64
import logging
import asyncio
import re
from typing import Optional
from langchain_core.tools import tool
from src.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT_S = 60
_TIMEOUT_MS = 60_000

def _build_prompt(prompt: str, orientation: Optional[str]) -> str:
    phrases = re.findall(r'"([^"]*)"', prompt)
    text_ctx = f" Include this text prominently: '{', '.join(phrases)}'." if phrases else ""
    
    aspect_mapping = {
        "vertical": " Aspect Ratio: 9:16 (Vertical format).",
        "horizontal": " Aspect Ratio: 16:9 (Horizontal format).",
        "square": " Aspect Ratio: 1:1 (Square format)."
    }
    
    safe_orientation = (orientation or "square").lower()
    aspect_instruction = aspect_mapping.get(safe_orientation, "")
    
    return (
        f"{prompt}.{text_ctx}{aspect_instruction} "
        "High-end professional photography, cinematic lighting, ultra-detailed, 8k, "
        "executive and modern aesthetic, sharp focus."
    )

def _extract_image_bytes(response) -> tuple[bytes, str]:
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            raw = part.inline_data.data
            mime = getattr(part.inline_data, "mime_type", "image/png") or "image/png"
            if isinstance(raw, str): raw = base64.b64decode(raw)
            return raw, mime
    raise ValueError("Nenhuma imagem retornada (sem inline_data).")

def _ext_from_mime(mime: str) -> str:
    return {"image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}.get(mime, "png")

def _run_gemini_3_image(enhanced_prompt: str) -> tuple[bytes, str]:
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options={"timeout": _TIMEOUT_MS},
    )
    # ATUALIZAÇÃO PARA SÉRIE 3: gemini-3-pro-image-preview
    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=enhanced_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )
    return _extract_image_bytes(response)

@tool
async def generate_image(prompt: str, orientation: Optional[str] = "square") -> str:
    """Gera imagem de luxo via Gemini 3 Series."""
    if not settings.GEMINI_API_KEY: return "Erro: Chave não configurada."

    enhanced_prompt = _build_prompt(prompt, orientation)

    try:
        logger.info(f"[ImageGen-v3] Solicitando imagem via gemini-3-pro-image-preview...")
        image_bytes, mime = await asyncio.wait_for(
            asyncio.to_thread(_run_gemini_3_image, enhanced_prompt),
            timeout=_TIMEOUT_S + 5,
        )
        
        ext = _ext_from_mime(mime)
        filename = f"img-{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
        
        with open(filepath, "wb") as f: f.write(image_bytes)

        logger.info(f"[ImageGen-v3] Sucesso: {filename}")
        return f"Imagem premium gerada: <SEND_FILE:{filename}>"
    except Exception as e:
        logger.error(f"[ImageGen-v3] Erro: {e}")
        return f"Falha na geração da imagem (Série 3): {str(e)}"
