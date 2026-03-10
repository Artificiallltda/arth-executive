from typing import Dict, List

AGENT_CAPABILITIES: Dict[str, Dict] = {
    "arth_executor": {
        "can_generate": ["image", "jpg", "png", "jpeg"],
        "tools": ["image_generator"],
        "can_search": False,
        "description": "Executa tarefas práticas e gera imagens"
    },
    "arth_analyst": {
        "can_generate": ["pdf", "docx", "pptx", "excel", "xlsx", "xls"],
        "tools": ["pdf_generator", "docx_generator", "pptx_generator", "excel_generator"],
        "can_search": False,
        "description": "Analisa dados e gera documentos, planilhas e apresentações"
    },
    "arth_researcher": {
        "can_generate": [],  # NÃO GERA NADA
        "tools": ["web_search"],
        "can_search": True,
        "description": "Pesquisa informações na internet"
    },
    "arth_planner": {
        "can_generate": [],  # NÃO GERA NADA
        "tools": [],
        "can_search": False,
        "description": "Planeja e estrutura tarefas"
    },
    "arth_qa": {
        "can_generate": [],  # NÃO GERA NADA
        "tools": [],
        "can_search": False,
        "description": "Valida e testa resultados"
    }
}

def get_agent_for_file_type(file_type: str) -> str:
    """Retorna o agente correto para gerar um tipo de arquivo."""
    file_type = file_type.lower().replace(".", "")
    for agent, caps in AGENT_CAPABILITIES.items():
        if file_type in caps.get("can_generate", []):
            return agent
    return "arth_analyst"  # fallback padrão

def can_agent_generate(agent: str, file_type: str) -> bool:
    """Verifica se um agente específico pode gerar um tipo de arquivo."""
    caps = AGENT_CAPABILITIES.get(agent, {})
    return file_type in caps.get("can_generate", [])
