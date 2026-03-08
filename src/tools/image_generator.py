import os
import uuid
import logging
import asyncio
import re
from typing import Optional
from langchain_core.tools import tool
from src.config import settings

logger = logging.getLogger(__name__)


@tool
async def generate_image(prompt: str, orientation: Optional[str] = "square") -> str:
    """
    Gera uma imagem profissional usando Imagen 3 (Google).
    orientation: 'square' (1:1), 'vertical' (9:16), 'horizontal' (16:9)
    """
    if not settings.GEMINI_API_KEY:
        return "Erro: GEMINI_API_KEY não configurada no ambiente."

    # --- Aspect ratio ---
    aspect_ratio = "1:1"
    if "vertical" in prompt.lower() or orientation == "vertical":
        aspect_ratio = "9:16"
    elif "horizontal" in prompt.lower() or orientation == "horizontal":
        aspect_ratio = "16:9"

    # --- Captura frases entre aspas para destaque ---
    phrases = re.findall(r'"([^"]*)"', prompt)
    text_context = f" Include this text prominently: '{', '.join(phrases)}'." if phrases else ""

    enhanced_prompt = (
        f"{prompt}.{text_context} "
        "High-end professional photography, cinematic lighting, ultra-detailed, 8k, "
        "executive and modern aesthetic, sharp focus."
    )

    def _run_imagen():
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

    try:
        logger.info(f"[ImageGen] Gerando via Imagen 3 | aspect={aspect_ratio} | prompt={enhanced_prompt[:80]}...")
        image_bytes = await asyncio.to_thread(_run_imagen)

        filename = f"img_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        logger.info(f"[ImageGen] Salvo: {filename} ({len(image_bytes):,} bytes)")
        return (
            f"Imagem profissional gerada com sucesso via Imagen 3. "
            f"Tag de envio: <SEND_FILE:{filename}>"
        )

    except Exception as e:
        logger.error(f"[ImageGen] Erro: {e}", exc_info=True)
        return f"Erro na geração de imagem: {str(e)}"
