from typing import TypedDict, Annotated, List, Optional, Any
import operator
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    Estado do Arth Executive AI - Blindado contra perda de contexto e falha de entrega.
    """
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    sender: str
    user_id: str
    channel: str
    requires_approval: bool
    approval_status: str # "pending", "approved", "rejected"
    # Campos de transferência de dados
    user_input: str      # Input original do usuário
    content: str         # Conteúdo rico (pesquisas, textos)
    media_context: Optional[str] 
    force_delivery: bool 
    # Rastreamento de Entrega
    generated_files: List[str] # Lista de caminhos gerados
    delivered_files: List[str] # Lista de arquivos já enviados (evita duplicidade)
