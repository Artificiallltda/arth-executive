import os
import logging
from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver

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

# --- Setup dos Modelos (Orquestrador + Personas) ---
openai_llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0)
gemini_llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY, 
    temperature=0
)

if settings.PRIMARY_MODEL == "gemini":
    llm_with_fallbacks = gemini_llm.with_fallbacks([openai_llm])
else:
    llm_with_fallbacks = openai_llm.with_fallbacks([gemini_llm])

# --- Carregamento de Personas ---
def load_persona(agent_filename: str) -> str:
    path = os.path.join(settings.SQUAD_PATH, agent_filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Você é o agente {agent_filename}. Atue com profissionalismo."

# --- Divisão de Tools ---
RESEARCHER_TOOLS = [search_web, search_memory, save_memory, query_knowledge_base]
PLANNER_TOOLS = [get_current_time, search_memory, save_memory, analyze_data_file]
EXECUTOR_TOOLS = [execute_python_code, generate_docx, generate_pdf, generate_image, generate_pptx, generate_audio, schedule_reminder, ask_chefia, audit_supabase_security, audit_database_schema, search_memory, save_memory, upload_document_to_knowledge_base]
QA_TOOLS = [search_memory, save_memory]
ANALYST_TOOLS = [analyze_data_file, audit_supabase_security, audit_database_schema, search_memory, save_memory]

def create_specialist_agent(tools, system_prompt: str):
    return create_react_agent(model=llm_with_fallbacks, tools=tools, prompt=system_prompt)

researcher_agent = create_specialist_agent(RESEARCHER_TOOLS, load_persona("researcher.md"))
planner_agent = create_specialist_agent(PLANNER_TOOLS, load_persona("planner.md"))
executor_agent = create_specialist_agent(EXECUTOR_TOOLS, load_persona("executor.md"))
qa_agent = create_specialist_agent(QA_TOOLS, load_persona("qa.md"))
analyst_agent = create_specialist_agent(ANALYST_TOOLS, load_persona("analyst.md"))

# Função Helper para rodar o sub-agente de forma assíncrona
async def agent_node(state, agent, name):
    # Aumentamos o limite interno de recursão para o sub-agente
    # NOVO: Usamos ainvoke para suportar StructuredTools
    result = await agent.ainvoke(state, {"recursion_limit": 25})
    last_msg = result["messages"][-1]
    return {
        "messages": [AIMessage(content=last_msg.content, name=name)],
        "sender": name
    }

def researcher_node(state): return agent_node(state, researcher_agent, "arth_researcher")
def planner_node(state): return agent_node(state, planner_agent, "arth_planner")
def executor_node(state): return agent_node(state, executor_agent, "arth_executor")
def qa_node(state): return agent_node(state, qa_agent, "arth_qa")
def analyst_node(state): return agent_node(state, analyst_agent, "arth_analyst")

# --- Orquestrador (Supervisor Node) ---
members = ["arth_researcher", "arth_planner", "arth_executor", "arth_qa", "arth_analyst"]
options = ["FINISH", "arth_approval"] + members

class RouteResponse(BaseModel):
    next_agent: Literal["FINISH", "arth_researcher", "arth_planner", "arth_executor", "arth_qa", "arth_analyst"]
    final_answer: str = ""
    requires_approval: bool = False

orchestrator_persona = load_persona("orchestrator.md")
system_prompt = (
    f"{orchestrator_persona}\n\n"
    "3. SEGURANÇA: Se o próximo passo envolver EXECUÇÃO DE CÓDIGO (Python) ou AGENDAMENTOS/CALENDÁRIO, defina requires_approval=True.\n"
    "   -> REGRA DE OURO: Se você estiver prestes a enviar para o @arth-executor pela PRIMEIRA VEZ para uma dessas tarefas, VOCÊ DEVE pedir aprovação primeiro.\n"
    "   -> EXCEÇÃO: Se o histórico mostrar que VOCÊ JÁ PERGUNTOU e o usuário deu OK, defina requires_approval=False.\n"
    "4. SEMPRE passe pelo @arth-qa se houver arquivos gerados."
)

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="messages"),
    ("system", "Quem deve atuar agora? Escolha um de: {options}"),
]).partial(options=str(options), members=", ".join(members))

supervisor_chain = prompt | llm_with_fallbacks.with_structured_output(RouteResponse)

async def supervisor_node(state: AgentState):
    logger.info(f"[Orquestrador] Gerenciando fluxo para: {state.get('sender', 'user')}")
    
    is_approved = state.get("approval_status") == "approved"
    update_data = {}
    messages = list(state.get("messages", []))
    
    if is_approved:
        logger.info("[HITL] Aprovação confirmada no estado.")
        messages.append(SystemMessage(content="SISTEMA: O usuário já AUTORIZOU esta ação. Prossiga para a execução IMEDIATAMENTE."))

    routing_result = await supervisor_chain.ainvoke({**state, "messages": messages})

    # BYPASS GOD MODE: Se já foi aprovado, bloqueamos o loop de aprovação
    if is_approved and (routing_result.requires_approval or routing_result.next_agent == "arth_approval"):
        logger.warning("[FORCE] Ignorando flag de aprovação redundante.")
        routing_result.requires_approval = False
        if routing_result.next_agent == "arth_approval":
            routing_result.next_agent = "arth_executor" # Destino mais comum
        update_data["approval_status"] = "none" # Reset apenas após o uso

    if routing_result.next_agent == "FINISH":
        content = routing_result.final_answer or "Processo concluído."
        return {**update_data, "next_agent": "FINISH", "messages": [AIMessage(content=content, name="arth_orchestrator")]}
    
    if routing_result.requires_approval:
        content = "[⚠️ Ação Crítica] Esta tarefa exige execução de comandos.\n\n**Você autoriza o Arth a prosseguir?** (Responda 'Sim' ou 'Ok')"
        return {
            **update_data,
            "next_agent": "arth_approval", 
            "requires_approval": True,
            "messages": [AIMessage(content=content, name="arth_orchestrator")]
        }
        
    return {**update_data, "next_agent": routing_result.next_agent}

def approval_node(state: AgentState):
    return {
        "approval_status": "approved",
        "requires_approval": False,
        "messages": [AIMessage(content="Aprovado pelo usuário. Prosseguindo...", name="arth_approval")]
    }

# --- Montagem do Grafo ---
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
