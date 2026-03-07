from langchain_core.tools import tool
from duckduckgo_search import DDGS

@tool
def search_web(query: str, max_results: int = 5) -> str:
    """
    Pesquisa na web usando o DuckDuckGo.
    Use esta ferramenta quando precisar buscar informa\'E7\'F5es atualizadas, not\'EDcias,
    fatos recentes, ou pesquisar sobre qualquer assunto na internet.
    Gere queries de busca concisas e espec\'EDficas.
    """
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            return f"Nenhum resultado encontrado para: {query}"
            
        formatted_results = []
        for i, r in enumerate(results):
            formatted_results.append(f"[{i+1}] {r.get('title', '')}\nURL: {r.get('href', '')}\nResumo: {r.get('body', '')}\n")
            
        return "\n".join(formatted_results)
    except Exception as e:
        return f"Erro ao pesquisar na web: {str(e)}"
