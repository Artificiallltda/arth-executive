import asyncio
import logging
from langchain_core.tools import tool
from ddgs import DDGS

logger = logging.getLogger(__name__)

@tool
async def search_web(query: str, max_results: int = 8) -> str:
    """
    Pesquisa na web em tempo real. Use para fatos, noticias e dados atuais.
    """
    try:
        logger.info(f"[WebSearch] Pesquisando: {query}")

        # DDGS é síncrono — rodar em thread para não bloquear o event loop
        def _run_search():
            with DDGS() as ddgs:
                gen = ddgs.text(query, max_results=max_results)
                return list(gen) if gen else []

        # Tenta até 3 vezes com pausa entre tentativas (DuckDuckGo pode rate-limitar)
        results = []
        for attempt in range(3):
            try:
                results = await asyncio.to_thread(_run_search)
                if results:
                    break
                if attempt < 2:
                    await asyncio.sleep(1.5)
            except Exception as e:
                logger.warning(f"[WebSearch] Tentativa {attempt + 1} falhou: {e}")
                if attempt < 2:
                    await asyncio.sleep(2.0)

        if not results:
            logger.warning(f"[WebSearch] Nenhum resultado encontrado para: {query}")
            return f"Nenhuma informacao recente encontrada para: {query}"

        formatted_results = []
        for i, r in enumerate(results):
            title = r.get('title', 'Sem título').strip()
            link = r.get('href', r.get('link', 'Sem URL')).strip()
            body = r.get('body', r.get('snippet', '')).strip()
            
            formatted_results.append(
                f"FONTE [{i+1}]: {title}\n"
                f"URL: {link}\n"
                f"CONTEÚDO: {body}\n"
                f"---"
            )

        final_output = "\n".join(formatted_results)
        logger.info(f"[WebSearch] Pesquisa concluída. Retornados {len(results)} resultados ({len(final_output)} chars).")
        return final_output
    except Exception as e:
        logger.error(f"[WebSearch] Falha total: {e}")
        return f"Erro na pesquisa em tempo real: {str(e)}"
