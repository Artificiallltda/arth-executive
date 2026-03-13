import os
import uuid
import base64
import logging
import asyncio
import re
from typing import Optional
from langchain_core.tools import tool
from config import settings

logger = logging.getLogger(__name__)

_TIMEOUT_S = 50   # timeout asyncio em segundos
_TIMEOUT_MS = 50_000  # mesmo timeout para http_options (SDK usa milissegundos)


def _build_prompt(prompt: str) -> str:
    phrases = re.findall(r'"([^"]*)"', prompt)
    text_ctx = f" Include this text prominently: '{', '.join(phrases)}'." if phrases else ""
    return (
        f"{prompt}.{text_ctx} "
        "High-end professional photography, cinematic lighting, ultra-detailed, 8k, "
        "executive and modern aesthetic, sharp focus."
    )


def _extract_image_bytes(response) -> tuple[bytes, str]:
    """
    Extrai bytes de imagem e mime_type de uma resposta generate_content.
    google-genai >= 1.0 retorna inline_data.data como bytes (não base64).
    Trata ambos os casos para compatibilidade.
    """
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            raw = part.inline_data.data
            mime = getattr(part.inline_data, "mime_type", "image/png") or "image/png"
            if isinstance(raw, str):
                raw = base64.b64decode(raw)
            return raw, mime
    raise ValueError("Nenhuma imagem retornada pelo modelo (sem inline_data).")


def _ext_from_mime(mime: str) -> str:
    return {"image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}.get(mime, "png")


def _run_flash_image(enhanced_prompt: str) -> tuple[bytes, str]:
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options={"timeout": _TIMEOUT_MS},
    )
    response = client.models.generate_content(
        model="gemini-3.1-flash-image-preview",
        contents=enhanced_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )
    return _extract_image_bytes(response)


def _run_gemini_25_flash(enhanced_prompt: str) -> tuple[bytes, str]:
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options={"timeout": _TIMEOUT_MS},
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=enhanced_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )
    return _extract_image_bytes(response)


@tool
async def generate_image(prompt: str, orientation: Optional[str] = "square") -> str:
    """
    Gera imagem profissional via Gemini (Google).
    Primary: gemini-3.1-flash-image-preview.
    Fallback: gemini-2.5-flash.
    orientation: 'square' (1:1), 'vertical' (9:16), 'horizontal' (16:9)
    """
    if not settings.GEMINI_API_KEY:
        return "Erro: GEMINI_API_KEY não configurada no ambiente."

    enhanced_prompt = _build_prompt(prompt)

    # --- Tentativa 1: gemini-3.1-flash-image-preview ---
    try:
        logger.info(f"[ImageGen] Tentando gemini-3.1-flash-image-preview | {enhanced_prompt[:80]}...")
        image_bytes, mime = await asyncio.wait_for(
            asyncio.to_thread(_run_flash_image, enhanced_prompt),
            timeout=_TIMEOUT_S + 5,
        )
        model_used = "gemini-3.1-flash-image-preview"
        logger.info(f"[ImageGen] flash-image-preview OK: {len(image_bytes):,} bytes, mime={mime}")
    except Exception as e1:
        logger.warning(f"[ImageGen] flash-image-preview falhou ({type(e1).__name__}: {e1}). Tentando gemini-2.5-flash...")

        # --- Fallback: gemini-2.5-flash ---
        try:
            image_bytes, mime = await asyncio.wait_for(
                asyncio.to_thread(_run_gemini_25_flash, enhanced_prompt),
                timeout=_TIMEOUT_S + 5,
            )
            model_used = "gemini-2.5-flash"
            logger.info(f"[ImageGen] gemini-2.5-flash OK: {len(image_bytes):,} bytes, mime={mime}")
        except Exception as e2:
            logger.error(f"[ImageGen] Ambos falharam. flash-image: {type(e1).__name__}:{e1} | 2.5-flash: {type(e2).__name__}:{e2}")
            return f"Erro na geração de imagem. flash-image-preview: {e1} | gemini-2.5-flash: {e2}"

    ext = _ext_from_mime(mime)
    filename = f"img-{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    logger.info(f"[ImageGen] Salvo via {model_used}: {filename} ({len(image_bytes):,} bytes)")
    return (
        f"Imagem gerada com sucesso via {model_used}. "
        f"ID para uso: SEND_FILE:{filename}. "
        "Se quiser enviar esta imagem diretamente ao usuário, você DEVE incluir a tag <SEND_FILE:" + filename + "> na sua resposta final."
    )
