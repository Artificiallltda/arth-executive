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


def _build_prompt(prompt: str) -> str:
    phrases = re.findall(r'"([^"]*)"', prompt)
    text_ctx = f" Include this text prominently: '{', '.join(phrases)}'." if phrases else ""
    return (
        f"{prompt}.{text_ctx} "
        "High-end professional photography, cinematic lighting, ultra-detailed, 8k, "
        "executive and modern aesthetic, sharp focus."
    )


def _aspect(prompt: str, orientation: str) -> str:
    if "vertical" in prompt.lower() or orientation == "vertical":
        return "9:16"
    if "horizontal" in prompt.lower() or orientation == "horizontal":
        return "16:9"
    return "1:1"


# ─── Primary: Imagen 3 ───────────────────────────────────────────────────────
def _run_imagen3(enhanced_prompt: str, aspect_ratio: str) -> bytes:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_images(
        model="imagen-3.0-generate-002",
        prompt=enhanced_prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio=aspect_ratio,
            safety_filter_level="BLOCK_ONLY_HIGH",
            person_generation="ALLOW_ADULT",
        ),
    )
    return response.generated_images[0].image.image_bytes


# ─── Fallback: Gemini Flash Image Preview ────────────────────────────────────
def _run_gemini_flash_image(enhanced_prompt: str) -> bytes:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-3.1-flash-image-preview",
        contents=enhanced_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            return base64.b64decode(part.inline_data.data)
    raise ValueError("Fallback: nenhuma imagem retornada pelo modelo.")


@tool
async def generate_image(prompt: str, orientation: Optional[str] = "square") -> str:
    """
    Gera imagem profissional via Imagen 3 (Google).
    Fallback automático para gemini-3.1-flash-image-preview se necessário.
    orientation: 'square' (1:1), 'vertical' (9:16), 'horizontal' (16:9)
    """
    if not settings.GEMINI_API_KEY:
        return "Erro: GEMINI_API_KEY não configurada no ambiente."

    enhanced_prompt = _build_prompt(prompt)
    aspect_ratio = _aspect(prompt, orientation)

    # --- Tentativa 1: Imagen 3 ---
    try:
        logger.info(f"[ImageGen] Imagen 3 | aspect={aspect_ratio} | {enhanced_prompt[:80]}...")
        image_bytes = await asyncio.to_thread(_run_imagen3, enhanced_prompt, aspect_ratio)
        model_used = "Imagen 3"
    except Exception as e1:
        logger.warning(f"[ImageGen] Imagen 3 falhou: {e1}. Tentando fallback...")

        # --- Fallback: Gemini Flash Image Preview ---
        try:
            image_bytes = await asyncio.to_thread(_run_gemini_flash_image, enhanced_prompt)
            model_used = "Gemini Flash Image"
        except Exception as e2:
            logger.error(f"[ImageGen] Fallback também falhou: {e2}", exc_info=True)
            return f"Erro na geração de imagem. Imagen 3: {e1} | Fallback: {e2}"

    filename = f"img_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    logger.info(f"[ImageGen] Salvo via {model_used}: {filename} ({len(image_bytes):,} bytes)")
    return (
        f"Imagem profissional gerada com sucesso via {model_used}. "
        f"Tag de envio: <SEND_FILE:{filename}>"
    )
