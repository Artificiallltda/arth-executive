"""
SISTEMA DE GERAÇÃO DE ARQUIVOS DE ALTA QUALIDADE
Stack: FastAPI + Playwright + Jinja2 + Tailwind CSS + Google Gemini
Deploy: Railway
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os

from tools.gerar_pdf import gerar_pdf_html
from tools.gerar_docx import gerar_docx
from tools.gerar_excel import gerar_excel
from tools.gerar_pptx import gerar_pptx
from tools.gemini_ai import (
    gerar_conteudo_para_pdf,
    gerar_slides_para_pptx,
    gerar_dados_para_excel
)

app = FastAPI(
    title="Gerador de Arquivos IA — Powered by Gemini",
    description="API para geração de PDF, DOCX, Excel e PPTX de alta qualidade com Google Gemini",
    version="2.0.0"
)

# CORS para integração com frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Modelos de entrada ──

class PDFRequest(BaseModel):
    titulo: str
    conteudo_markdown: str
    tema: Optional[str] = "azul"  # azul, verde, roxo, escuro

class PDFAutoRequest(BaseModel):
    """Gera PDF com conteúdo criado automaticamente pelo Gemini"""
    topico: str
    tipo_documento: Optional[str] = "relatório"
    tema: Optional[str] = "azul"

class DOCXRequest(BaseModel):
    titulo: str
    secoes: List[dict]
    autor: Optional[str] = "Sistema IA"

class ExcelRequest(BaseModel):
    titulo: str
    cabecalhos: List[str]
    dados: List[List]
    nome_aba: Optional[str] = "Dados"

class ExcelAutoRequest(BaseModel):
    """Gera Excel com dados criados automaticamente pelo Gemini"""
    topico: str

class PPTXRequest(BaseModel):
    titulo_apresentacao: str
    subtitulo: Optional[str] = ""
    slides: List[dict]
    tema: Optional[str] = "profissional"

class PPTXAutoRequest(BaseModel):
    """Gera PPTX com conteúdo criado automaticamente pelo Gemini"""
    topico: str
    subtitulo: Optional[str] = ""
    num_slides: Optional[int] = 6
    tema: Optional[str] = "profissional"


# ── Endpoints Manuais ──

@app.post("/gerar/pdf", summary="Gerar PDF a partir de Markdown")
async def endpoint_pdf(req: PDFRequest):
    try:
        caminho = await gerar_pdf_html(req.titulo, req.conteudo_markdown, req.tema)
        return FileResponse(caminho, media_type="application/pdf", filename=f"{req.titulo}.pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/gerar/docx", summary="Gerar documento Word")
async def endpoint_docx(req: DOCXRequest):
    try:
        caminho = gerar_docx(req.titulo, req.secoes, req.autor)
        return FileResponse(caminho, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=f"{req.titulo}.docx")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/gerar/excel", summary="Gerar planilha Excel")
async def endpoint_excel(req: ExcelRequest):
    try:
        caminho = gerar_excel(req.titulo, req.cabecalhos, req.dados, req.nome_aba)
        return FileResponse(caminho, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=f"{req.titulo}.xlsx")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/gerar/pptx", summary="Gerar apresentação PowerPoint")
async def endpoint_pptx(req: PPTXRequest):
    try:
        caminho = gerar_pptx(req.titulo_apresentacao, req.subtitulo, req.slides, req.tema)
        return FileResponse(caminho, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", filename=f"{req.titulo_apresentacao}.pptx")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoints com Gemini (geração automática) ──

@app.post("/gerar/pdf-auto", summary="Gerar PDF com conteúdo criado pelo Gemini")
async def endpoint_pdf_auto(req: PDFAutoRequest):
    """
    Passa apenas o tópico e o Gemini cria o conteúdo completo automaticamente.
    Exemplo: {"topico": "Tendências de IA em 2026", "tema": "azul"}
    """
    try:
        conteudo_md = gerar_conteudo_para_pdf(req.topico, req.tipo_documento)
        caminho = await gerar_pdf_html(req.topico, conteudo_md, req.tema)
        return FileResponse(caminho, media_type="application/pdf", filename=f"{req.topico}.pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/gerar/pptx-auto", summary="Gerar PPTX com conteúdo criado pelo Gemini")
async def endpoint_pptx_auto(req: PPTXAutoRequest):
    """
    Passa apenas o tópico e o Gemini cria todos os slides automaticamente.
    """
    try:
        slides = gerar_slides_para_pptx(req.topico, req.num_slides)
        caminho = gerar_pptx(req.topico, req.subtitulo, slides, req.tema)
        return FileResponse(caminho, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", filename=f"{req.topico}.pptx")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/gerar/excel-auto", summary="Gerar Excel com dados criados pelo Gemini")
async def endpoint_excel_auto(req: ExcelAutoRequest):
    """
    Passa apenas o tópico e o Gemini cria os dados da planilha automaticamente.
    """
    try:
        dados_gerados = gerar_dados_para_excel(req.topico)
        caminho = gerar_excel(
            dados_gerados["titulo"],
            dados_gerados["cabecalhos"],
            dados_gerados["dados"]
        )
        return FileResponse(caminho, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=f"{req.topico}.xlsx")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Utilitários ──

@app.get("/listar-arquivos", summary="Listar arquivos gerados")
async def listar_arquivos():
    os.makedirs("outputs", exist_ok=True)
    arquivos = os.listdir("outputs")
    return {"arquivos": arquivos, "total": len(arquivos)}

@app.delete("/limpar-outputs", summary="Limpar arquivos gerados")
async def limpar_outputs():
    import glob
    arquivos = glob.glob("outputs/*")
    for f in arquivos:
        os.remove(f)
    return {"mensagem": f"{len(arquivos)} arquivo(s) removido(s)"}

@app.get("/health", summary="Health check")
async def health():
    return {
        "status": "ok",
        "servico": "Gerador de Arquivos IA",
        "modelo_ia": "Google Gemini 2.5",
        "versao": "2.0.0"
    }
