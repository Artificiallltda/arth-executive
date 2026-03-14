import os
import re
import logging
import asyncio
import json
import time
from datetime import datetime
from typing import Literal, Optional, List, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from src.core.state import AgentState
from src.tools.basic_tools import get_current_time
from src.tools.web_search import search_web
from src.tools.web_reader import read_url
from src.tools.document_reader import read_document
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
from src.tools.excel_tools import create_excel, append_to_excel, read_excel
from src.core.capabilities import can_agent_generate, get_agent_for_file_type
from src.core.agents.arth_analyst import arth_analyst_processor
from src.config import settings

logger = logging.getLogger(__name__)

# --- Setup dos Modelos (Blindagem Manus AI) ---
# Timeouts e Retries configurados globalmente
LLM_TIMEOUT = 90
MAX_RETRIES = 3

def get_gemini_model(model_name: str, temperature: float = 0):
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=settings.GEMINI_API_KEY,
        max_retries=MAX_RETRIES,
        timeout=LLM_TIMEOUT,
        disable_search=True
    )

supervisor_llm = get_gemini_model("gemini-2.0-pro-exp-02-05") # Atualizado para versão estável pro
executor_llm = get_gemini_model("gemini-2.0-flash") # Conforme manual: Flash é 3x mais rápido

deepseek_llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=settings.DEEPSEEK_API_KEY,
    openai_api_base="https://api.deepseek.com",
    temperature=0.3,
    max_retries=MAX_RETRIES,
    timeout=LLM_TIMEOUT
)

def load_persona(agent_filename: str) -> str:
    path = os.path.join(settings.SQUAD_PATH, agent_filename)
    persona = ""
    def _read_file_safe(file_path):
        for enc in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(file_path, "r", encoding=enc) as f: return f.read()
            except: continue
        with open(file_path, "r", encoding='utf-8', errors='replace') as f: return f.read()
    try:
        if os.path.exists(path): persona = _read_file_safe(path)
        else: persona = f"Você é o agente {agent_filename}."
    except Exception as e:
        logger.error(f"[CORE] Erro persona {agent_filename}: {e}")
        persona = f"Você é o agente {agent_filename}."
    
    shared_memory_path = os.path.join(settings.BASE_DIR, "data", "ai-reputation-dossier.md")
    if os.path.exists(shared_memory_path):
        try:
            shared = _read_file_safe(shared_memory_path)[:25000]
            persona = f"{persona}\n\n### CONTEXTO DA MARCA:\n{shared}"
        except: pass
    return persona

def create_specialist_agent(tools, system_prompt: str, model_instance):
    safe_tools = [t for t in tools if t is not None]
    return create_react_agent(model=model_instance, tools=safe_tools, prompt=system_prompt)

# Agentes
researcher_agent = create_specialist_agent([search_web, read_url, read_document, search_memory, save_memory, query_knowledge_base], load_persona("researcher.md"), deepseek_llm)
planner_agent = create_specialist_agent([get_current_time, search_memory, save_memory, schedule_reminder], load_persona("planner.md"), deepseek_llm)
analyst_agent = create_specialist_agent([analyze_data_file, read_document, read_excel, audit_supabase_security, audit_database_schema, search_memory, save_memory], load_persona("analyst.md"), deepseek_llm)
executor_agent = create_specialist_agent([
    get_current_time, execute_python_code, save_memory, search_memory, 
    ask_chefia, generate_image, generate_audio, upload_document_to_knowledge_base,
    generate_docx, generate_pdf, generate_pptx, create_excel, append_to_excel
], load_persona("executor.md"), executor_llm)
qa_agent = create_specialist_agent([search_memory, save_memory], load_persona("qa.md"), supervisor_llm)

async def agent_node(state, agent, name):
    messages = list(state.get("messages", []))
    if len(messages) > 30:
        if messages and getattr(messages[0], "type", "") == "system":
            messages = [messages[0]] + messages[-29:]
        else: messages = messages[-30:]
            
    # Blindagem de Execução com Timeout
    try:
        result = await asyncio.wait_for(
            agent.ainvoke({**state, "messages": messages}, RunnableConfig(recursion_limit=50)),
            timeout=LLM_TIMEOUT + 10
        )
    except asyncio.TimeoutError:
        logger.error(f"[NODE] Timeout crítico no agente {name}")
        error_msg = AIMessage(content=f"⚠️ O agente {name} demorou muito para responder. Tentando simplificar...", name=name)
        return {"messages": [error_msg], "sender": name}

    msg = result["messages"][-1]
    def extract_text(content):
        if isinstance(content, str): return content
        if isinstance(content, list): return " ".join(extract_text(part) for part in content)
        if isinstance(content, dict): return content.get("text", content.get("content", str(content)))
        return str(content)

    content_str = extract_text(msg.content)
    if content_str.startswith("[{'type': 'text'"):
        try:
            import ast
            parsed = ast.literal_eval(content_str)
            if isinstance(parsed, list) and len(parsed) > 0: content_str = parsed[0].get("text", content_str)
        except: pass

    tool_messages = [m for m in result["messages"] if getattr(m, "type", "") == "tool"]
    tool_text = " ".join(str(m.content) for m in tool_messages)
    file_tags = re.findall(r'<(?:SEND_FILE|SEND_AUDIO):([^>]+)>', tool_text)
    has_main_doc = any(f.lower().endswith(('.pptx', '.pdf', '.docx', '.xlsx')) for f in file_tags)
    
    for tag in file_tags:
        if has_main_doc and tag.lower().startswith('img-'): continue
        t_str = f"<SEND_FILE:{tag}>"
        if t_str not in content_str: content_str += f"\n{t_str}"
        
    msg = msg.model_copy(update={"content": content_str, "name": name})
    return {"messages": [msg], "sender": name, "content": state.get("content", ""), "user_input": state.get("user_input", "")}

