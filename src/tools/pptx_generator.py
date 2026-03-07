import os
import json
import uuid
import logging
import base64
import httpx
import traceback
from langchain_core.tools import tool
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR
from src.config import settings

logger = logging.getLogger(__name__)

def _apply_dark_theme(slide):
    """Aplica fundo escuro moderno (Dark Mode) em um slide específico."""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(33, 37, 41)

def _style_run(run, size_pt, bold=False, rgb=RGBColor(255, 255, 255)):
    """Formata a fonte de um fragmento de texto."""
    run.font.name = "Segoe UI"
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = rgb

@tool
async def generate_pptx(slides_content_json: str) -> str:
    """Cria uma apresentacao de Slides (.pptx) com design moderno."""
    try:
        filename = f"Apresentacao_{uuid.uuid4().hex[:6]}.pptx"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
        
        # Cor de Destaque: Azul AIOS (RGB: 0, 122, 255)
        ACCENT_COLOR = RGBColor(0, 122, 255)

        try:
            content = json.loads(slides_content_json)
        except Exception as e:
            return f"Erro de JSON: {e}"

        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        
        presentation_title = content.get("presentation_title", "Apresentacao")
        slides = content.get("slides", [])

        # CAPA
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        _apply_dark_theme(slide)
        title_shape = slide.shapes.title
        title_shape.text = presentation_title
        paras = title_shape.text_frame.paragraphs
        if paras and paras[0].runs:
            _style_run(paras[0].runs[0], size_pt=54, bold=True, rgb=ACCENT_COLOR)

        # SLIDES
        for slide_data in slides:
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            _apply_dark_theme(slide)
            
            title_shape = slide.shapes.title
            title_shape.text = slide_data.get("title", "")
            paras = title_shape.text_frame.paragraphs
            if paras and paras[0].runs:
                _style_run(paras[0].runs[0], size_pt=40, bold=True, rgb=ACCENT_COLOR)
            
            body_shape = slide.placeholders[1]
            tf = body_shape.text_frame
            for i, bullet in enumerate(slide_data.get("bullets", [])):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.text = str(bullet)
                if p.runs: _style_run(p.runs[0], size_pt=24, rgb=RGBColor(200, 200, 200))

        prs.save(filepath)
        return f"Apresentacao PPTX gerada: <SEND_FILE:{filename}>"
    except Exception as e:
        return f"Erro no PPTX: {e}"
