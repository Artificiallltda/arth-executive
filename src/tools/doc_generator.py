from langchain_core.tools import tool
import os
import re
import uuid
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from fpdf import FPDF
from src.config import settings

# --- Cores Executivas ---
AZUL_EXEC = RGBColor(31, 73, 125)
CINZA_CORP = RGBColor(80, 80, 80)

def _add_rich_text(paragraph, text: str):
    """Adiciona texto com suporte a **negrito** inline."""
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part)

def _parse_markdown_to_docx(doc: Document, content: str):
    """Aplica design executivo no Word."""
    lines = content.split('\n')
    for line in lines:
        stripped = line.strip()
        if not stripped: continue
        
        if stripped.startswith('# ') and not stripped.startswith('## '):
            h = doc.add_heading(stripped[2:].strip(), level=1)
            if h.runs: h.runs[0].font.color.rgb = AZUL_EXEC
        elif stripped.startswith('## '):
            h = doc.add_heading(stripped[3:].strip(), level=2)
            if h.runs: h.runs[0].font.color.rgb = CINZA_CORP
        elif stripped.startswith('- ') or stripped.startswith('* '):
            p = doc.add_paragraph(style='List Bullet')
            _add_rich_text(p, stripped[2:].strip())
        else:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(8)
            _add_rich_text(p, stripped)

@tool
async def generate_docx(title: str, content: str) -> str:
    """Cria um documento Word (.docx) com design executivo profissional."""
    try:
        filename = f"{uuid.uuid4().hex[:8]}_{title.replace(' ', '_').lower()}.docx"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
        
        doc = Document()
        title_h = doc.add_heading(title, 0)
        title_h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        _parse_markdown_to_docx(doc, content)
        doc.save(filepath)
        return f"Documento Word executivo gerado com sucesso: <SEND_FILE:{filename}>"
    except Exception as e:
        return f"Falha ao gerar DOCX: {str(e)}"

def _parse_markdown_to_pdf(pdf: FPDF, content: str):
    """Aplica design moderno no PDF."""
    lines = content.split('\n')
    for line in lines:
        stripped = line.strip()
        if not stripped:
            pdf.ln(4)
            continue
        
        safe = stripped.encode('latin-1', 'replace').decode('latin-1')
        
        if stripped.startswith('# ') and not stripped.startswith('## '):
            pdf.set_text_color(31, 73, 125)
            pdf.set_font("Helvetica", style='B', size=18)
            pdf.multi_cell(0, 12, safe[2:])
            pdf.set_draw_color(31, 73, 125)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(4)
        elif stripped.startswith('## '):
            pdf.set_text_color(80, 80, 80)
            pdf.set_font("Helvetica", style='B', size=14)
            pdf.multi_cell(0, 10, safe[3:])
            pdf.ln(2)
        elif stripped.startswith('- ') or stripped.startswith('* '):
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", size=11)
            pdf.cell(10)
            pdf.multi_cell(0, 7, f"- {safe[2:]}")
        else:
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", size=11)
            pdf.multi_cell(0, 7, safe)
            pdf.ln(2)

@tool
async def generate_pdf(title: str, content: str) -> str:
    """Cria um documento PDF com visual limpo e profissional."""
    try:
        filename = f"{uuid.uuid4().hex[:8]}_{title.replace(' ', '_').lower()}.pdf"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", style='B', size=24)
        pdf.set_text_color(31, 73, 125)
        pdf.cell(0, 20, title.encode('latin-1', 'replace').decode('latin-1'), ln=True, align='C')
        pdf.ln(10)
        
        _parse_markdown_to_pdf(pdf, content)
        pdf.output(filepath)
        return f"PDF profissional gerado com sucesso: <SEND_FILE:{filename}>"
    except Exception as e:
        return f"Falha ao gerar PDF: {str(e)}"