async def researcher_node(state): 
    res = await agent_node(state, researcher_agent, "arth_researcher")
    if len(str(res["messages"][-1].content)) > 200: res["content"] = str(res["messages"][-1].content)
    return res

async def planner_node(state): return await agent_node(state, planner_agent, "arth_planner")
async def executor_node(state): return await agent_node(state, executor_agent, "arth_executor")
async def qa_node(state): return await agent_node(state, qa_agent, "arth_qa")
async def analyst_node(state): 
    updated_state = await arth_analyst_processor(state)
    return await agent_node(updated_state, analyst_agent, "arth_analyst")

# --- Supervisor ---
members = ["arth_researcher", "arth_planner", "arth_executor", "arth_qa", "arth_analyst"]
class RouteResponse(BaseModel):
    next_agent: Literal["FINISH", "arth_researcher", "arth_planner", "arth_executor", "arth_qa", "arth_analyst"]
    final_answer: str = ""

orchestrator_persona = load_persona("orchestrator.md")
prompt = ChatPromptTemplate.from_messages([
    ("system", orchestrator_persona),
    MessagesPlaceholder(variable_name="messages"),
    ("system", "Quem deve atuar agora? Escolha um de: {members} ou FINISH."),
]).partial(members=str(members))

supervisor_chain = prompt | supervisor_llm.with_structured_output(RouteResponse)

async def supervisor_node(state: AgentState):
    messages = list(state.get("messages", []))
    last_human_idx = max((i for i, m in enumerate(messages) if m.type == "human"), default=0)
    msgs_this_turn = messages[last_human_idx + 1:]
    specialist_runs = {}
    has_file = False
    for m in msgs_this_turn:
        if m.type == "ai" and getattr(m, "name", "") in members:
            specialist_runs[m.name] = specialist_runs.get(m.name, 0) + 1
            if "<SEND_FILE:" in str(m.content): has_file = True

    if specialist_runs.get("arth_executor", 0) >= 3: return {"next_agent": "FINISH"}

    short_messages = messages[-15:]
    try:
        routing_result = await asyncio.wait_for(
            supervisor_chain.ainvoke({**state, "messages": short_messages}),
            timeout=LLM_TIMEOUT
        )
    except:
        logger.warning("[SUPERVISOR] Falha no roteamento. Encaminhando para FINISH.")
        return {"next_agent": "FINISH"}
    
    user_input = messages[last_human_idx].content.lower()
    needs_file = any(kw in user_input for kw in ["pdf", "docx", "pptx", "excel", "planilha", "imagem", "foto", "apresentação", "apresentacao"])
    has_research = specialist_runs.get("arth_researcher", 0) > 0
    
    if needs_file and not has_file:
        if has_research or specialist_runs.get("arth_executor", 0) == 0: return {"next_agent": "arth_executor"}

    if needs_file and routing_result.next_agent == "FINISH" and not has_file: return {"next_agent": "arth_executor"}

    ret = {"next_agent": routing_result.next_agent}
    if routing_result.next_agent == "FINISH" and routing_result.final_answer:
        ret["messages"] = [AIMessage(content=routing_result.final_answer, name="arth_orchestrator")]
    return ret

def build_arth_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("arth_orchestrator", supervisor_node)
    workflow.add_node("arth_researcher", researcher_node)
    workflow.add_node("arth_planner", planner_node)
    workflow.add_node("arth_executor", executor_node)
    workflow.add_node("arth_qa", qa_node)
    workflow.add_node("arth_analyst", analyst_node)
    workflow.add_edge(START, "arth_orchestrator")
    for member in members: workflow.add_edge(member, "arth_orchestrator")
    workflow.add_conditional_edges("arth_orchestrator", lambda state: state["next_agent"], {k: k for k in members} | {"FINISH": END})
    return workflow
