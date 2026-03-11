import os
import re
import logging
import asyncio
from datetime import datetime
from typing import Literal, Optional, List, Any
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
    """
    Aguarda até que o arquivo exista no disco e tenha tamanho > 0.
    Retorna True se encontrou, False se timeout.
    """
    import os
    import asyncio
    import time
    
    start = time.time()
    while time.time() - start < max_wait:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            size = os.path.getsize(file_path)
            logger.info(f"[FileWait] ✅ Arquivo confirmado após {time.time()-start:.1f}s: {file_path} ({size} bytes)")
            return True
        
        await asyncio.sleep(check_interval)
    
    logger.error(f"[FileWait] ❌ Timeout após {max_wait}s aguardando: {file_path}")
    return False

# --- Setup dos Modelos Especializados (Arquitetura Híbrida Custo-Benefício) ---

# 🧠 ORQUESTRADOR / SUPERVISOR: GPT-4o para estabilidade de roteamento e análise de intenção
supervisor_llm = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=4000)

# 🧠 CÉREBRO E CONTEXTO PESADO: DeepSeek V3 (Uso de API direta via OpenAI compatibility layer)
# Destinado a: Researcher, Analyst e Planner (Geração de conteúdo rico e processamento pesado)
deepseek_llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=settings.DEEPSEEK_API_KEY,
    openai_api_base="https://api.deepseek.com",
    temperature=0.3,
    max_tokens=8000
)

# ⚡ EXECUÇÃO PRECISA E TOOL CALLING: GPT-4o-mini
# Destinado a: Executor (Precisão extrema em Schemas JSON e Structured Outputs)
executor_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# fallback de segurança (Google Gemini)
gemini_fallback = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY, 
    temperature=0
)

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
    get_current_time, search_web, read_url, read_document, generate_docx, generate_pdf, 
    execute_python_code, save_memory, search_memory, ask_chefia, 
    generate_image, analyze_data_file, schedule_reminder, 
    generate_pptx, audit_supabase_security, audit_database_schema, 
    generate_audio, query_knowledge_base, upload_document_to_knowledge_base,
    create_excel, append_to_excel, read_excel
]
# Blindagem contra ferramentas nulas (PARTE 2)
ALL_TOOLS = [t for t in ALL_TOOLS if t is not None]

# --- Criação dos Agentes Especialistas com LLMs Distintos ---
def create_specialist_agent(tools, system_prompt: str, model_instance):
    # Garante que tools é uma lista válida
    safe_tools = [t for t in tools if t is not None]
    if not safe_tools:
        logger.warning(f"Agente criado sem ferramentas válidas! Prompt: {system_prompt[:50]}")
    return create_react_agent(model=model_instance.with_fallbacks([gemini_fallback]), tools=safe_tools, prompt=system_prompt)

# 1. Pesquisador, Analista e Planejador -> DeepSeek V3 (Cérebro e Contexto)
researcher_agent = create_specialist_agent([search_web, read_url, read_document, search_memory, save_memory, query_knowledge_base], load_persona("researcher.md"), deepseek_llm)
planner_agent = create_specialist_agent([get_current_time, search_memory, save_memory, schedule_reminder], load_persona("planner.md"), deepseek_llm)
analyst_agent = create_specialist_agent([analyze_data_file, read_document, read_excel, audit_supabase_security, audit_database_schema, search_memory, save_memory], load_persona("analyst.md"), deepseek_llm)

# 2. Executor (File Generator) -> GPT-4o-mini (Estabilidade em Tool Calling/JSON)
# Agora assume TODA a geração de arquivos estruturados (Excel, PDF, PPTX, DOCX) + Mídias
executor_agent = create_specialist_agent([
    get_current_time, execute_python_code, save_memory, search_memory, 
    ask_chefia, generate_image, generate_audio, upload_document_to_knowledge_base,
    generate_docx, generate_pdf, generate_pptx, create_excel, append_to_excel
], load_persona("executor.md"), executor_llm)

