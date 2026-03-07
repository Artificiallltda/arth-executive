import os
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
    msg = result["messages"][-1]
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
options = ["FINISH", "arth_approval"] + members

class RouteResponse(BaseModel):
    next_agent: Literal["FINISH", "arth_researcher", "arth_planner", "arth_executor", "arth_qa", "arth_analyst", "arth_approval"]
    final_answer: Optional[str] = ""
    requires_approval: bool = False

orchestrator_persona = load_persona("orchestrator.md")
# Melhoramos o prompt para ser mais explícito com as regras de segurança
prompt = ChatPromptTemplate.from_messages([
    ("system", orchestrator_persona),
    MessagesPlaceholder(variable_name="messages"),
    ("system", (
        "Quem deve atuar agora? Escolha um de: {options}.\n\n"
        "REGRA DE OURO DE SEGURANÇA:\n"
        "Se a próxima ação for para o @arth-executor e envolver IMAGENS, PYTHON ou AGENDAMENTOS, "
        "defina 'requires_approval=True' IMEDIATAMENTE. Não pule esta etapa."
    )),
]).partial(options=str(options), members=", ".join(members))

supervisor_chain = prompt | llm_with_fallbacks.with_structured_output(RouteResponse)

async def supervisor_node(state: AgentState):
    is_approved = state.get("approval_status") == "approved"
    messages = list(state.get("messages", []))
    
    # --- CAMADA DE SEGURANÇA INTELIGENTE ---
    # Busca gatilho apenas na última interação humana para evitar loops com histórico antigo
    last_human_msg = next((m for m in reversed(messages) if m.type == "human"), None)
    found_trigger = False
    if last_human_msg:
        critical_triggers = ["imagem", "image", "gerar", "crie", "create", "pdf", "docx", "pptx", "python", "agende", "lembrete", "reminder"]
        found_trigger = any(t in str(last_human_msg.content).lower() for t in critical_triggers)
    
    # Se já houve uma execução de ferramenta com sucesso (tag de arquivo presente), não bloqueia
    has_file = any("<SEND_FILE:" in str(m.content) for m in messages if m.type == "ai")
    
    needs_hard_approval = found_trigger and not is_approved and not has_file

    if is_approved:
        messages.append(SystemMessage(content="SISTEMA: Ação já autorizada pelo usuário. Prossiga para a execução."))

    # Chamada do modelo de roteamento com limite expandido
    routing_result = await supervisor_chain.ainvoke({**state, "messages": messages})

    # Força a rota de aprovação se necessário
    if needs_hard_approval and routing_result.next_agent == "arth_executor":
        routing_result.next_agent = "arth_approval"
        routing_result.requires_approval = True

    # Bypass Absoluto: Se já aprovado, nunca mais pede aprovação nesta thread
    if is_approved:
        routing_result.requires_approval = False
        if routing_result.next_agent == "arth_approval":
            routing_result.next_agent = "arth_executor"

    logger.info(f"[ROUTER] De: supervisor | Para: {routing_result.next_agent} | Approval: {routing_result.requires_approval}")

    # --- LÓGICA DE FINALIZAÇÃO (Preserva Mídias e Evita Hallucinação) ---
    if routing_result.next_agent == "FINISH":
        # Procura a última mensagem de um especialista que contenha uma tag
        last_specialist_msg = next((m for m in reversed(messages) if m.type == "ai" and m.name in members), None)
        
        if last_specialist_msg and any(tag in str(last_specialist_msg.content) for tag in ["<SEND_FILE:", "<SEND_AUDIO:"]):
            logger.info(f"[Supervisor] Finalizando com mídia detectada em {last_specialist_msg.name}")
            return {"next_agent": "FINISH", "requires_approval": False}
        
        return {
            "next_agent": "FINISH", 
            "requires_approval": False,
            "messages": [AIMessage(content=routing_result.final_answer or "Tarefa concluída.", name="arth_orchestrator")]
        }
    
    # --- ROTA DE APROVAÇÃO ---
    if routing_result.requires_approval:
        logger.warning("[⚠️ HITL] Bloqueio preventivo. Aguardando aprovação explícita.")
        content = "[⚠️ Ação Crítica] Esta tarefa exige execução de comandos.\n\n**Você autoriza o Arth a prosseguir?** (Responda 'Sim' ou 'Ok')"
        return {
            "next_agent": "arth_approval", 
            "requires_approval": True,
            "messages": [AIMessage(content=content, name="arth_orchestrator")]
        }
        
    return {
        "next_agent": routing_result.next_agent, 
        "requires_approval": False, # Reset obrigatório
        "approval_status": "approved" if is_approved else "none"
    }

async def approval_node(state: AgentState):
    return {
        "approval_status": "approved", 
        "requires_approval": False, # Fundamental para quebrar o loop
        "messages": [AIMessage(content="Autorização confirmada! Prosseguindo... 🚀⚙️", name="arth_approval")]
    }

def build_arth_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("arth_orchestrator", supervisor_node)
    workflow.add_node("arth_researcher", researcher_node)
    workflow.add_node("arth_planner", planner_node)
    workflow.add_node("arth_executor", executor_node)
    workflow.add_node("arth_qa", qa_node)
    workflow.add_node("arth_analyst", analyst_node)
    workflow.add_node("arth_approval", approval_node)
    
    workflow.add_edge(START, "arth_orchestrator")
    for member in members:
        workflow.add_edge(member, "arth_orchestrator")
    workflow.add_edge("arth_approval", "arth_orchestrator")
        
    workflow.add_conditional_edges(
        "arth_orchestrator",
        lambda state: state["next_agent"],
        {k: k for k in members} | {"FINISH": END, "arth_approval": "arth_approval"}
    )
    return workflow
