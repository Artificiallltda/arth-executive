import os
import re
import logging
import asyncio
import json
from datetime import datetime
from typing import Literal, Optional, List, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI

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

async def wait_for_file(file_path: str, max_wait: float = 10.0, check_interval: float = 0.5):
    import os
    import asyncio
    import time
    start = time.time()
    while time.time() - start < max_wait:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return True
        await asyncio.sleep(check_interval)
    return False

# --- Setup dos Modelos ---
# Utilizando as versões mais atuais do Gemini conforme migração do GPT
supervisor_llm = ChatGoogleGenerativeAI(
    model="gemini-3-pro-preview", 
    temperature=0, 
    google_api_key=settings.GEMINI_API_KEY,
    disable_search=True # Evita conflitos com ferramentas de busca manuais
)

# CORREÇÃO: DeepSeek mantém OpenAI, Gemini usa Google nativo
from langchain_openai import ChatOpenAI
deepseek_llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=settings.DEEPSEEK_API_KEY,
    openai_api_base="https://api.deepseek.com",
    temperature=0.3
)

# Executor com Gemini 3.1 Flash (mais rápido para geração de mídia/pptx)
executor_llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview", 
    temperature=0, 
    google_api_key=settings.GEMINI_API_KEY
)
gemini_fallback = ChatGoogleGenerativeAI(model="gemini-3-flash-preview", google_api_key=settings.GEMINI_API_KEY, temperature=0)

def load_persona(agent_filename: str) -> str:
    path = os.path.join(settings.SQUAD_PATH, agent_filename)
    persona = ""

    def _read_file_safe(file_path):
        for enc in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    return f.read()
            except:
                continue
        with open(file_path, "r", encoding='utf-8', errors='replace') as f:
            return f.read()

    try:
        if os.path.exists(path):
            persona = _read_file_safe(path)
        else:
            persona = f"Você é o agente {agent_filename}."
    except Exception as e:
        logger.error(f"[CORE] Erro ao ler persona {agent_filename}: {e}")
        persona = f"Você é o agente {agent_filename}."

    # --- INJEÇÃO DE MEMÓRIA COMPARTILHADA (Dossiê de Reputação) ---
    # Busca o dossiê na pasta de dados do squad
    shared_memory_path = os.path.join(settings.BASE_DIR, "data", "ai-reputation-dossier.md")
    shared_content = ""
    if os.path.exists(shared_memory_path):
        try:
            shared_content = _read_file_safe(shared_memory_path)
        except Exception as e:
            logger.error(f"[CORE] Erro ao ler dossiê de reputação: {e}")

    if shared_content:
        # Garante que o dossiê não exceda um limite seguro de context window
        safe_shared = shared_content[:25000] 
        return f"{persona}\n\n### CONTEXTO DA MARCA (MEMÓRIA COMPARTILHADA):\n{safe_shared}"

    return persona


