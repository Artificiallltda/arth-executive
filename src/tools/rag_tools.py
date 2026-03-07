import os
import logging
import uuid
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from src.config import settings

logger = logging.getLogger(__name__)

# Configura o diret\u00f3rio do ChromaDB local (dentro de data/chroma)
CHROMA_DB_DIR = os.path.join(settings.BASE_DIR, "data", "chroma")
COLLECTION_NAME = "corporate_knowledge"

def get_vector_store():
    """Retorna a inst\u00e2ncia do ChromaDB para opera\u00e7\u00f5es."""
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY n\u00e3o configurada para RAG.")
        
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=settings.OPENAI_API_KEY)
    
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_DB_DIR
    )

@tool
def query_knowledge_base(query: str) -> str:
    """
    Busca informa\u00e7\u00f5es na Base de Conhecimento Corporativa (RAG) da empresa.
    Use esta ferramenta SEMPRE que o usu\u00e1rio fizer perguntas sobre regras internas, 
    manuais, pol\u00edticas, hist\u00f3rico de funcion\u00e1rios ou dados espec\u00edficos do neg\u00f3cio.
    
    Par\u00e2metro:
    - query: A pergunta ou tema a ser pesquisado (ex: 'Qual a pol\u00edtica de f\u00e9rias?').
    """
    try:
        if not os.path.exists(CHROMA_DB_DIR):
            return "A Base de Conhecimento Corporativa est\u00e1 vazia no momento."
            
        vectorstore = get_vector_store()
        
        # Busca os 3 documentos mais relevantes
        docs = vectorstore.similarity_search(query, k=3)
        
        if not docs:
            return f"Nenhuma informa\u00e7\u00e3o encontrada na base corporativa para: {query}"
            
        # Formata a sa\u00edda para o LLM
        result = "Informa\u00e7\u00f5es encontradas nos Manuais Corporativos:\n\n"
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", "Documento Desconhecido")
            result += f"--- [Fonte: {source}] ---\n{doc.page_content}\n\n"
            
        return result
        
    except Exception as e:
        logger.error(f"Erro na busca RAG: {e}")
        return f"Falha ao consultar o banco de dados corporativo: {str(e)}"

@tool
def upload_document_to_knowledge_base(content: str, title: str) -> str:
    """
    Salva e indexa um novo documento, manual ou regra na Base de Conhecimento da Empresa.
    
    Use esta ferramenta quando o usu\u00e1rio te ensinar algo novo sobre a empresa ou pedir 
    para voc\u00ea "aprender", "memorizar" ou "guardar na base" uma pol\u00edtica, contrato ou procedimento.
    
    Par\u00e2metros:
    - content: O texto completo que deve ser memorizado (ex: o texto do manual).
    - title: O nome da fonte ou t\u00edtulo do documento (ex: 'Manual de Vendas 2026').
    """
    try:
        os.makedirs(CHROMA_DB_DIR, exist_ok=True)
        vectorstore = get_vector_store()
        
        # Cria o documento com metadados para indexa\u00e7\u00e3o vetorial
        doc_id = str(uuid.uuid4())
        document = Document(
            page_content=content,
            metadata={"source": title, "doc_id": doc_id}
        )
        
        vectorstore.add_documents([document])
        # N\u00e3o \u00e9 mais necess\u00e1rio chamar persist() no Chroma v0.4.x+, ele salva automatico.
        
        return f"Sucesso! O documento '{title}' foi indexado na Base de Conhecimento e j\u00e1 pode ser pesquisado."
        
    except Exception as e:
        logger.error(f"Erro ao salvar na base RAG: {e}")
        return f"Falha ao indexar o documento: {str(e)}"

