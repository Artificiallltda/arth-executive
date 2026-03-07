from langchain_core.tools import tool
import httpx
import logging
from src.config import settings

logger = logging.getLogger(__name__)

@tool
async def ask_chefia(query: str) -> str:
    """
    Delega uma pergunta gastron\u00f4mica para o ChefIA (Especialista em Culin\u00e1ria).
    Use para: receitas, dicas de cozinha, ingredientes ou card\u00e1pios.
    """
    
    # URL configurada via settings ou fallback local
    chefia_url = getattr(settings, "CHEFIA_API_URL", "http://localhost:8001/chat") 
    
    logger.info(f"Delegando para ChefIA: {query}")
    
    try:
        async with httpx.AsyncClient() as client:
            # Tenta se comunicar com o endpoint do ChefIA
            response = await client.post(chefia_url, json={"message": query}, timeout=30.0)
            
            if response.status_code == 200:
                reply = response.json().get("reply", "O ChefIA enviou uma resposta vazia.")
                return f"Resposta do ChefIA: {reply}"
            else:
                return f"O ChefIA respondeu com erro (Status {response.status_code})."
                
    except Exception as e:
        # Fallback amig\u00e1vel caso o outro agente esteja offline
         return (
             f"O ChefIA est\u00e1 ocupado na cozinha no momento (Offline). "
             f"Mas como sou um assistente executivo, posso tentar pesquisar na web para você se desejar!"
         )
