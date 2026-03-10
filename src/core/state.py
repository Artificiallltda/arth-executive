from typing import TypedDict, Annotated, List, Optional, Any
import operator
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    Estado do Arth Executive AI - Blindado contra perda de contexto.
    """
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    sender: str
    user_id: str
    channel: str
    requires_approval: bool
    approval_status: str # "pending", "approved", "rejected"
    # Campos de transferência de dados entre agentes
    user_input: str      # Input original do usuário para este turno
    content: str         # Conteúdo rico gerado por um agente (ex: pesquisa) para o próximo
    media_context: Optional[str] 
    force_delivery: bool # Sinalizador para entrega proativa
