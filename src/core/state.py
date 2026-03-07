from typing import TypedDict, Annotated, List, Optional
import operator
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    O estado M\u00ednimo do Arth.
    """
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    sender: str
    user_id: str
    channel: str
    requires_approval: bool
    approval_status: str # "pending", "approved", "rejected"
    # Novo: Contexto de M\u00eddia (Base64 ou URL da imagem de refer\u00eancia)
    media_context: Optional[str] 
