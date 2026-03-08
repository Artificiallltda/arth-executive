import os
import re
import logging
from typing import Literal, Optional, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from src.core.state import AgentState
from src.tools.basic_tools import get_current_time
from src.tools.web_search import search_web
from src.tools.doc_generator import generate_docx, generate_pdf
from src.tools.code_executor import execute_python_code
from src.tools.memory_tools import save_memory, search_memory
from src.tools.chefia_integration import ask_chefia
from src.tools.image_generator import generate_image
from src.tools.data_analyst import analyze_data_file
from src.tools.scheduler_tools import schedule_reminder
from src.tools.pptx_generator import generate_pptx
from src.tools.database_tools import audit_supabase_security, audit_database_schema
from src.tools.audio_generator import generate_audio
from src.tools.rag_tools import query_knowledge_base, upload_document_to_knowledge_base
from src.config import settings

logger = logging.getLogger(__name__)

# --- Setup dos Modelos ---
openai_llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0)
gemini_llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY, 
    temperature=0
)

llm_with_fallbacks = openai_llm.with_fallbacks([gemini_llm]) if settings.PRIMARY_MODEL != "gemini" else gemini_llm.with_fallbacks([openai_llm])

# --- Carregamento de Personas ---
def load_persona(agent_filename: str) -> str:
    path = os.path.join(settings.SQUAD_PATH, agent_filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Você é o agente {agent_filename}. Atue com profissionalismo."

# --- Ferramentas ---
ALL_TOOLS = [
    get_current_time, search_web, generate_docx, generate_pdf, 
    execute_python_code, save_memory, search_memory, ask_chefia, 
    generate_image, analyze_data_file, schedule_reminder, 
    generate_pptx, audit_supabase_security, audit_database_schema, 
    generate_audio, query_knowledge_base, upload_document_to_knowledge_base
]

# --- Criação dos Agentes Especialistas ---
# NOVO: Forçamos o uso do loop de ferramenta assíncrono
def create_specialist_agent(tools, system_prompt: str):
    return create_react_agent(model=llm_with_fallbacks, tools=tools, prompt=system_prompt)

researcher_agent = create_specialist_agent([search_web, search_memory, save_memory, query_knowledge_base], load_persona("researcher.md"))
planner_agent = create_specialist_agent([get_current_time, search_memory, save_memory, analyze_data_file], load_persona("planner.md"))
executor_agent = create_specialist_agent(ALL_TOOLS, load_persona("executor.md")) # Executor tem acesso a tudo
qa_agent = create_specialist_agent([search_memory, save_memory], load_persona("qa.md"))
analyst_agent = create_specialist_agent([analyze_data_file, audit_supabase_security, audit_database_schema, search_memory, save_memory], load_persona("analyst.md"))

async def agent_node(state, agent, name):
    messages = list(state.get("messages", []))

    # Injeta contexto de canal/usuário para ferramentas que precisam (ex: schedule_reminder)
    user_id = state.get("user_id", "")
    channel = state.get("channel", "")
    if user_id and channel:
        messages = [SystemMessage(
            content=(
                f"[CONTEXTO DE SISTEMA]: Canal ativo='{channel}', user_id='{user_id}'. "
                f"Use esses valores EXATOS ao chamar ferramentas que exigem user_id ou channel."
            )
        )] + messages

    result = await agent.ainvoke({**state, "messages": messages}, RunnableConfig(recursion_limit=25))
    inner_messages = result["messages"]
    msg = inner_messages[-1]

    # Normaliza content de modelos com blocos estruturados (ex: Gemini 2.5 thinking mode).
    # Sem isso, msg.content vira {'type': 'text', 'text': '...', 'extras': {...}} em string crua.
    original_type = type(msg.content).__name__
    if not isinstance(msg.content, str):
        if isinstance(msg.content, list):
            text_parts = [b.get('text', '') for b in msg.content
                          if isinstance(b, dict) and b.get('type') == 'text']
            clean = '\n'.join(filter(None, text_parts))
        elif isinstance(msg.content, dict) and msg.content.get('type') == 'text':
            clean = msg.content.get('text', '')
        else:
            clean = str(msg.content)
        if clean:
            msg = msg.model_copy(update={"content": clean})
            logger.info(f"[{name}] content normalizado: {original_type} → str ({len(clean)} chars)")
        else:
            logger.warning(f"[{name}] content normalização falhou: tipo={original_type}, valor={str(msg.content)[:100]}")

    # Garante que tags de arquivo/áudio geradas por ferramentas cheguem ao estado externo.
    # Escaneia APENAS ToolMessages (resultados das ferramentas desta execução),
    # não o histórico de mensagens que pode conter tags de conversas anteriores.
    tool_messages = [m for m in inner_messages if getattr(m, "type", "") == "tool"]
    tool_text = " ".join(str(m.content) for m in tool_messages)
    file_tags = re.findall(r'<(?:SEND_FILE|SEND_AUDIO):[^>]+>', tool_text)
    if file_tags:
        msg_content = str(msg.content) if not isinstance(msg.content, str) else msg.content
        missing = [t for t in file_tags if t not in msg_content]
        if missing:
            msg = msg.model_copy(update={"content": msg_content + "\n" + "\n".join(missing)})

    msg.name = name
    return {
        "messages": [msg],
        "sender": name
    }

async def researcher_node(state): return await agent_node(state, researcher_agent, "arth_researcher")
async def planner_node(state): return await agent_node(state, planner_agent, "arth_planner")
async def executor_node(state): return await agent_node(state, executor_agent, "arth_executor")
async def qa_node(state): return await agent_node(state, qa_agent, "arth_qa")
async def analyst_node(state): return await agent_node(state, analyst_agent, "arth_analyst")

# --- Orquestrador (Supervisor) ---
members = ["arth_researcher", "arth_planner", "arth_executor", "arth_qa", "arth_analyst"]
options = ["FINISH"] + members

class RouteResponse(BaseModel):
    next_agent: Literal["FINISH", "arth_researcher", "arth_planner", "arth_executor", "arth_qa", "arth_analyst"]
    final_answer: str = "" # Removido Optional para evitar Erro de Serialização no Pydantic

orchestrator_persona = load_persona("orchestrator.md")
prompt = ChatPromptTemplate.from_messages([
    ("system", orchestrator_persona),
    MessagesPlaceholder(variable_name="messages"),
    ("system", "Quem deve atuar agora? Escolha um de: {options}."),
]).partial(options=str(options), members=", ".join(members))

supervisor_chain = prompt | llm_with_fallbacks.with_structured_output(RouteResponse)

async def supervisor_node(state: AgentState):
    messages = list(state.get("messages", []))

    # Guarda: se já foi gerado um arquivo desde o último HumanMessage, encerra imediatamente.
    # Evita que o orquestrador invoque o executor múltiplas vezes por rodada.
    last_human_idx = 0
    for i, m in enumerate(messages):
        if m.type == "human":
            last_human_idx = i
    for m in messages[last_human_idx + 1:]:
        if m.type == "ai" and getattr(m, "name", "") in members:
            if any(tag in str(m.content) for tag in ["<SEND_FILE:", "<SEND_AUDIO:"]):
                logger.info(f"[Supervisor] Arquivo já gerado por {m.name}, encerrando rodada.")
                return {"next_agent": "FINISH"}

    routing_result = await supervisor_chain.ainvoke(state)
    logger.info(f"[ROUTER] Para: {routing_result.next_agent}")

    if routing_result.next_agent == "FINISH":
        messages = list(state.get("messages", []))
        # Se o último especialista já deu uma resposta rica (com arquivo ou texto longo), NÃO adicionamos nada em cima.
        last_specialist_msg = next((m for m in reversed(messages) if m.type == "ai" and m.name in members), None)

        if last_specialist_msg:
            logger.info(f"[Supervisor] Finalizando. Preservando resposta de {last_specialist_msg.name}")
            return {"next_agent": "FINISH"}

        # Caso contrário, o orquestrador responde diretamente.
        return {
            "next_agent": "FINISH",
            "messages": [AIMessage(content=routing_result.final_answer or "Processamento concluído.", name="arth_orchestrator")]
        }

    return {"next_agent": routing_result.next_agent}

def build_arth_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("arth_orchestrator", supervisor_node)
    workflow.add_node("arth_researcher", researcher_node)
    workflow.add_node("arth_planner", planner_node)
    workflow.add_node("arth_executor", executor_node)
    workflow.add_node("arth_qa", qa_node)
    workflow.add_node("arth_analyst", analyst_node)

    workflow.add_edge(START, "arth_orchestrator")
    for member in members:
        workflow.add_edge(member, "arth_orchestrator")

    workflow.add_conditional_edges(
        "arth_orchestrator",
        lambda state: state["next_agent"],
        {k: k for k in members} | {"FINISH": END}
    )
    return workflow
