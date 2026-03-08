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
    fill.fore_color.rgb = RGBColor(18, 18, 18)

def _style_run(run, size_pt, bold=False, rgb=RGBColor(255, 255, 255)):
    run.font.name = "Arial"
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = rgb

@tool
async def generate_pptx(slides_content_json: str) -> str:
    """
    Cria uma apresentacao PPTX de luxo. 
    Aceita imagens opcionais por slide se o campo 'image_path' estiver presente.
    """
    try:
        filename = f"Deck_{uuid.uuid4().hex[:6]}.pptx"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
        ACCENT_COLOR = RGBColor(0, 120, 215)

        content = json.loads(slides_content_json)
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        # CAPA
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        _apply_dark_theme(slide)
        tx = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11), Inches(2))
        tf = tx.text_frame
        p = tf.paragraphs[0]
        p.text = content.get("presentation_title", "APRESENTAÇÃO EXECUTIVA").upper()
        _style_run(p.runs[0], 54, True, ACCENT_COLOR)

        # SLIDES
        for s_data in content.get("slides", []):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            _apply_dark_theme(slide)
            
            # Título
            tx_title = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(1))
            p_title = tx_title.text_frame.paragraphs[0]
            p_title.text = s_data.get("title", "").upper()
            _style_run(p_title.runs[0], 32, True, ACCENT_COLOR)

            # Imagem (se houver) -> Layout Side-by-Side
            img_path = s_data.get("image_path")
            has_image = False
            if img_path:
                full_img_path = os.path.join(settings.DATA_OUTPUTS_PATH, img_path.replace("<SEND_FILE:", "").replace(">", ""))
                if os.path.exists(full_img_path):
                    slide.shapes.add_picture(full_img_path, Inches(7), Inches(1.5), height=Inches(5))
                    has_image = True

            # Texto
            width = Inches(6) if has_image else Inches(11)
            tx_body = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), width, Inches(5))
            tf_body = tx_body.text_frame
            tf_body.word_wrap = True
            
            for i, bullet in enumerate(s_data.get("bullets", [])):
                p = tf_body.paragraphs[0] if i == 0 else tf_body.add_paragraph()
                p.text = f"• {bullet}"
                _style_run(p.runs[0], 20, rgb=RGBColor(220, 220, 220))
                p.space_after = Pt(12)

        prs.save(filepath)
        return f"Apresentação Premium gerada: <SEND_FILE:{filename}>"
    except Exception as e:
        logger.error(f"Erro PPTX: {e}")
        return f"Falha no PPTX: {str(e)}"
