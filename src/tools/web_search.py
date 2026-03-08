import asyncio
import logging
from langchain_core.tools import tool
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

@tool
async def search_web(query: str, max_results: int = 5) -> str:
    """
    Pesquisa na web usando o DuckDuckGo.
    Use esta ferramenta quando precisar buscar informacoes atualizadas, noticias,
    fatos recentes, ou pesquisar sobre qualquer assunto na internet.
    Gere queries de busca concisas e especificas.
    """
    try:
        def _search():
            ddgs = DDGS()
            return list(ddgs.text(query, max_results=max_results))

        results = await asyncio.wait_for(asyncio.to_thread(_search), timeout=15.0)

        if not results:
            return f"Nenhum resultado encontrado para: {query}"

        formatted_results = []
        for i, r in enumerate(results):
            formatted_results.append(
                f"[{i+1}] {r.get('title', '')}\n"
                f"URL: {r.get('href', '')}\n"
                f"Resumo: {r.get('body', '')}\n"
            )

        return "\n".join(formatted_results)
    except asyncio.TimeoutError:
        logger.warning(f"[WebSearch] Timeout na busca: {query}")
        return f"Timeout ao pesquisar '{query}'. Tente uma query mais simples."
    except Exception as e:
        logger.error(f"[WebSearch] Erro: {e}")
        return f"Erro ao pesquisar na web: {str(e)}"