# 3. QA usa o Supervisor (GPT-4o)
qa_agent = create_specialist_agent([search_memory, save_memory], load_persona("qa.md"), supervisor_llm)


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

    result = await agent.ainvoke({**state, "messages": messages}, RunnableConfig(recursion_limit=50))
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
    tool_messages = [m for m in inner_messages if getattr(m, "type", "") == "tool"]
    tool_text = " ".join(str(m.content) for m in tool_messages)
    # CORREÇÃO CRÍTICA: Adicionado parênteses para capturar apenas o nome do arquivo
    file_tags = re.findall(r'<(?:SEND_FILE|SEND_AUDIO):([^>]+)>', tool_text)
    
    # --- ENTREGA IMEDIATA (DICA DO USUÁRIO - CORREÇÃO DEFINITIVA) ---
    delivered_this_step = []
    if file_tags:
        from src.router.adapters.telegram import safe_send_file
        chat_id = state.get("user_id")
        already_delivered = state.get("delivered_files", []) or []
        output_dir = os.path.abspath(settings.DATA_OUTPUTS_PATH)
        
        for filename in file_tags:
            # Limpeza do filename (remove possíveis espaços ou tags residuais)
            filename = filename.strip().replace("<SEND_FILE:", "").replace(">", "")
            
            if filename in already_delivered: 
                logger.info(f"[{name}] Arquivo já enviado anteriormente: {filename}")
                continue
            
            full_path = os.path.join(output_dir, filename)
            logger.info(f"[{name}] 🚨 ARQUIVO DETECTADO NO RESULTADO: {filename}")
            
            # ESPERA ATÉ 5 SEGUNDOS PELO ARQUIVO (CORREÇÃO DEFINITIVA)
            if await wait_for_file(full_path, max_wait=5.0) and chat_id:
                logger.info(f"[{name}] 🚀 DISPARANDO ENTREGA IMEDIATA para {chat_id}")
                await safe_send_file(chat_id, full_path)
                delivered_this_step.append(filename)
            else:
                logger.warning(f"[{name}] ⚠️ Falha na entrega imediata: {filename} (Físico não encontrado ou ChatID vazio)")

    if file_tags:
        msg_content = str(msg.content) if not isinstance(msg.content, str) else msg.content
        missing = [t for t in file_tags if t not in msg_content]
        if missing:
            msg = msg.model_copy(update={"content": msg_content + "\n" + "\n".join(missing)})

    # --- BLINDAGEM DE MÍDIAS (08/03/2026) ---
    if isinstance(msg.content, str) and ".pptx>" in msg.content:
        msg_content = msg.content
        msg_content = re.sub(r'\n?<SEND_FILE:img[-_][^>]+>\n?', '', msg_content)
        if msg_content != msg.content:
            msg = msg.model_copy(update={"content": msg_content.strip()})
            logger.info(f"[{name}] Tags de imagem removidas devido ao PPTX.")

    # Remove tags inválidas
    if isinstance(msg.content, str) and "<SEND_FILE:" in msg.content:
        def _check_tag(m):
            tag_filename = m.group(1).strip()
            fp = os.path.join(settings.DATA_OUTPUTS_PATH, tag_filename)
            if os.path.exists(fp): return f"<SEND_FILE:{tag_filename}>"
            logger.warning(f"[{name}] Tag para arquivo inexistente removida: {tag_filename}")
            return ""
        cleaned = re.sub(r'<SEND_FILE:([^>]+)>', _check_tag, msg.content)
        if cleaned != msg.content: msg = msg.model_copy(update={"content": cleaned})

    # --- BLINDAGEM DE ESTADO DEFINITIVA (ORION + DICA DO USUÁRIO) ---
    new_content = str(result.get("content", state.get("content", "")))
    new_user_input = str(result.get("user_input", state.get("user_input", "")))
    all_delivered = list(state.get("delivered_files", []) or []) + delivered_this_step

    return {
        "messages": [msg],
        "sender": name,
        "content": new_content,
        "user_input": new_user_input,
        "delivered_files": all_delivered
    }

async def researcher_node(state): 
    # ==================================================================
    # REFORÇO NO RESEARCHER PARA PRESERVAR CONTEÚDO (DICA PARTE 1)
    # ==================================================================
    result = await agent_node(state, researcher_agent, "arth_researcher")
    
    # Se o pesquisador retornou dados no histórico, tenta extrair para a chave 'content'
    messages = result.get("messages", [])
    if messages:
        last_msg = messages[-1]
        if len(str(last_msg.content)) > 100:
             logger.info(f"[Researcher] 📦 Detectado conteúdo rico ({len(str(last_msg.content))} chars). Preservando no state.")
             result["content"] = str(last_msg.content)
             
    return result

