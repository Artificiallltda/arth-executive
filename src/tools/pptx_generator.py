import os
import json
import uuid
import logging
from langchain_core.tools import tool
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from src.config import settings

logger = logging.getLogger(__name__)

def _apply_dark_theme(slide):
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(10, 10, 12) # Ultra Dark

def _style_run(run, size_pt, bold=False, rgb=RGBColor(255, 255, 255)):
    run.font.name = "Impact" # Fonte bem diferente para teste visual
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = rgb

@tool
async def generate_pptx(slides_content_json: str) -> str:
    """Gera uma apresentação de APRESENTAÇÃO DE ELITE com layout moderno."""
    try:
        filename = f"Elite_Deck_{uuid.uuid4().hex[:6]}.pptx"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
        GOLD_COLOR = RGBColor(255, 215, 0) # Mudar para Dourado para teste visual claro

        content = json.loads(slides_content_json)
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        # CAPA
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        _apply_dark_theme(slide)
        tx = slide.shapes.add_textbox(Inches(1), Inches(3), Inches(11), Inches(2))
        p = tx.text_frame.paragraphs[0]
        p.text = str(content.get("presentation_title", "ELITE EXECUTIVE")).upper()
        _style_run(p.runs[0], 60, True, GOLD_COLOR)

        # SLIDES
        for s_data in content.get("slides", []):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            _apply_dark_theme(slide)
            
            # Título Lateral ou Superior
            tx_title = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12), Inches(1))
            p_title = tx_title.text_frame.paragraphs[0]
            p_title.text = str(s_data.get("title", "")).upper()
            _style_run(p_title.runs[0], 40, True, GOLD_COLOR)

            img_path = s_data.get("image_path")
            has_image = False
            if img_path:
                clean_path = str(img_path).replace("<SEND_FILE:", "").replace(">", "").strip()
                full_img_path = os.path.join(settings.DATA_OUTPUTS_PATH, clean_path)
                if os.path.exists(full_img_path):
                    # Forçar imagem na esquerda para testar mudança de layout
                    slide.shapes.add_picture(full_img_path, Inches(0.5), Inches(1.5), width=Inches(6), height=Inches(5))
                    has_image = True

            # Texto (Sempre na direita se houver imagem)
            left_pos = Inches(7) if has_image else Inches(1)
            tx_body = slide.shapes.add_textbox(left_pos, Inches(1.5), Inches(5.5), Inches(5))
            tf_body = tx_body.text_frame
            tf_body.word_wrap = True
            
            for i, bullet in enumerate(s_data.get("bullets", [])):
                p = tf_body.paragraphs[0] if i == 0 else tf_body.add_paragraph()
                p.text = f"▶ {bullet}"
                if p.runs:
                    _style_run(p.runs[0], 24, rgb=RGBColor(230, 230, 230))
                p.space_after = Pt(20)

        prs.save(filepath)
        return f"Apresentação ELITE gerada: <SEND_FILE:{filename}>"
    except Exception as e:
        logger.error(f"Erro PPTX: {e}")
        return f"Falha no PPTX: {str(e)}"
