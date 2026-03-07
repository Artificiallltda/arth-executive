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

# --- Setup dos Modelos (Orquestrador + Personas) ---
openai_llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0)
gemini_llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY, 
    temperature=0
)

# Define quem entra primeiro no ringue
if settings.PRIMARY_MODEL == "gemini":
    logger = logging.getLogger(__name__) # Ensure logger exists or use print
    print("[OK] Usando Gemini como motor principal.")
    llm_with_fallbacks = gemini_llm.with_fallbacks([openai_llm])
else:
    llm_with_fallbacks = openai_llm.with_fallbacks([gemini_llm])

# --- Carregamento de Personas (AIOS Ecosystem) ---
def load_persona(agent_filename: str) -> str:
    path = os.path.join(settings.SQUAD_PATH, agent_filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"[\u26a0\ufe0f ERRO] Persona n\u00e3o encontrada: {path}")
        return f"Voc\u00ea \u00e9 o agente {agent_filename}. Atue com profissionalismo."

# --- Divisão de Tools por Especialidade ---
RESEARCHER_TOOLS = [search_web, search_memory, save_memory, query_knowledge_base]
PLANNER_TOOLS = [get_current_time, search_memory, save_memory, analyze_data_file]
EXECUTOR_TOOLS = [execute_python_code, generate_docx, generate_pdf, generate_image, generate_pptx, generate_audio, schedule_reminder, ask_chefia, audit_supabase_security, audit_database_schema, search_memory, save_memory, upload_document_to_knowledge_base]
QA_TOOLS = [search_memory, save_memory]
ANALYST_TOOLS = [analyze_data_file, audit_supabase_security, audit_database_schema, search_memory, save_memory]

# --- Criação dos Agentes Especialistas (Nós) ---
def create_specialist_agent(tools, system_prompt: str):
    # O create_react_agent gerencia o próprio loop de tool internamente
    return create_react_agent(model=llm_with_fallbacks, tools=tools, prompt=system_prompt)

# Inicialização com Personas Externas
researcher_agent = create_specialist_agent(RESEARCHER_TOOLS, load_persona("researcher.md"))
planner_agent = create_specialist_agent(PLANNER_TOOLS, load_persona("planner.md"))
executor_agent = create_specialist_agent(EXECUTOR_TOOLS, load_persona("executor.md"))
qa_agent = create_specialist_agent(QA_TOOLS, load_persona("qa.md"))
analyst_agent = create_specialist_agent(ANALYST_TOOLS, load_persona("analyst.md"))

# Fun\u00e7\u00e3o Helper para rodar o sub-agente
def agent_node(state, agent, name):
    # Aumentamos o limite interno de recurs\u00e3o para o sub-agente
    result = agent.invoke(state, {"recursion_limit": 25})
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
# Adicionamos o nó de aprovação à lista de opções técnicas
options = ["FINISH", "arth_approval"] + members

class RouteResponse(BaseModel):
    next_agent: Literal["FINISH", "arth_researcher", "arth_planner", "arth_executor", "arth_qa", "arth_analyst"]
    final_answer: str = ""
    requires_approval: bool = False # Campo novo para o Orchestrator sinalizar

orchestrator_persona = load_persona("orchestrator.md")
system_prompt = (
    f"{orchestrator_persona}\n\n"
    "3. SEGURANÇA: Se o próximo passo envolver EXECUÇÃO DE CÓDIGO (Python) ou AGENDAMENTOS/CALENDÁRIO, defina requires_approval=True.\n"
    "   -> REGRA DE OURO: Se você estiver prestes a enviar para o @arth-executor pela PRIMEIRA VEZ para uma dessas tarefas, VOCÊ DEVE pedir aprovação primeiro (requires_approval=True).\n"
    "   -> EXCEÇÃO: Se o histórico mostrar que VOCÊ JÁ PERGUNTOU se podia fazer isso e o usuário respondeu 'Sim/Pode/Ok' (ou similar), defina requires_approval=False.\n"
    "4. SEMPRE passe pelo @arth-qa se houver arquivos gerados para conferência."
)

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="messages"),
    ("system", "Quem deve atuar agora? Escolha um de: {options}"),
]).partial(options=str(options), members=", ".join(members))

