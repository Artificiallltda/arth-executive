import asyncio
import logging
import re
from typing import Optional
from langchain_core.tools import tool
from ddgs import DDGS
from src.config import settings

logger = logging.getLogger(__name__)

async def _search_duckduckgo(query: str, max_results: int = 5) -> str:
    """Fallback usando DuckDuckGo."""
    try:
        def _run_search():
            with DDGS() as ddgs:
                gen = ddgs.text(query, max_results=max_results)
                return list(gen) if gen else []

        results = await asyncio.to_thread(_run_search)
        if not results:
            return ""

        formatted = []
        for i, r in enumerate(results):
            formatted.append(f"FONTE [{i+1}]: {r.get('title', '')}\nURL: {r.get('href', '')}\nCONTEÚDO: {r.get('body', '')}\n---")
        return "\n".join(formatted)
    except Exception as e:
        logger.warning(f"[WebSearch] Falha no fallback DuckDuckGo: {e}")
        return ""

@tool
async def search_web(query: str, max_results: int = 6) -> str:
    """
    Pesquisa na web em tempo real. Motor primário: Tavily (AI-Search).
    Use para fatos, notícias e dados atuais.
    """
    try:
        logger.info(f"[WebSearch] Pesquisando: {query}")

        # Se tiver chave do Tavily, usa o motor premium
        if settings.TAVILY_API_KEY:
            try:
                from tavily import TavilyClient
                tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
                
                # Executa busca assíncrona via thread
                search_result = await asyncio.to_thread(
                    tavily.search, 
                    query=query, 
                    search_depth="advanced", # Mais profundo para nível executivo
                    max_results=max_results
                )
                
                results = search_result.get("results", [])
                if results:
                    formatted = []
                    for i, r in enumerate(results):
                        formatted.append(
                            f"FONTE [{i+1}]: {r.get('title', 'Sem título')}\n"
                            f"URL: {r.get('url', 'Sem URL')}\n"
                            f"CONTEÚDO: {r.get('content', '')}\n"
                            f"---"
                        )
                    final_output = "\n".join(formatted)
                    logger.info(f"[WebSearch] Tavily OK. {len(results)} resultados.")
                    return final_output
            except Exception as te:
                logger.warning(f"[WebSearch] Erro no Tavily: {te}. Tentando fallback...")

        # Fallback ou se não tiver chave
        logger.info("[WebSearch] Usando motor DuckDuckGo...")
        ddg_output = await _search_duckduckgo(query, max_results)
        
        if not ddg_output:
            return f"Infelizmente não encontrei informações recentes para: {query}"
            
        return ddg_output

    except Exception as e:
        logger.error(f"[WebSearch] Falha total: {e}")
        return f"Erro na pesquisa em tempo real: {str(e)}"
