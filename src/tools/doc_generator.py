from langchain_core.tools import tool
import os
import re
import uuid
import logging
import unicodedata
import asyncio
from typing import Any
from datetime import datetime
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from fpdf import FPDF
from src.config import settings

logger = logging.getLogger(__name__)

def _safe_filename(title: str, max_len: int = 50) -> str:
    """Normaliza para ASCII puro — evita surrogates e erros de encoding."""
    normalized = unicodedata.normalize('NFKD', title)
    ascii_only = normalized.encode('ascii', errors='ignore').decode('ascii')
    safe = re.sub(r'[^\w\s-]', '', ascii_only).strip().lower().replace(' ', '-')
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


from pydantic import BaseModel, Field
from typing import Optional, Any, Union

class DocxSchema(BaseModel):
    title: Optional[str] = Field(default="Documento", description="Título do documento.")
    content: Optional[str] = Field(default=None, description="Conteúdo em texto ou markdown para o documento.")
    filename: Optional[str] = Field(default=None, description="Nome do arquivo .docx opcional.")

class PdfSchema(BaseModel):
    title: Optional[str] = Field(default="Documento", description="Título do PDF.")
    content: Optional[str] = Field(default=None, description="Conteúdo do PDF.")

@tool(args_schema=DocxSchema)
async def generate_docx(title: str = "Documento", content: str = "", filename: Optional[str] = None) -> str:
    """Gera DOCX com tratamento robusto e formatação melhorada."""
    if not content:
        logger.error("[DOCXGen] ERRO CRÍTICO: content é None ou vazio!")
        return "Erro: O conteúdo do documento não pode estar vazio."

    try:
        # ==================================================================
        # NORMALIZAÇÃO DE PARÂMETROS
        # ==================================================================
        if not filename:
            filename = f"documento_{int(datetime.now().timestamp())}.docx"
        
        if not filename.endswith(".docx"):
            filename += ".docx"
        output_dir = settings.DATA_OUTPUTS_PATH
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        
        logger.info(f"[DOCXGen] Gerando DOCX: {filepath}")
        
        # ==================================================================
        # FUNÇÃO SÍNCRONA PARA RODAR EM THREAD SEPARADA
        # ==================================================================
        def _generate():
            doc = Document()
            
            # Configura margens
            sections = doc.sections
            for section in sections:
                section.top_margin = Inches(1)
                section.bottom_margin = Inches(1)
                section.left_margin = Inches(1)
                section.right_margin = Inches(1)
            
            # TÍTULO PRINCIPAL
            title_para = doc.add_heading(title, level=0)
            title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # DATA
            date_para = doc.add_paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            date_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            # LINHA HORIZONTAL
            doc.add_paragraph('_' * 50)
            
            # CONTEÚDO
            if isinstance(content, str):
                paragraphs = content.split('\n')
                for para in paragraphs:
                    if para.strip():
                        p = doc.add_paragraph()
                        p.add_run(para.strip())
                        p.paragraph_format.space_after = Pt(12)
            else:
                p = doc.add_paragraph()
                p.add_run(str(content))
                p.paragraph_format.space_after = Pt(12)
            
            # RODAPÉ
            doc.add_paragraph('_' * 50)
            footer = doc.add_paragraph("Documento gerado pelo Arth Executive")
            footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
            footer.paragraph_format.space_before = Pt(12)
            
            doc.save(filepath)
            return filepath
        
        # Executa em thread separada
        filepath = await asyncio.to_thread(_generate)
        
        # Verifica resultado
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            size_bytes = os.path.getsize(filepath)
            logger.info(f"[DOCXGen] ✅ DOCX gerado: {filepath} ({size_bytes} bytes)")
            return f"Documento Word gerado com sucesso: <SEND_FILE:{os.path.basename(filepath)}>"
        else:
            logger.error(f"[DOCXGen] ❌ Arquivo não foi criado")
            return "Falha ao gerar DOCX: Arquivo não foi criado."
            
    except Exception as e:
        logger.error(f"[DOCXGen] ❌ Erro: {str(e)}")
        return f"Erro ao gerar DOCX: {str(e)}"


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


# ==============================================================================
# 🛡️ BLINDAGEM DE PDF (DO NOT MODIFY) 🛡️
# Atenção Desenvolvedor/AI:
# O USO DE `effective_width` AO INVÉS DE `w=0` NO MULTICELL É OBRIGATÓRIO PARA O FPDF2.
# NÃO MODIFIQUE OS IMPORTES DO FPDF E ESTA LÓGICA DE QUEBRA, EVITE REGRESSÕES 'Not enough horizontal space'.
# ==============================================================================
@tool(args_schema=PdfSchema)
async def generate_pdf(title: str, content: str) -> str:
    """Cria um documento PDF com visual executivo e suporte total a UTF-8."""
    if title is None or content is None:
        logger.error(f"[PDFGen] ERRO: Parâmetros nulos. title={title}, content={'OK' if content else 'None'}")
        title = title or "Documento"
        content = content or "Conteúdo não fornecido."
        
    try:
        filename = f"{uuid.uuid4().hex[:6]}-{_safe_filename(title)}.pdf"
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
            """Remove caracteres fora do Latin-1 (preserva asteriscos de markdown para formatação fpdf2)."""
            return text.encode("latin-1", errors="replace").decode("latin-1")

        # Usa a largura efetiva da página em vez de 0 para evitar o bug de espaço horizontal do fpdf2
        effective_width = pdf.w - pdf.l_margin - pdf.r_margin

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
                # Removendo asteriscos de titulos pois h1 já é Bold forte no código
                clean_title = _clean(stripped[2:]).replace("**", "")
                pdf.multi_cell(effective_width, 11, clean_title, markdown=True)
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
                clean_title = _clean(stripped[3:]).replace("**", "")
                pdf.multi_cell(effective_width, 9, clean_title, markdown=True)
                pdf.ln(2)

            elif stripped.startswith('### '):
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(64, 64, 64)
                clean_title = _clean(stripped[4:]).replace("**", "")
                pdf.multi_cell(effective_width, 8, clean_title, markdown=True)
                pdf.ln(1)

            elif stripped.startswith('- ') or stripped.startswith('* '):
                pdf.set_font("Helvetica", "", 11)
                pdf.set_text_color(50, 50, 50)
                pdf.multi_cell(effective_width, 7, f"  -  {_clean(stripped[2:])}", markdown=True)

            elif re.match(r'^\d+\. ', stripped):
                body = re.sub(r'^\d+\. ', '', stripped)
                pdf.set_font("Helvetica", "", 11)
                pdf.set_text_color(50, 50, 50)
                pdf.multi_cell(effective_width, 7, f"  {_clean(body)}", markdown=True)

            else:
                pdf.set_font("Helvetica", "", 11)
                pdf.set_text_color(50, 50, 50)
                pdf.multi_cell(effective_width, 7, _clean(stripped), markdown=True)
                pdf.ln(2)

        # Isolando output() (blocking IO sync) para não trancar o supervisor
        await asyncio.to_thread(pdf.output, filepath)
        
        exists = os.path.exists(filepath)
        logger.info(f"[PDF] Salvo: {filepath} | exists={exists} | size={os.path.getsize(filepath) if exists else 0}B")
        return f"PDF Executivo gerado com sucesso: <SEND_FILE:{filename}>"
    except Exception as e:
        logger.error(f"[PDF] Erro: {e}", exc_info=True)
        return f"Falha ao gerar PDF: {str(e)}"