supervisor_chain = prompt | llm_with_fallbacks.with_structured_output(RouteResponse)

def supervisor_node(state: AgentState):
    print(f"[\u2699\uFE0F Arth Orchestrator] Gerenciando fluxo para: {state.get('sender', 'user')}")
    
    # Se já fomos aprovados, preparamos o reset, mas continuamos o roteamento
    update_data = {}
    if state.get("approval_status") == "approved":
         update_data["approval_status"] = "none"

    routing_result = supervisor_chain.invoke(state)
    
    if routing_result.next_agent == "FINISH":
        content = routing_result.final_answer or "Processo concluído com sucesso."
        update_data.update({"next_agent": "FINISH", "messages": [AIMessage(content=content, name="arth_orchestrator")]})
        return update_data
    
    # Se o orquestrador pediu aprovação, desviamos para o nó de aprovação
    if routing_result.requires_approval:
        print("[\u26A0\uFE0F HITL] A\u00e7\u00e3o cr\u00edtica detectada. Encaminhando para aprova\u00e7\u00e3o.")
        update_data.update({"next_agent": "arth_approval", "requires_approval": True})
        return update_data
        
    update_data["next_agent"] = routing_result.next_agent
    return update_data

def approval_node(state: AgentState):
    """
    Nó que serve como 'breakpoint'. 
    Quando o grafo atinge este nó, ele será pausado (se configurado com interrupt_before).
    Ao retomar, ele simplesmente marca como aprovado (assumindo que o usuário deu o OK).
    """
    return {
        "approval_status": "approved",
        "requires_approval": False,
        "messages": [AIMessage(content="Aprovado pelo usuário. Prosseguindo...", name="arth_approval")]
    }

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection

# --- Montagem do Grafo ---
def build_arth_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("arth_orchestrator", supervisor_node)
    workflow.add_node("arth_researcher", researcher_node)
    workflow.add_node("arth_planner", planner_node)
    workflow.add_node("arth_executor", executor_node)
    workflow.add_node("arth_qa", qa_node)
    workflow.add_node("arth_analyst", analyst_node)
    workflow.add_node("arth_approval", approval_node) # Novo nó
    
    workflow.add_edge(START, "arth_orchestrator")
    
    for member in members:
        workflow.add_edge(member, "arth_orchestrator")
    
    workflow.add_edge("arth_approval", "arth_orchestrator") # Volta para decidir o próximo
        
    workflow.add_conditional_edges(
        "arth_orchestrator",
        lambda state: state["next_agent"],
        {k: k for k in members} | {"FINISH": END, "arth_approval": "arth_approval"}
    )
    
    # Persistência Profissional (Supabase / Postgres)
    if settings.SUPABASE_DATABASE_URL:
        # Nota: O langgraph-checkpoint-postgres gerencia as tabelas automaticamente
        # Precisamos usar a versão assíncrona para o execute_brain do message_handler
        async def get_checkpointer():
            conn = await AsyncConnection.connect(settings.SUPABASE_DATABASE_URL)
            return AsyncPostgresSaver(conn)
        
        # Como o build_arth_graph() é síncrono no message_handler, 
        # mas o compile() aceita o saver, vamos precisar de um padrão diferente ou 
        # mudar o message_handler.
        # Por enquanto, vamos usar uma gambiarra controlada ou inicializar no message_handler.
        return workflow # Retornamos apenas o workflow para o message_handler compilar assincronamente
    else:
        print("[⚠️ AVISO] SUPABASE_DATABASE_URL não configurada. Usando MemorySaver (volátil).")
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)
