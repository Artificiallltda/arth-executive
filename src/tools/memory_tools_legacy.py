import os
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from src.config import settings

# Inicializa o banco vetorial local (SQLite)
# Ele vai criar uma pasta "chroma_db" dentro de "data"
PERSIST_DIRECTORY = os.path.join(os.getcwd(), "data", "chroma_db")
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vector_store = Chroma(
    collection_name="arth_long_term_memory",
    embedding_function=embeddings,
    persist_directory=PERSIST_DIRECTORY
)

@tool
def save_memory(fact: str, context: str = "") -> str:
    """
    Salva uma informa\'E7\'E3o importante, fato, prefer\'EAncia do usu\'E1rio ou evento na mem\'F3ria de Longo Prazo.
    Use esta ferramenta SEMPRE que o usu\'E1rio falar algo sobre ele mesmo (ex: "Meu nome \'E9 X", "Eu gosto de Y", "Meu email \'E9 Z") 
    ou quando voc\'EA processar uma informa\'E7\'E3o longa que precisa ser lembrada no futuro.
    - fact: A informa\'E7\'E3o principal a ser salva (ex: "O usu\'E1rio se chama Gean").
    - context: Detalhes adicionais (opcional).
    """
    try:
        doc = f"FATO: {fact}\nCONTEXTO: {context}"
        vector_store.add_texts([doc])
        return f"Mem\'F3ria salva com sucesso: '{fact}'"
    except Exception as e:
        return f"Erro ao salvar na mem\'F3ria: {str(e)}"

@tool
def search_memory(query: str, n_results: int = 3) -> str:
    """
    Busca na mem\'F3ria de Longo Prazo do Arth por fatos, nomes, documentos ou a\'E7\'F5es passadas.
    Use isso se voc\'EA precisar lembrar quem \'E9 o usu\'E1rio, o que ele gosta, ou consultar algo que voc\'EA salvou antes.
    - query: O que voc\'EA est\'E1 buscando (ex: "Qual \'E9 o nome do usu\'E1rio?", "Resumo da reuni\'E3o XYZ").
    """
    try:
        results = vector_store.similarity_search(query, k=n_results)
        if not results:
            return f"Nenhuma mem\'F3ria encontrada para: {query}"
            
        memories = [f"- {res.page_content}" for res in results]
        return "Mem\'F3rias encontradas:\n" + "\n".join(memories)
    except Exception as e:
        return f"Erro ao buscar na mem\'F3ria: {str(e)}"
