import os
import logging
from typing import Optional
from langchain_core.tools import tool
import fitz  # PyMuPDF
from docx import Document
from src.config import settings

logger = logging.getLogger(__name__)

@tool
async def read_document(filename: str) -> str:
    """
    Lê o conteúdo textual de um documento (PDF ou DOCX) que o usuário enviou.
    Use para resumos, análises de contratos ou resolução de exercícios.
    """
    try:
        # Tenta localizar o arquivo na pasta de outputs (onde os recebidos costumam ficar)
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
        
        if not os.path.exists(filepath):
            return f"Erro: Arquivo '{filename}' não encontrado no servidor."

        ext = os.path.splitext(filename)[1].lower()
        content = ""

        # --- Leitura de PDF ---
        if ext == ".pdf":
            logger.info(f"[DocReader] Lendo PDF: {filename}")
            with fitz.open(filepath) as doc:
                for page in doc:
                    content += page.get_text()
        
        # --- Leitura de DOCX ---
        elif ext == ".docx":
            logger.info(f"[DocReader] Lendo DOCX: {filename}")
            doc = Document(filepath)
            content = "\n".join([p.text for p in doc.paragraphs])

        else:
            return f"Extensão '{ext}' não suportada para leitura direta ainda."

        if not content.strip():
            return "O documento parece estar vazio ou contém apenas imagens/scans não processáveis por texto puro."

        logger.info(f"[DocReader] Sucesso. {len(content)} caracteres extraídos.")
        return content[:15000] # Limite para não estourar contexto do modelo

    except Exception as e:
        logger.error(f"[DocReader] Erro ao ler documento: {e}")
        return f"Falha técnica ao ler o arquivo: {str(e)}"