def create_specialist_agent(tools, system_prompt: str, model_instance):
    safe_tools = [t for t in tools if t is not None]
    # Removed gemini_fallback to prevent 8-minute retry loops on 429 errors
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
    user_id = state.get("user_id", "")
    channel = state.get("channel", "")
    # PROTEÇÃO CONTRA ESTOURO DE CONTEXTO (Max 128k tokens)
    # Limita o histórico enviado para o agente para as últimas 30 mensagens
    # para evitar sobrecarregar os modelos (especialmente gemini-3-flash-preview e deepseek).
    if len(messages) > 30:
        # Mantém a SystemMessage (primeira msg) se existir, e pega as últimas 29
        if messages and getattr(messages[0], "type", "") == "system":
            messages = [messages[0]] + messages[-29:]
        else:
            messages = messages[-30:]
            
    result = await agent.ainvoke({**state, "messages": messages}, RunnableConfig(recursion_limit=50))
    msg = result["messages"][-1]

    # EXTRAÇÃO AGRESSIVA DE TEXTO (Blindagem contra formato Multimodal do Gemini 3.1)
    def extract_text(content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(extract_text(part) for part in content)
        if isinstance(content, dict):
            # Tenta pegar 'text' ou o primeiro valor string que encontrar
            return content.get("text", content.get("content", str(content)))
        return str(content)

    content_str = extract_text(msg.content)

    # Limpeza de possíveis artefatos de stringificação de lista/dict que restarem
    if content_str.startswith("[{'type': 'text'"):
        try:
            # Tenta extrair o texto de dentro da string que parece uma lista
            import ast
            parsed = ast.literal_eval(content_str)
            if isinstance(parsed, list) and len(parsed) > 0:
                content_str = parsed[0].get("text", content_str)
        except: pass

    tool_messages = [m for m in result["messages"] if getattr(m, "type", "") == "tool"]
    tool_text = " ".join(str(m.content) for m in tool_messages)
    file_tags = re.findall(r'<(?:SEND_FILE|SEND_AUDIO):([^>]+)>', tool_text)
    
    # SILENCIAMENTO INTELIGENTE (Estilo Manus AI)
    # Se houver um documento principal, não mostra imagens individuais (img-xxx)
    has_main_doc = any(f.lower().endswith(('.pptx', '.pdf', '.docx', '.xlsx')) for f in file_tags)
    
    # Injeta as tags na mensagem para o estado saber
    for tag in file_tags:
        # Se temos um doc principal, pula tags que começam com 'img-'
        if has_main_doc and tag.lower().startswith('img-'):
            continue
        t_str = f"<SEND_FILE:{tag}>"
        if t_str not in content_str: content_str += f"\n{t_str}"
        
    # FIX: Ensure the correct agent name is attached to the AIMessage 
    # so the supervisor can properly count it and break loops.
    msg = msg.model_copy(update={"content": content_str, "name": name})

    return {
        "messages": [msg],
        "sender": name,
        "content": state.get("content", ""),
        "user_input": state.get("user_input", "")
    }

async def researcher_node(state): 
    res = await agent_node(state, researcher_agent, "arth_researcher")
    if len(str(res["messages"][-1].content)) > 200:
        res["content"] = str(res["messages"][-1].content)
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

    # Trava de segurança contra loops infinitos (Max 3 execuções do executor por turno)
    if specialist_runs.get("arth_executor", 0) >= 3:
        return {"next_agent": "FINISH"}

    short_messages = messages[-15:]
    routing_result = await supervisor_chain.ainvoke({**state, "messages": short_messages})
    
    # Validação de Rota (Blindagem de Arquivos e Fluxo Manus AI)
    user_input = messages[last_human_idx].content.lower()
    needs_file = any(kw in user_input for kw in ["pdf", "docx", "pptx", "excel", "planilha", "imagem", "foto", "apresentação", "apresentacao"])
    
    # REGRA DE OURO: Se houve pesquisa e o usuário quer arquivo, FORÇA o executor
    has_research = specialist_runs.get("arth_researcher", 0) > 0
    if needs_file and not has_file:
        if has_research:
            logger.info("[SUPERVISOR] 🚀 Pesquisa concluída. Encaminhando OBRIGATORIAMENTE para o Executor.")
            return {"next_agent": "arth_executor"}
        elif specialist_runs.get("arth_executor", 0) == 0:
            return {"next_agent": "arth_executor"}

    if needs_file and routing_result.next_agent == "FINISH" and not has_file:
        return {"next_agent": "arth_executor"}

    ret = {"next_agent": routing_result.next_agent}
    
    # FIX: Se a jornada acabou e há uma resposta final (ex: saudação, conversa normal),
    # precisamos devolvê-la para o estado sob o nome do orchestrator.
    if routing_result.next_agent == "FINISH" and routing_result.final_answer:
        msg = AIMessage(content=routing_result.final_answer, name="arth_orchestrator")
        ret["messages"] = [msg]

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
