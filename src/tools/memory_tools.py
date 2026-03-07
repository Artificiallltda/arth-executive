import os
from typing import Optional
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from src.config import settings

PERSIST_DIRECTORY = os.path.join(os.getcwd(), "data", "chroma_db")
_vector_store = None

def _get_vector_store() -> Chroma:
    """Lazy init: cria o Chroma apenas na primeira chamada real."""
    global _vector_store
    if _vector_store is None:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        _vector_store = Chroma(
            collection_name="arth_long_term_memory",
            embedding_function=embeddings,
            persist_directory=PERSIST_DIRECTORY
        )
    return _vector_store

@tool
def save_memory(fact: str, context: str = "", agent_id: str = "global") -> str:
    """
    Salva uma informação importante, fato, preferência do usuário ou evento na memória de Longo Prazo.
    Use esta ferramenta SEMPRE que o usuário falar algo sobre ele mesmo (ex: "Meu nome é X", "Eu gosto de Y", "Meu email é Z") 
    ou quando você processar uma informação longa que precisa ser lembrada no futuro.
    - fact: A informação principal a ser salva (ex: "O usuário se chama Gean").
    - context: Detalhes adicionais (opcional).
    - agent_id: Identificador do agente que gerou a memória (opcional, default 'global').
    """
    try:
        doc = f"FATO: {fact}\nCONTEXTO: {context}"
        _get_vector_store().add_texts([doc], metadatas=[{"agent": agent_id}])
        return f"Memória salva com sucesso: '{fact}' pelo agente '{agent_id}'"
    except Exception as e:
        return f"Erro ao salvar na memória: {str(e)}"

@tool
def search_memory(query: str, n_results: int = 3, filter_agent: Optional[str] = None) -> str:
    """
    Busca na memória de Longo Prazo do Arth por fatos, nomes, documentos ou ações passadas.
    Use isso se você precisar lembrar quem é o usuário, o que ele gosta, ou consultar algo que você salvou antes.
    Todos os agentes têm acesso de LEITURA à memória global por padrão.
    - query: O que você está buscando (ex: "Qual é o nome do usuário?", "Resumo da reunião XYZ").
    - filter_agent: (Opcional) Filtrar para buscar memórias apenas de um agente específico.
    """
    try:
        filter_kwargs = {"filter": {"agent": filter_agent}} if filter_agent else {}
        results = _get_vector_store().similarity_search(query, k=n_results, **filter_kwargs)
        if not results:
            return f"Nenhuma memória encontrada para: {query}"
            
        memories = [f"-[{res.metadata.get('agent', 'global')}] {res.page_content}" for res in results]
        return "Memórias encontradas:\n" + "\n".join(memories)
    except Exception as e:
        return f"Erro ao buscar na memória: {str(e)}"