async def planner_node(state): return await agent_node(state, planner_agent, "arth_planner")
async def executor_node(state): 
    new_messages = list(state.get("messages", []))
    new_messages.append(SystemMessage(content=(
        "🚨 INSTRUÇÃO DE SEGURANÇA: NUNCA crie (alucine) tags <SEND_FILE:> da sua cabeça. "
        "Você DEVE chamar as ferramentas (generate_image, generate_audio) ANTES de ditar a resposta final."
    )))
    return await agent_node({**state, "messages": new_messages}, executor_agent, "arth_executor")
async def qa_node(state): return await agent_node(state, qa_agent, "arth_qa")
async def analyst_node(state): 
    # ==================================================================
    # RECUPERAÇÃO DE CONTEÚDO (DICA PARTE 2)
    # ==================================================================
    # Injetamos o conteúdo da pesquisa explicitamente no estado se vier do researcher
    if state.get("sender") == "arth_researcher":
         research_content = state.get("content", "")
         if research_content:
             logger.info(f"[Supervisor] 📦 Passando conteúdo da pesquisa para Analyst: {len(research_content)} chars")
             state["content"] = research_content

    updated_state = await arth_analyst_processor(state)
    return await agent_node(updated_state, analyst_agent, "arth_analyst")

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

supervisor_chain = prompt | supervisor_llm.with_structured_output(RouteResponse)

# ANTES de qualquer decisão de roteamento
def validate_agent_choice(agent_name: str, state: dict) -> str:
    """Valida se o agente escolhido pode realmente fazer o que foi pedido."""
    messages = list(state.get("messages", []))
    last_human_idx = max((i for i, m in enumerate(messages) if m.type == "human"), default=0)
    user_input = messages[last_human_idx].content.lower() if messages else ""
    
    # Detecta intenções
    search_keywords = ["pesquise", "busque", "google", "internet", "saiba sobre", "procure", "encontre", "analise", "veja sobre", "informações sobre"]
    needs_search = any(kw in user_input for kw in search_keywords)
    
    # Detecta tipo de arquivo solicitado
    file_types = []
    if any(kw in user_input for kw in ["pdf", "documento"]):
        file_types.append("pdf")
    if any(kw in user_input for kw in ["docx", "word"]):
        file_types.append("docx")
    if any(kw in user_input for kw in ["pptx", "ppt", "apresentação", "slide"]):
        file_types.append("pptx")
    if any(kw in user_input for kw in ["excel", "planilha", "xlsx"]):
        file_types.append("excel")
    
    # ESTRATÉGIA ORION: Se precisa de pesquisa e o agente escolhido é o researcher,
    # NÃO redirecione ainda, mesmo que o usuário tenha pedido um arquivo.
    # A pesquisa deve vir primeiro.
    if needs_search and agent_name == "arth_researcher":
        logger.info("[Supervisor] Permitindo arth_researcher para fase de coleta de dados.")
        return agent_name

    if not file_types or agent_name == "FINISH":
        return agent_name
    
    # Para cada tipo, verifica se o agente pode gerar
    for ft in file_types:
        if not can_agent_generate(agent_name, ft):
            correct_agent = get_agent_for_file_type(ft)
            logger.warning(
                f"[Supervisor] {agent_name} NÃO pode gerar {ft.upper()}. "
                f"Redirecionando estruturalmente para {correct_agent}"
            )
            return correct_agent
    
    return agent_name

