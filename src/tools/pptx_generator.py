# 🛡️ SKILL BLINDADA (12/03/2026) - AUDITORIA ORION
# Esta skill foi atualizada para suportar BIBLIOTECA DE TEMPLATES PPTX e isolamento de projeto.
import os
import json
import uuid
import logging
import re
import asyncio
from langchain_core.tools import tool
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from src.config import settings
from src.tools.image_generator import generate_image
from typing import Any, Optional, Union
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ─── Manus Executive Design System (Fallback) ──────────────────────────────
_BG     = RGBColor(10,  12,  16)
_CARD   = RGBColor(28,  33,  40)
_ACCENT = RGBColor(88, 166, 255)
_WHITE  = RGBColor(255, 255, 255)
_TEXT   = RGBColor(230, 237, 243)
_MUTED  = RGBColor(110, 118, 129)

_W = Inches(13.333)
_H = Inches(7.5)

def _bg(slide, color=_BG):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color

def _rect(slide, l, t, w, h, color):
    s = slide.shapes.add_shape(1, l, t, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = color
    s.line.fill.background()
    return s

def _add_decorative_elements(slide):
    shape = slide.shapes.add_shape(5, _W - Inches(3), _H - Inches(2), Inches(3), Inches(2))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _CARD
    shape.line.fill.background()
    line = slide.shapes.add_shape(1, Inches(0.5), _H - Inches(0.8), _W - Inches(1), Pt(1))
    line.fill.solid()
    line.fill.fore_color.rgb = _ACCENT

def _text(slide, l, t, w, h, txt, size, bold=False, color=_TEXT, align=PP_ALIGN.LEFT, italic=False):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = str(txt)
    r.font.name = "Calibri"
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    return tb

def _build_cover(prs, title, subtitle=""):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(slide)
    _rect(slide, Inches(0), Inches(2.2), _W, Inches(3.2), _CARD)
    _rect(slide, Inches(0.8), Inches(2.2), Pt(8), Inches(3.2), _ACCENT)
    font_size = 54 if len(title) < 30 else 42
    _text(slide, Inches(1.2), Inches(2.5), Inches(11.0), Inches(1.8), title.upper(), font_size, bold=True, color=_WHITE)
    if subtitle:
        _text(slide, Inches(1.2), Inches(4.3), Inches(10.5), Inches(0.8), subtitle, 22, color=_ACCENT)
    _text(slide, Inches(0.8), _H - Inches(0.6), Inches(8), Inches(0.4), "EXECUTIVE STRATEGY DECK  ·  ARTIFICIALL ELITE", 10, color=_MUTED)

def _build_content(prs, title, bullets, img_path=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(slide)
    _add_decorative_elements(slide)
    _rect(slide, Inches(0), Inches(0), _W, Inches(1.1), _CARD)
    _rect(slide, Inches(0.5), Inches(0.35), Pt(4), Inches(0.4), _ACCENT)
    _text(slide, Inches(0.75), Inches(0.30), Inches(12), Inches(0.6), title.upper(), 28, bold=True, color=_WHITE)

    has_image = False
    if img_path:
        clean_name = str(img_path)
        tag_match = re.search(r'<SEND_FILE:([^>]+)>', clean_name)
        if tag_match: clean_name = tag_match.group(1).strip()
        else: clean_name = clean_name.replace("SEND_FILE:", "").replace("<", "").replace(">", "").strip()
        
        found_path = None
        for v in [clean_name, clean_name.replace("-", "_"), clean_name.replace("_", "-")]:
            fp = os.path.join(settings.DATA_OUTPUTS_PATH, v)
            if os.path.exists(fp):
                found_path = fp
                break
        if found_path:
            try:
                _rect(slide, Inches(0.45), Inches(1.45), Inches(6.1), Inches(5.1), _ACCENT)
                slide.shapes.add_picture(found_path, Inches(0.5), Inches(1.5), width=Inches(6.0), height=Inches(5.0))
                has_image = True
            except: pass

    txt_l = Inches(7.0) if has_image else Inches(1.0)
    txt_w = Inches(5.8) if has_image else Inches(11.3)
    tb = slide.shapes.add_textbox(txt_l, Inches(1.6), txt_w, Inches(5.3))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, bullet in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before, p.space_after, p.level = Pt(18), Pt(4), 0
        r = p.add_run()
        r.text, r.font.bold, r.font.color.rgb = "◈  ", True, _ACCENT
        r2 = p.add_run()
        r2.text, r2.font.size, r2.font.color.rgb = str(bullet), Pt(19), _TEXT

class PpptxSchema(BaseModel):
    slides_content_json: Any = Field(..., description="Conteúdo dos slides em JSON.")
    template_name: Optional[str] = Field(None, description="Nome do template na biblioteca (ex: 'vendas', 'investidores').")

def _get_template_path(template_name: str = None):
    """Busca um template específico ou escolhe um automaticamente da biblioteca."""
    import random
    base_path = os.path.join(settings.BASE_DIR, "data", "templates", "pptx")
    
    if not os.path.exists(base_path):
        os.makedirs(base_path, exist_ok=True)
        return None

    if template_name:
        clean_name = template_name.replace(".pptx", "")
        specific_path = os.path.join(base_path, f"{clean_name}.pptx")
        if os.path.exists(specific_path): return specific_path

    # Seleção Automática (Público)
    templates = [f for f in os.listdir(base_path) if f.endswith(".pptx")]
    if not templates: return None

    # Tenta o mestre primeiro, senão vai no aleatório
    if "template.pptx" in templates:
        return os.path.join(base_path, "template.pptx")
    
    chosen = random.choice(templates)
    logger.info(f"[PPTXGen] 🎲 Template automático para o público: {chosen}")
    return os.path.join(base_path, chosen)

@tool(args_schema=PpptxSchema)
async def generate_pptx(slides_content_json: Any, template_name: str = None) -> str:
    """Gera PPTX Premium com suporte a BIBLIOTECA DE TEMPLATES."""
    if slides_content_json is None:
        slides_content_json = {"title": "Apresentação", "slides": [{"title": "Aviso", "bullets": ["Sem conteúdo."]}]}

    try:
        filename = f"Exec-Deck-{uuid.uuid4().hex[:6]}.pptx"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)

        # Normalização de JSON (Blindagem para Gemini/DeepSeek)
        prs_title, prs_subtitle, slides_data = "EXECUTIVE DECK", "", []
        
        if isinstance(slides_content_json, str):
            # Limpeza de markdown code blocks (```json ... ```)
            clean_json = re.sub(r'```(?:json)?\n?(.*?)\n?```', r'\1', slides_content_json, flags=re.DOTALL).strip()
            try: 
                slides_content_json = json.loads(clean_json)
            except: 
                # Se ainda falhar, tenta extrair o primeiro par de chaves/colchetes
                match = re.search(r'(\{.*\}|\[.*\])', clean_json, re.DOTALL)
                if match:
                    try: slides_content_json = json.loads(match.group(1))
                    except: slides_data = [{"title": "Info", "bullets": [slides_content_json]}]
                else:
                    slides_data = [{"title": "Info", "bullets": [slides_content_json]}]
        
        if isinstance(slides_content_json, dict):
            prs_title = slides_content_json.get("presentation_title", slides_content_json.get("title", "Apresentação"))
            prs_subtitle = slides_content_json.get("subtitle", "")
            slides_data = slides_content_json.get("slides", [])
        elif isinstance(slides_content_json, list):
            # Se a lista já contém dicts com title/content, usa direto
            if slides_content_json and isinstance(slides_content_json[0], dict):
                slides_data = slides_content_json
            else:
                slides_data = [{"title": "Ponto", "bullets": [str(i)]} for i in slides_content_json]

        # Geração
        template_path = _get_template_path(template_name)
        if template_path:
            logger.info(f"[PPTXGen] 📂 Usando template: {template_path}")
            prs = Presentation(template_path)
        else:
            prs = Presentation()
            prs.slide_width, prs.slide_height = _W, _H

        _build_cover(prs, prs_title, prs_subtitle)
        for i, s_data in enumerate(slides_data):
            title = s_data.get("title", f"SLIDE {i+1}")
            bullets = s_data.get("bullets", s_data.get("content", []))
            if isinstance(bullets, str): bullets = [bullets]
            
            img_path = s_data.get("image", s_data.get("img_path"))
            if not img_path:
                for b_idx, bullet in enumerate(bullets):
                    match = re.search(r'<SEND_FILE:(img-[^>]+)>', str(bullet))
                    if match:
                        img_path = match.group(1)
                        bullets[b_idx] = re.sub(r'<SEND_FILE:[^>]+>', '', str(bullet)).strip()
                        break
            
            _build_content(prs, title, bullets, img_path)

        await asyncio.to_thread(prs.save, filepath)
        return f"Apresentação Executiva gerada: <SEND_FILE:{filename}>"
    except Exception as e:
        logger.error(f"[PPTX] Erro: {e}")
        return f"Falha no PPTX: {str(e)}"
