from langchain_core.tools import tool
import os
import re
import uuid
import logging
import unicodedata
import unicodedata
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from fpdf import FPDF
from src.config import settings

logger = logging.getLogger(__name__)

def _safe_filename(title: str, max_len: int = 50) -> str:
    """Normaliza título para ASCII puro — evita surrogates e erros de encoding."""
    normalized = unicodedata.normalize('NFKD', title)
    ascii_only = normalized.encode('ascii', errors='ignore').decode('ascii')
    safe = re.sub(r'[^\w\s-]', '', ascii_only).strip().lower().replace(' ', '_')
    return (safe or 'documento')[:max_len]


def _safe_filename(title: str, max_len: int = 50) -> str:
    """Normaliza para ASCII puro — evita surrogates e erros de encoding."""
    normalized = unicodedata.normalize('NFKD', title)
    ascii_only = normalized.encode('ascii', errors='ignore').decode('ascii')
    safe = re.sub(r'[^\w\s-]', '', ascii_only).strip().lower().replace(' ', '_')
    return (safe or 'documento')[:max_len]


# ─── Paleta Executiva ────────────────────────────────────────────────────────
_AZUL_CORP  = RGBColor(28,  78, 158)   # Azul corporativo profundo
_AZUL_SEC   = RGBColor(36, 110, 185)   # Azul secundário
_CINZA_H    = RGBColor(45,  45,  45)   # Quase preto para sub-headings
_CINZA_BODY = RGBColor(55,  55,  55)   # Cinza escuro para corpo


# ─── Helpers DOCX ────────────────────────────────────────────────────────────

def _add_rich_text(paragraph, text: str, size_pt: int = 11, color=None):
    """Adiciona texto com suporte a **negrito** inline."""
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    for part in parts:
        bold = part.startswith('**') and part.endswith('**')
        run = paragraph.add_run(part[2:-2] if bold else part)
        run.bold = bold
        run.font.size = Pt(size_pt)
        run.font.name = "Calibri"
        if color:
            run.font.color.rgb = color


def _set_margins(doc: Document, margin_in: float = 1.0):
    for section in doc.sections:
        section.top_margin    = Inches(margin_in)
        section.bottom_margin = Inches(margin_in)
        section.left_margin   = Inches(margin_in)
        section.right_margin  = Inches(margin_in)


def _parse_markdown_to_docx(doc: Document, content: str):
    """Converte markdown simples em Word com design executivo."""
    for line in content.split('\n'):
        stripped = line.strip()

        if not stripped:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            continue

        if stripped.startswith('# ') and not stripped.startswith('## '):
            h = doc.add_heading(stripped[2:].strip(), level=1)
            h.paragraph_format.space_before = Pt(20)
            h.paragraph_format.space_after  = Pt(8)
            if h.runs:
                h.runs[0].font.color.rgb = _AZUL_CORP
                h.runs[0].font.size      = Pt(16)
                h.runs[0].font.name      = "Calibri"

        elif stripped.startswith('## '):
            h = doc.add_heading(stripped[3:].strip(), level=2)
            h.paragraph_format.space_before = Pt(14)
            h.paragraph_format.space_after  = Pt(6)
            if h.runs:
                h.runs[0].font.color.rgb = _AZUL_SEC
                h.runs[0].font.size      = Pt(13)
                h.runs[0].font.name      = "Calibri"

        elif stripped.startswith('### '):
            h = doc.add_heading(stripped[4:].strip(), level=3)
            h.paragraph_format.space_before = Pt(10)
            h.paragraph_format.space_after  = Pt(4)
            if h.runs:
                h.runs[0].font.color.rgb = _CINZA_H
                h.runs[0].font.size      = Pt(11)
                h.runs[0].font.name      = "Calibri"

        elif stripped.startswith('- ') or stripped.startswith('* '):
            p = doc.add_paragraph(style='List Bullet')
            p.paragraph_format.space_after  = Pt(4)
            p.paragraph_format.space_before = Pt(2)
            _add_rich_text(p, stripped[2:].strip(), size_pt=11, color=_CINZA_BODY)

        elif re.match(r'^\d+\. ', stripped):
            text_body = re.sub(r'^\d+\. ', '', stripped)
            p = doc.add_paragraph(style='List Number')
            p.paragraph_format.space_after = Pt(4)
            _add_rich_text(p, text_body, size_pt=11, color=_CINZA_BODY)

        else:
            p = doc.add_paragraph()
            p.paragraph_format.space_after  = Pt(8)
            p.paragraph_format.space_before = Pt(2)
            _add_rich_text(p, stripped, size_pt=11, color=_CINZA_BODY)


