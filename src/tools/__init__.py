import logging
import importlib
from pathlib import Path

logger = logging.getLogger(__name__)

# Dicionário para armazenar geradores disponíveis
AVAILABLE_GENERATORS = {}

# Lista de todos os geradores necessários
GENERATORS_TO_CHECK = [
    ("doc_generator", "generate_pdf", "PDF"),
    ("doc_generator", "generate_docx", "DOCX"),
    ("pptx_generator", "generate_pptx", "PPTX"),
    ("excel_tools", "create_excel", "Excel"),
]

for module_name, func_name, label in GENERATORS_TO_CHECK:
    try:
        module = importlib.import_module(f".{module_name}", package="src.tools")
        func = getattr(module, func_name)
        AVAILABLE_GENERATORS[func_name] = func
        logger.info(f"✅ {label} generator disponível e carregado")
    except (ImportError, AttributeError) as e:
        logger.error(f"❌ {label} generator NÃO disponível: {str(e)}")
        # Cria função dummy que retorna erro claro
        def dummy_generator(*args, **kwargs):
            return {"error": f"Gerador de {label} não disponível", "success": False}
        AVAILABLE_GENERATORS[func_name] = dummy_generator
