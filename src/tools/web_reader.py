import httpx
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

@tool
async def read_url(url: str) -> str:
    """
    Lê o conteúdo completo de um link/URL específico. 
    Use quando o usuário enviar um link ou quando você precisar aprofundar em um resultado de pesquisa.
    """
    try:
        logger.info(f"[WebReader] Lendo URL: {url}")
        
        # Chamada simplificada para evitar bloqueios de header
        jina_url = f"https://r.jina.ai/{url}"
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(jina_url, timeout=30.0)
            if resp.status_code == 200:
                content = resp.text
                logger.info(f"[WebReader] Conteúdo extraído: {len(content)} caracteres.")
                return content[:12000] # Aumentado para 12k chars
            else:
                logger.warning(f"[WebReader] Falha ao ler link (Status {resp.status_code})")
                return f"Não foi possível extrair o conteúdo do link (Erro {resp.status_code}). Tente buscar o assunto via search_web."

    except Exception as e:
        logger.error(f"[WebReader] Erro total: {e}")
        return f"Erro ao tentar ler o link: {str(e)}"
