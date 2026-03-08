import asyncio
import logging
from langchain_core.tools import tool
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

@tool
async def search_web(query: str, max_results: int = 8) -> str:
    """
    Pesquisa na web em tempo real (Google Search via DuckDuckGo).
    Use esta ferramenta para buscar fatos, noticias, dados de mercado e informacoes atualizadas.
    """
    try:
        logger.info(f"[WebSearch] Pesquisando: {query}")
        def _search():
            with DDGS() as ddgs:
                # 'wt-wt' para resultados globais/mais amplos se regional falhar
                results = list(ddgs.text(query, max_results=max_results))
                return results

        results = await asyncio.wait_for(asyncio.to_thread(_search), timeout=20.0)

        if not results:
            return f"Nenhum resultado em tempo real encontrado para: {query}"

        formatted_results = []
        for i, r in enumerate(results):
            formatted_results.append(
                f"[{i+1}] {r.get('title', '')}\n"
                f"URL: {r.get('href', '')}\n"
                f"Resumo: {r.get('body', '')}\n"
            )

        return "\n".join(formatted_results)
    except Exception as e:
        logger.error(f"[WebSearch] Erro de conectividade: {e}")
        return f"Erro ao acessar a internet em tempo real: {str(e)}"
