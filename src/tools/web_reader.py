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
        
        # Usando o r.jina.ai que é um proxy que limpa o HTML e entrega Markdown puro
        jina_url = f"https://r.jina.ai/{url}"
        
        headers = {
            "Accept": "text/event-stream",
            "X-With-Generated-Alt": "true" # Tenta gerar alt text para imagens no site
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(jina_url, headers=headers, timeout=30.0)
            if resp.status_code == 200:
                content = resp.text
                logger.info(f"[WebReader] Conteúdo extraído: {len(content)} caracteres.")
                # Retorna apenas os primeiros 10k caracteres para não estourar contexto
                return content[:10000]
            else:
                logger.warning(f"[WebReader] Falha ao ler link (Status {resp.status_code})")
                return f"Não foi possível extrair o conteúdo do link. Erro: {resp.status_code}"

    except Exception as e:
        logger.error(f"[WebReader] Erro total: {e}")
        return f"Erro ao tentar ler o link: {str(e)}"
