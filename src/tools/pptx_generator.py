# 🛡️ SKILL BLINDADA (14/03/2026) - PADRÃO MANUS AI
import os
import json
import uuid
import logging
import re
import asyncio
import sys
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

# ─── CONFIGURAÇÃO DE CAMINHOS ABSOLUTOS (MANUS STYLE) ───────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # src/tools
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR)) # arth-executive
TEMPLATES_DIR = os.getenv("TEMPLATES_DIR", os.path.join(PROJECT_ROOT, "data", "templates", "pptx"))

# ─── Manus Executive Design System (Fallback) ──────────────────────────────
_BG, _CARD, _ACCENT = RGBColor(10, 12, 16), RGBColor(28, 33, 40), RGBColor(88, 166, 255)
_WHITE, _TEXT, _MUTED = RGBColor(255, 255, 255), RGBColor(230, 237, 243), RGBColor(110, 118, 129)
_W, _H = Inches(13.333), Inches(7.5)

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
        # Limpeza e busca de imagem
        clean_name = re.sub(r'<[^>]+>', '', str(img_path)).replace("SEND_FILE:", "").replace("img:", "").strip()
        fp = os.path.join(settings.DATA_OUTPUTS_PATH, clean_name)
        if os.path.exists(fp):
            try:
                temp_pic = slide.shapes.add_picture(fp, 0, 0)
                orig_w, orig_h = temp_pic.width, temp_pic.height
                max_w, max_h = Inches(6.0), Inches(5.0)
                scale = min(max_w / orig_w, max_h / orig_h)
                new_w, new_h = int(orig_w * scale), int(orig_h * scale)
                left, top = Inches(0.5) + int((max_w - new_w) / 2), Inches(1.5) + int((max_h - new_h) / 2)
                shape_obj = temp_pic._element
                shape_obj.getparent().remove(shape_obj)
                _rect(slide, left - Pt(2), top - Pt(2), new_w + Pt(4), new_h + Pt(4), _ACCENT)
                slide.shapes.add_picture(fp, left, top, width=new_w, height=new_h)
                has_image = True
            except Exception as e: logger.error(f"[PPTXGen] Erro imagem: {e}")

    txt_l, txt_w = (Inches(7.0), Inches(5.8)) if has_image else (Inches(1.0), Inches(11.3))
    tb = slide.shapes.add_textbox(txt_l, Inches(1.6), txt_w, Inches(5.3))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, bullet in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before, p.space_after, p.level = Pt(18), Pt(4), 0
        r = p.add_run(); r.text, r.font.bold, r.font.color.rgb = "◈  ", True, _ACCENT
        r2 = p.add_run(); r2.text, r2.font.size, r2.font.color.rgb = str(bullet), Pt(19), _TEXT

def _get_template_path(template_name: str = None):
    """Busca um template de forma ABSOLUTA e INTELIGENTE (Manus AI Pathing)."""
    logger.info(f"🔍 [PPTXGen] Buscando template para: '{template_name}' em {TEMPLATES_DIR}")
    
    if not os.path.exists(TEMPLATES_DIR):
        logger.warning(f"⚠️ [PPTXGen] Pasta de templates não existe: {TEMPLATES_DIR}")
        os.makedirs(TEMPLATES_DIR, exist_ok=True)
        return None

    templates = [f for f in os.listdir(TEMPLATES_DIR) if f.endswith(".pptx")]
    
    if template_name:
        clean_query = str(template_name).lower().replace(".pptx", "").strip()
        # 1. Nome exato
        target = f"{clean_query}.pptx"
        if target in [t.lower() for t in templates]:
            path = os.path.join(TEMPLATES_DIR, target)
            logger.info(f"✅ [PPTXGen] Template exato encontrado: {path}")
            return path
        
        # 2. Prefixo template_
        target_pref = f"template_{clean_query}.pptx"
        if target_pref in [t.lower() for t in templates]:
            path = os.path.join(TEMPLATES_DIR, target_pref)
            logger.info(f"✅ [PPTXGen] Template com prefixo encontrado: {path}")
            return path

        # 3. Fuzzy Match (contém)
        for t in templates:
            if clean_query in t.lower():
                path = os.path.join(TEMPLATES_DIR, t)
                logger.info(f"✅ [PPTXGen] Template parcial encontrado: {path}")
                return path

    # FALLBACK AUTOMÁTICO (MANUS AI)
    fallback_path = os.path.join(TEMPLATES_DIR, "template_apresentacao.pptx")
    if os.path.exists(fallback_path):
        logger.info(f"💡 [PPTXGen] Usando fallback padrão: {fallback_path}")
        return fallback_path
    
    if templates:
        path = os.path.join(TEMPLATES_DIR, templates[0])
        logger.info(f"🎲 [PPTXGen] Usando primeiro template disponível: {path}")
        return path

    logger.warning("❌ [PPTXGen] Nenhum template encontrado. Usando design via código.")
    return None

class PpptxSchema(BaseModel):
    slides_content_json: Any = Field(..., description="Conteúdo dos slides em JSON.")
    template_name: Optional[str] = Field(None, description="Nome do template.")

@tool(args_schema=PpptxSchema)
async def generate_pptx(slides_content_json: Any, template_name: str = None) -> str:
    """Gera PPTX Premium com CAMINHOS ABSOLUTOS e FALLBACKS."""
    try:
        filename = f"Exec-Deck-{uuid.uuid4().hex[:6]}.pptx"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)

        # Normalização de JSON
        prs_title, prs_subtitle, slides_data = "EXECUTIVE DECK", "", []
        if isinstance(slides_content_json, str):
            clean_json = re.sub(r'```(?:json)?\n?(.*?)\n?```', r'\1', slides_content_json, flags=re.DOTALL).strip()
            try: slides_content_json = json.loads(clean_json)
            except: 
                match = re.search(r'(\{.*\}|\[.*\])', clean_json, re.DOTALL)
                slides_content_json = json.loads(match.group(1)) if match else {}

        if isinstance(slides_content_json, dict):
            prs_title = slides_content_json.get("title", "Apresentação")
            prs_subtitle = slides_content_json.get("subtitle", "")
            slides_data = slides_content_json.get("slides", [])

        # Geração
        template_path = _get_template_path(template_name)
        prs = Presentation(template_path) if template_path else Presentation()
        if not template_path: prs.slide_width, prs.slide_height = _W, _H

        _build_cover(prs, prs_title, prs_subtitle)
        for i, s_data in enumerate(slides_data):
            title = s_data.get("title", f"SLIDE {i+1}")
            bullets = s_data.get("bullets", s_data.get("content", []))
            if isinstance(bullets, str): bullets = [bullets]
            img_path = s_data.get("image", s_data.get("img_path"))
            _build_content(prs, title, bullets, img_path)

        await asyncio.to_thread(prs.save, filepath)
        return f"Apresentação Executiva gerada: <SEND_FILE:{filename}>"
    except Exception as e:
        logger.error(f"[PPTX] Erro: {e}")
        return f"Falha no PPTX: {str(e)}"
