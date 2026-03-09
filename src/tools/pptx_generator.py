import os
import json
import uuid
import logging
import re
from langchain_core.tools import tool
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from src.config import settings

logger = logging.getLogger(__name__)

# ─── Manus Executive Design System ──────────────────────────────────────────
# Paleta: Dark Navy + Cobalt Blue — limpo, profissional, moderno
_BG     = RGBColor(10,  12,  16)   # Quase preto profundo
_CARD   = RGBColor(28,  33,  40)   # Cinza azulado escuro para elementos
_ACCENT = RGBColor(88, 166, 255)   # Azul cobalto brilhante (Electric Blue)
_WHITE  = RGBColor(255, 255, 255)  # Branco puro
_TEXT   = RGBColor(230, 237, 243)  # Off-white para leitura
_MUTED  = RGBColor(110, 118, 129)  # Cinza médio para detalhes

_W = Inches(13.333)
_H = Inches(7.5)


def _bg(slide, color=_BG):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _rect(slide, l, t, w, h, color, alpha=1.0):
    """Adiciona retângulo colorido."""
    s = slide.shapes.add_shape(1, l, t, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = color
    s.line.fill.background() # sem borda
    return s


def _add_decorative_elements(slide):
    """Adiciona formas geométricas sutis para visual premium."""
    # Triângulo decorativo no canto inferior direito
    shape = slide.shapes.add_shape(5, _W - Inches(3), _H - Inches(2), Inches(3), Inches(2))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _CARD
    shape.line.fill.background()
    
    # Linha fina de acento
    line = slide.shapes.add_shape(1, Inches(0.5), _H - Inches(0.8), _W - Inches(1), Pt(1))
    line.fill.solid()
    line.fill.fore_color.rgb = _ACCENT


def _text(slide, l, t, w, h, txt, size, bold=False, color=_TEXT,
          align=PP_ALIGN.LEFT, italic=False):
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

    # Grande retângulo central de destaque (levemente mais alto para títulos longos)
    _rect(slide, Inches(0), Inches(2.2), _W, Inches(3.2), _CARD)
    
    # Barra vertical de acento
    _rect(slide, Inches(0.8), Inches(2.2), Pt(8), Inches(3.2), _ACCENT)

    # Título principal - Ajuste dinâmico de fonte para títulos longos
    font_size = 54 if len(title) < 30 else 42
    _text(slide, Inches(1.2), Inches(2.5), Inches(11.0), Inches(1.8),
          title.upper(), font_size, bold=True, color=_WHITE)

    # Subtítulo - Posicionado mais abaixo para não colidir
    if subtitle:
        _text(slide, Inches(1.2), Inches(4.3), Inches(10.5), Inches(0.8),
              subtitle, 22, color=_ACCENT)

    # Footer decorativo
    _text(slide, Inches(0.8), _H - Inches(0.6), Inches(8), Inches(0.4),
          "EXECUTIVE STRATEGY DECK  ·  MANUS AI PRO", 10, color=_MUTED)


def _build_content(prs, title, bullets, img_path=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(slide)
    _add_decorative_elements(slide)

    # Header moderno
    _rect(slide, Inches(0), Inches(0), _W, Inches(1.1), _CARD)
    _rect(slide, Inches(0.5), Inches(0.35), Pt(4), Inches(0.4), _ACCENT)
    
    _text(slide, Inches(0.75), Inches(0.30), Inches(12), Inches(0.6),
          title.upper(), 28, bold=True, color=_WHITE)

    # Imagem
    has_image = False
    if img_path:
        clean_name = str(img_path)
        tag_match = re.search(r'<SEND_FILE:([^>]+)>', clean_name)
        if tag_match:
            clean_name = tag_match.group(1).strip()
        else:
            clean_name = clean_name.replace("SEND_FILE:", "").replace("<", "").replace(">", "").strip()

        variants = [clean_name, clean_name.replace("-", "_"), clean_name.replace("_", "-")]
        found_path = None
        for v in variants:
            fp = os.path.join(settings.DATA_OUTPUTS_PATH, v)
            if os.path.exists(fp):
                found_path = fp
                break

        if found_path:
            try:
                # Moldura da imagem (Premium Look)
                _rect(slide, Inches(0.45), Inches(1.45), Inches(6.1), Inches(5.1), _ACCENT)
                slide.shapes.add_picture(
                    found_path, Inches(0.5), Inches(1.5),
                    width=Inches(6.0), height=Inches(5.0)
                )
                has_image = True
            except Exception as e:
                logger.error(f"[PPTX] Erro imagem: {e}")

    # Conteúdo (Texto) - Espaçamento de linha melhorado
    txt_l = Inches(7.0) if has_image else Inches(1.0)
    txt_w = Inches(5.8) if has_image else Inches(11.3)
    
    tb = slide.shapes.add_textbox(txt_l, Inches(1.6), txt_w, Inches(5.3))
    tf = tb.text_frame
    tf.word_wrap = True

    for i, bullet in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(18) # Mais espaço entre bullets
        p.space_after = Pt(4)
        p.level = 0
        
        # Marcador customizado (Exec Dot)
        r = p.add_run()
        r.text = "◈  "
        r.font.color.rgb = _ACCENT
        r.font.bold = True
        
        r2 = p.add_run()
        r2.text = str(bullet)
        r2.font.size = Pt(19) # Fonte levemente menor para caber melhor
        r2.font.color.rgb = _TEXT


@tool
async def generate_pptx(slides_content_json: str) -> str:
    """Gera apresentação executiva premium com design Manus AI (Navy + Cobalt Blue, Calibri)."""
    try:
        filename = f"Exec-Deck-{uuid.uuid4().hex[:6]}.pptx"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)

        content = json.loads(slides_content_json)
        prs = Presentation()
        prs.slide_width = _W
        prs.slide_height = _H

        # Slide de capa
        _build_cover(
            prs,
            title=content.get("presentation_title", "EXECUTIVE DECK"),
            subtitle=content.get("subtitle", "")
        )

        # Slides de conteúdo
        for s_data in content.get("slides", []):
            _build_content(
                prs,
                title=s_data.get("title", ""),
                bullets=s_data.get("bullets", []),
                img_path=s_data.get("image_path")
            )

        prs.save(filepath)
        logger.info(f"[PPTX] Apresentação salva: {filename}")
        return f"Apresentação Executiva gerada: <SEND_FILE:{filename}>"
    except Exception as e:
        logger.error(f"[PPTX] Erro: {e}", exc_info=True)
        return f"Falha no PPTX: {str(e)}"
