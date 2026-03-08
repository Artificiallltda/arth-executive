import os
import json
import uuid
import logging
from langchain_core.tools import tool
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from src.config import settings

logger = logging.getLogger(__name__)

# ─── Manus Executive Design System ──────────────────────────────────────────
# Paleta: Dark Navy + Cobalt Blue — limpo, profissional, moderno
_BG     = RGBColor(13,  17,  23)   # #0D1117 — fundo principal
_CARD   = RGBColor(22,  27,  34)   # #161B22 — header / cards
_ACCENT = RGBColor(88, 166, 255)   # #58A6FF — azul cobalto
_WHITE  = RGBColor(255, 255, 255)  # branco puro
_TEXT   = RGBColor(230, 237, 243)  # #E6EDF3 — off-white
_MUTED  = RGBColor(139, 148, 158)  # #8B949E — cinza

_W = Inches(13.333)
_H = Inches(7.5)


def _bg(slide, color=_BG):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _rect(slide, l, t, w, h, color):
    """Adiciona retângulo colorido (MSO_AUTO_SHAPE_TYPE.RECTANGLE = 1)."""
    s = slide.shapes.add_shape(1, l, t, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = color
    s.line.color.rgb = color  # linha mesma cor do fill = invisível
    return s


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

    # Barra de acento no topo
    _rect(slide, Inches(0), Inches(0), _W, Pt(5), _ACCENT)

    # Barra vertical decorativa à esquerda
    _rect(slide, Inches(0.75), Inches(1.5), Pt(4), Inches(3.4), _ACCENT)

    # Título principal
    _text(slide, Inches(1.15), Inches(1.7), Inches(11.0), Inches(2.6),
          title.upper(), 48, bold=True, color=_WHITE)

    # Subtítulo (se informado)
    if subtitle:
        _text(slide, Inches(1.15), Inches(4.5), Inches(9.5), Inches(0.8),
              subtitle, 22, color=_ACCENT, italic=True)

    # Barra de acento na base
    _rect(slide, Inches(0), _H - Pt(5), _W, Pt(5), _ACCENT)

    # Label rodapé
    _text(slide, Inches(0.5), _H - Inches(0.55), Inches(8), Inches(0.4),
          "EXECUTIVE BRIEFING  ·  CONFIDENTIAL", 9, color=_MUTED)


def _build_content(prs, title, bullets, img_path=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(slide)

    # Barra de header
    _rect(slide, Inches(0), Inches(0), _W, Inches(0.95), _CARD)
    # Borda esquerda colorida no header
    _rect(slide, Inches(0), Inches(0), Pt(5), Inches(0.95), _ACCENT)

    # Título no header
    _text(slide, Inches(0.28), Inches(0.10), Inches(12.5), Inches(0.72),
          title.upper(), 26, bold=True, color=_WHITE)

    # Barra de acento na base
    _rect(slide, Inches(0), _H - Pt(4), _W, Pt(4), _ACCENT)

    # Número da página
    slide_num = len(prs.slides)
    _text(slide, _W - Inches(0.8), _H - Inches(0.45), Inches(0.7), Inches(0.35),
          str(slide_num), 10, color=_MUTED, align=PP_ALIGN.RIGHT)

    # Imagem (se informada)
    has_image = False
    if img_path:
        clean = str(img_path).split(":")[-1].replace(">", "").strip()
        full_path = os.path.join(settings.DATA_OUTPUTS_PATH, clean)
        if os.path.exists(full_path):
            try:
                slide.shapes.add_picture(
                    full_path, Inches(0.4), Inches(1.1),
                    width=Inches(5.9), height=Inches(5.7)
                )
                has_image = True
                logger.info(f"[PPTX] Imagem inserida: {clean}")
            except Exception as e:
                logger.error(f"[PPTX] Erro ao inserir imagem {clean}: {e}")
        else:
            logger.warning(f"[PPTX] Imagem não encontrada: {full_path}")

    # Área de texto
    txt_l = Inches(6.6) if has_image else Inches(0.65)
    txt_w = Inches(6.3) if has_image else Inches(12.15)

    tb = slide.shapes.add_textbox(txt_l, Inches(1.2), txt_w, Inches(5.85))
    tf = tb.text_frame
    tf.word_wrap = True

    for i, bullet in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(14)
        p.space_after = Pt(4)

        # Marcador colorido
        r_dot = p.add_run()
        r_dot.text = "●  "
        r_dot.font.name = "Calibri"
        r_dot.font.size = Pt(11)
        r_dot.font.bold = True
        r_dot.font.color.rgb = _ACCENT

        # Texto do bullet
        r_txt = p.add_run()
        r_txt.text = str(bullet)
        r_txt.font.name = "Calibri"
        r_txt.font.size = Pt(18)
        r_txt.font.color.rgb = _TEXT


@tool
async def generate_pptx(slides_content_json: str) -> str:
    """Gera apresentação executiva premium com design Manus AI (Navy + Cobalt Blue, Calibri)."""
    try:
        filename = f"Exec_Deck_{uuid.uuid4().hex[:6]}.pptx"
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
