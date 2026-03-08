import asyncio
import logging
from langchain_core.tools import tool
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

@tool
async def search_web(query: str, max_results: int = 8) -> str:
    """
    Pesquisa na web em tempo real. Use para fatos, noticias e dados atuais.
    """
    try:
        logger.info(f"[WebSearch] Pesquisando: {query}")

        # DDGS é síncrono — rodar em thread separada para não bloquear o event loop
        def _run_search():
            with DDGS() as ddgs:
                gen = ddgs.text(query, max_results=max_results)
                return list(gen) if gen else []

        results = await asyncio.to_thread(_run_search)

        if not results:
            return f"Nenhuma informacao recente encontrada para: {query}"

        formatted_results = []
        for i, r in enumerate(results):
            formatted_results.append(
                f"[{i+1}] {r.get('title', '')}\n"
                f"URL: {r.get('href', '')}\n"
                f"Resumo: {r.get('body', '')}\n"
            )

        return "\n".join(formatted_results)
    except Exception as e:
        logger.error(f"[WebSearch] Falha: {e}")
        return f"Erro na pesquisa em tempo real: {str(e)}"