@tool
async def generate_docx(title: str, content: str) -> str:
    """Cria um documento Word (.docx) com design executivo profissional."""
    try:
        filename = f"{uuid.uuid4().hex[:6]}_{_safe_filename(title)}.docx"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)

        doc = Document()
        _set_margins(doc, margin_in=1.0)

        # Título principal — centralizado, azul, grande
        title_h = doc.add_heading(title, 0)
        title_h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_h.paragraph_format.space_after = Pt(6)
        if title_h.runs:
            title_h.runs[0].font.color.rgb = _AZUL_CORP
            title_h.runs[0].font.size      = Pt(22)
            title_h.runs[0].font.name      = "Calibri"

        # Linha decorativa abaixo do título
        sep = doc.add_paragraph()
        sep.paragraph_format.space_after = Pt(18)
        r = sep.add_run("─" * 78)
        r.font.color.rgb = _AZUL_CORP
        r.font.size      = Pt(8)

        _parse_markdown_to_docx(doc, content)

        doc.save(filepath)
        exists = os.path.exists(filepath)
        logger.info(f"[DOCX] Salvo: {filepath} | exists={exists} | size={os.path.getsize(filepath) if exists else 0}B")
        return f"Documento Word executivo gerado com sucesso: <SEND_FILE:{filename}>"
    except Exception as e:
        logger.error(f"[DOCX] Erro: {e}", exc_info=True)
        return f"Falha ao gerar DOCX: {str(e)}"


# ─── PDF ─────────────────────────────────────────────────────────────────────

class ArthPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(140, 140, 140)
        self.cell(0, 8, "ARTH EXECUTIVE  ·  CONFIDENTIAL", 0, 1, "R")
        # Linha decorativa azul
        self.set_draw_color(88, 166, 255)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_draw_color(88, 166, 255)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_font("Helvetica", "", 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 10, f"Página {self.page_no()}", 0, 0, "C")


@tool
async def generate_pdf(title: str, content: str) -> str:
    """Cria um documento PDF com visual executivo e suporte total a UTF-8."""
    try:
        filename = f"{uuid.uuid4().hex[:6]}_{_safe_filename(title)}.pdf"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)

        pdf = ArthPDF()
        pdf.set_margins(left=18, top=15, right=18)
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        # Título principal
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(28, 78, 158)
        pdf.multi_cell(0, 14, title, align='C')

        # Linha decorativa azul
        pdf.set_draw_color(88, 166, 255)
        pdf.set_line_width(0.8)
        y = pdf.get_y() + 3
        pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
        pdf.ln(12)

        def _clean(text: str) -> str:
            """Remove marcadores markdown e caracteres fora do Latin-1."""
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
            text = re.sub(r'\*([^*]+)\*', r'\1', text)
            return text.encode("latin-1", errors="replace").decode("latin-1")

        # Conteúdo
        for line in content.split('\n'):
            stripped = line.strip()

            if not stripped:
                pdf.ln(5)
                continue

            if stripped.startswith('# ') and not stripped.startswith('## '):
                pdf.ln(4)
                pdf.set_font("Helvetica", "B", 17)
                pdf.set_text_color(28, 78, 158)
                pdf.multi_cell(0, 11, _clean(stripped[2:]))
                # Underline do H1
                y2 = pdf.get_y() + 1
                pdf.set_draw_color(28, 78, 158)
                pdf.set_line_width(0.5)
                pdf.line(pdf.l_margin, y2, pdf.w - pdf.r_margin, y2)
                pdf.ln(5)

            elif stripped.startswith('## '):
                pdf.ln(3)
                pdf.set_font("Helvetica", "B", 14)
                pdf.set_text_color(36, 110, 185)
                pdf.multi_cell(0, 9, _clean(stripped[3:]))
                pdf.ln(2)

            elif stripped.startswith('### '):
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(64, 64, 64)
                pdf.multi_cell(0, 8, _clean(stripped[4:]))
                pdf.ln(1)

            elif stripped.startswith('- ') or stripped.startswith('* '):
                pdf.set_font("Helvetica", "", 11)
                pdf.set_text_color(50, 50, 50)
                pdf.multi_cell(0, 7, f"  -  {_clean(stripped[2:])}")

            elif re.match(r'^\d+\. ', stripped):
                body = re.sub(r'^\d+\. ', '', stripped)
                pdf.set_font("Helvetica", "", 11)
                pdf.set_text_color(50, 50, 50)
                pdf.multi_cell(0, 7, f"  {_clean(body)}")

            else:
                pdf.set_font("Helvetica", "", 11)
                pdf.set_text_color(50, 50, 50)
                pdf.multi_cell(0, 7, _clean(stripped))
                pdf.ln(2)

        pdf.output(filepath)
        exists = os.path.exists(filepath)
        logger.info(f"[PDF] Salvo: {filepath} | exists={exists} | size={os.path.getsize(filepath) if exists else 0}B")
        return f"PDF Executivo gerado com sucesso: <SEND_FILE:{filename}>"
    except Exception as e:
        logger.error(f"[PDF] Erro: {e}", exc_info=True)
        return f"Falha ao gerar PDF: {str(e)}"