async def supervisor_node(state: AgentState):
    # ==================================================================
    # RASTREAMENTO DE ESTADO (PARTE 3)
    # ==================================================================
    logger.info(f"[GRAPH] State antes do roteamento: { {k: type(v).__name__ for k, v in state.items()} }")
    if state is None:
        logger.error("[GRAPH] State é None! Corrigindo para dict vazio.")
        state = {}

    messages = list(state.get("messages", []))

    # Índice do último HumanMessage = início do turno atual
    last_human_idx = max((i for i, m in enumerate(messages) if m.type == "human"), default=0)
    msgs_this_turn = messages[last_human_idx + 1:]

    # Conta execuções por especialista neste turno — previne loop infinito.
    specialist_runs: dict = {}
    for m in msgs_this_turn:
        if m.type == "ai" and getattr(m, "name", "") in members:
            specialist_runs[m.name] = specialist_runs.get(m.name, 0) + 1
            if any(tag in str(m.content) for tag in ["<SEND_FILE:", "<SEND_AUDIO:"]):
                logger.info(f"[Supervisor] Arquivo já gerado por {m.name}, encerrando rodada.")
                return {"next_agent": "FINISH"}

    # Se qualquer especialista já rodou 2+ vezes sem entregar arquivo → força FINISH
    if any(count >= 2 for count in specialist_runs.values()):
        repeat_info = {k: v for k, v in specialist_runs.items() if v >= 2}
        logger.warning(f"[Supervisor] Loop detectado {repeat_info}. Forçando FINISH.")
        return {"next_agent": "FINISH"}

    # --- TRUNFAMENTO DE CONTEXTO (PREVENÇÃO DE ERRO 429 TPM) ---
    # O Supervisor não precisa ler 500k tokens de histórico para decidir a rota.
    # Enviamos apenas as últimas 15 mensagens para manter a agilidade e economia.
    short_messages = messages[-15:] if len(messages) > 15 else messages
    
    # Prepara um estado reduzido para o supervisor_chain
    minimal_state = {**state, "messages": short_messages}

    routing_result = await supervisor_chain.ainvoke(minimal_state)
    logger.info(f"[ROUTER] Decisão LLM: {routing_result.next_agent}")
    
    # Estrutural: Valida se a rota faz sentido para a capacidade
    validated_agent = validate_agent_choice(routing_result.next_agent, state)
    if validated_agent != routing_result.next_agent:
        routing_result.next_agent = validated_agent

    # ==================================================================
    # PROTEÇÃO E PASSAGEM DE ESTADO (PARTE 2 - REFORÇO DICA)
    # ==================================================================
    if routing_result.next_agent == "arth_analyst":
        logger.info(f"[Graph] Preparando para chamar arth_analyst")
        
        # Recupera conteúdo rico de pesquisa se houver
        research_content = state.get("content", "")
        if not research_content and len(messages) > 1:
            # Tenta pegar da última mensagem de IA se o 'content' explícito estiver vazio
            last_ai = next((m for m in reversed(messages) if m.type == "ai"), None)
            if last_ai:
                research_content = str(last_ai.content)
                logger.info(f"[Supervisor] 📦 Recuperando conteúdo da última mensagem AI para o Analyst: {len(research_content)} chars")

        # Garante que content existe no estado para evitar erro Pydantic de None
        state["content"] = research_content or ""
        
        # Garante que user_input existe
        if "user_input" not in state or state.get("user_input") is None:
            state["user_input"] = ""
            
        logger.info(f"[Graph] State blindado para Analyst: content={len(str(state.get('content','')))}, user_input='{state.get('user_input','')[:50]}'")

    # --- FORÇAR EXECUTOR SE ARQUIVO AINDA NÃO FOI GERADO (BLINDAGEM CONTRA FINISH PREMATURO) ---
    if routing_result.next_agent == "FINISH" and msgs_this_turn:
        # Pega a requisição original do ser humano neste turno
        human_req = messages[last_human_idx].content.lower()
        needs_file = any(kw in human_req for kw in ["pptx", "apresentação", "slide", "pdf", "docx", "excel", "planilha"])
        needs_img = any(kw in human_req for kw in ["imagem", "foto", "desenhe", "áudio"])
        
        # Verifica se o analista/executor já obteve sucesso (gerou alguma tag SEND_FILE) neste turno
        has_file = False
        generated_file_path = ""
        for m in msgs_this_turn:
            if getattr(m, "name", "") in members:
                content_str = str(m.content)
                if "<SEND_FILE:" in content_str or "<SEND_AUDIO:" in content_str:
                    has_file = True
                    match = re.search(r'<SEND_FILE:([^>]+)>', content_str)
                    if match:
                        generated_file_path = match.group(1)
        
        # Se o usuário pediu documento e AINDA não tem arquivo, DEVE ir pro Analyst
        if needs_file and not has_file and specialist_runs.get("arth_analyst", 0) < 1:
            logger.warning("[Supervisor] Override: LLM tentou FINISH mas usuário pediu documento/pptx. Forçando arth_analyst.")
            routing_result.next_agent = "arth_analyst"
        # Se pediu imagem/áudio e não tem arquivo, vai pro Executor
        elif needs_img and not has_file and specialist_runs.get("arth_executor", 0) < 1:
            logger.warning("[Supervisor] Override: LLM tentou FINISH mas usuário pediu mídia. Forçando arth_executor.")
            routing_result.next_agent = "arth_executor"
            
        # ANTES DE FINISH, VERIFICA ARQUIVO FÍSICO (BLINDAGEM ESTRUTURAL 09/03/2026)
        if routing_result.next_agent == "FINISH" and (needs_file or needs_img) and generated_file_path:
            expected_full_path = os.path.join(settings.DATA_OUTPUTS_PATH, generated_file_path)
            
            if not os.path.exists(expected_full_path):
                logger.error(f"[Supervisor] Arquivo FANTASMA! Tag gerada, mas o arquivo {expected_full_path} NÃO EXISTE Fisicamente!")
                file_ext = os.path.splitext(generated_file_path)[1].replace(".", "")
                correct_retry_agent = get_agent_for_file_type(file_ext)
                return {"next_agent": correct_retry_agent} # Retenta no agente correto
                
            if os.path.getsize(expected_full_path) == 0:
                logger.error(f"[Supervisor] Arquivo VAZIO (0 bytes): {expected_full_path}!")
                file_ext = os.path.splitext(generated_file_path)[1].replace(".", "")
                correct_retry_agent = get_agent_for_file_type(file_ext)
                return {"next_agent": correct_retry_agent}

    # --- SUPORTE A ENTREGA PROATIVA BLINDADA (ESCANER TOTAL DE TURNO) ---
    if routing_result.next_agent == "FINISH":
        from src.router.adapters.telegram import safe_send_file
        chat_id = state.get("user_id")
        
        # Escaneia todas as mensagens desde o último input humano (turno atual)
        all_tags = []
        for m in msgs_this_turn:
            content_str = str(m.content)
            tags = re.findall(r'<(?:SEND_FILE|SEND_AUDIO):([^>]+)>', content_str)
            all_tags.extend(tags)
        
        # Remove duplicatas preservando a ordem
        unique_tags = list(dict.fromkeys(all_tags))
        
        if unique_tags and chat_id:
            logger.info(f"[Supervisor] 📦 DETECTADOS {len(unique_tags)} ARQUIVOS PARA ENTREGA NESTE TURNO.")
            output_dir = os.path.abspath(settings.DATA_OUTPUTS_PATH)
            
            for filename in unique_tags:
                filename = filename.strip()
                full_path = os.path.join(output_dir, filename)
                
                # ESPERA ATÉ 5 SEGUNDOS PELO ARQUIVO (REDUNDÂNCIA)
                if await wait_for_file(full_path, max_wait=5.0):
                    logger.info(f"[Supervisor] 🚀 Disparando entrega de: {filename}")
                    await safe_send_file(full_path, chat_id)
                else:
                    logger.error(f"[Supervisor] ❌ Arquivo não apareceu no disco após espera: {full_path}")

        # Lógica de finalização original...
        last_human_idx = max((i for i, m in enumerate(messages) if m.type == "human"), default=0)
        msgs_this_turn = messages[last_human_idx + 1:]
        last_specialist_msg = next((m for m in reversed(msgs_this_turn) if m.type == "ai" and m.name in members), None)
        if last_specialist_msg:
            return {"next_agent": "FINISH"}
        return {"next_agent": "FINISH", "messages": [AIMessage(content=routing_result.final_answer or "Tarefa concluída.", name="arth_orchestrator")]}

    # Correção do Handoff React Agent:
    # Se o último step foi um agente (AIMessage), o próximo agente React 
    # assumirá que a mensagem final já foi gerada e retornará imediatamente.
    # Precisamos injetar uma HumanMessage instrucionando-o a prosseguir.
    if messages and getattr(messages[-1], "type", "") == "ai":
        prev_agent = getattr(messages[-1], "name", "outro agente")
        handoff_msg = HumanMessage(
            content=(
                f"O Orquestrador alocou a tarefa para você ({routing_result.next_agent}). "
                f"O agente '{prev_agent}' forneceu as informações acima. "
                f"Use esses dados para cumprir o pedido original do usuário agora."
            ),
            name="arth_orchestrator"
        )
        return {"next_agent": routing_result.next_agent, "messages": [handoff_msg]}

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
