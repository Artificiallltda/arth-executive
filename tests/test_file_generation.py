import asyncio
import os
import sys
import logging
from pathlib import Path

# Adiciona o diretório raiz ao PYTHONPATH para os imports do src funcionarem no teste
sys.path.append(str(Path(__file__).parent.parent))

from src.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def test_all_generators():
    """Testa cada tipo de arquivo e registra resultado físico."""
    results = {}
    
    os.makedirs(settings.DATA_OUTPUTS_PATH, exist_ok=True)
    
    # --- 1. PDF ---
    try:
        from src.tools.doc_generator import generate_pdf
        logger.info("[TEST] Iniciando teste PDF...")
        # A tool wrapper exige um dicionário {"title": ..., "content": ...} quando chamada diretamente via invoke/ainvoke
        result = await generate_pdf.ainvoke({"title": "Teste PDF", "content": "# Teste\nConteúdo do PDF"})
        
        # Pega a tag <SEND_FILE...> do resultado para checar fisicamente
        import re
        match = re.search(r'<SEND_FILE:([^>]+)>', result)
        if match and os.path.exists(os.path.join(settings.DATA_OUTPUTS_PATH, match.group(1))):
            results["pdf"] = "✅"
        else:
            results["pdf"] = "❌ (Arquivo físico não gerado)"
    except Exception as e:
        results["pdf"] = f"❌ Erro Exceção: {str(e)}"
    
    # --- 2. DOCX ---
    try:
        from src.tools.doc_generator import generate_docx
        logger.info("[TEST] Iniciando teste DOCX...")
        result = await generate_docx.ainvoke({"title": "Teste DOCX", "content": "# Teste\nConteúdo do DOCX"})
        match = re.search(r'<SEND_FILE:([^>]+)>', result)
        if match and os.path.exists(os.path.join(settings.DATA_OUTPUTS_PATH, match.group(1))):
            results["docx"] = "✅"
        else:
            results["docx"] = "❌ (Arquivo físico não gerado)"
    except Exception as e:
        results["docx"] = f"❌ Erro Exceção: {str(e)}"
    
    # --- 3. PPTX ---
    try:
        from src.tools.pptx_generator import generate_pptx
        import json
        logger.info("[TEST] Iniciando teste PPTX...")
        payload = json.dumps({
            "presentation_title": "Teste", 
            "slides": [{"title": "Slide 1", "bullets": ["Teste"]}]
        })
        result = await generate_pptx.ainvoke({"slides_content_json": payload})
        match = re.search(r'<SEND_FILE:([^>]+)>', result)
        if match and os.path.exists(os.path.join(settings.DATA_OUTPUTS_PATH, match.group(1))):
            results["pptx"] = "✅"
        else:
            results["pptx"] = "❌ (Arquivo físico não gerado)"
    except Exception as e:
        results["pptx"] = f"❌ Erro Exceção: {str(e)}"
    
    # --- 4. Excel ---
    try:
        from src.tools.excel_tools import create_excel
        logger.info("[TEST] Iniciando teste Excel...")
        result = await create_excel.ainvoke({"data": [{"colA": 1, "colB": 2}], "file_path": "planilha_teste.xlsx"})
        match = re.search(r'<SEND_FILE:([^>]+)>', result)
        if match and os.path.exists(os.path.join(settings.DATA_OUTPUTS_PATH, match.group(1))):
            results["excel"] = "✅"
        else:
            results["excel"] = "❌ (Arquivo físico não gerado)"
    except Exception as e:
        results["excel"] = f"❌ Erro Exceção: {str(e)}"
    
    logger.info("="*50)
    logger.info("[RESULTADOS DOS TESTES DE GERAÇÃO ESTRUTURAL]")
    for k, v in results.items():
        logger.info(f"{k.upper():<10} : {v}")
    logger.info("="*50)
    
    return results

if __name__ == "__main__":
    asyncio.run(test_all_generators())
