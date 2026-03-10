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
from src.config import settings

logger = logging.getLogger(__name__)

# --- Setup dos Modelos ---
openai_llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0)
gemini_llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY, 
    temperature=0
)

# Gemini como Primário, OpenAI como Fallback
llm_with_fallbacks = gemini_llm.with_fallbacks([openai_llm])

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

# --- Criação dos Agentes Especialistas ---
# NOVO: Reduzimos a carga cognitiva dividindo as ferramentas
def create_specialist_agent(tools, system_prompt: str):
    return create_react_agent(model=llm_with_fallbacks, tools=tools, prompt=system_prompt)

researcher_agent = create_specialist_agent([search_web, read_url, read_document, search_memory, save_memory, query_knowledge_base], load_persona("researcher.md"))
planner_agent = create_specialist_agent([get_current_time, search_memory, save_memory, schedule_reminder], load_persona("planner.md"))
executor_agent = create_specialist_agent([get_current_time, execute_python_code, save_memory, search_memory, ask_chefia, generate_image, generate_audio, upload_document_to_knowledge_base], load_persona("executor.md")) # Apenas Mídias e Scripts
qa_agent = create_specialist_agent([search_memory, save_memory], load_persona("qa.md"))
analyst_agent = create_specialist_agent([analyze_data_file, read_document, create_excel, append_to_excel, read_excel, generate_pdf, generate_docx, generate_pptx, audit_supabase_security, audit_database_schema, search_memory, save_memory], load_persona("analyst.md")) # Documentos e Excel

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

    # --- BLINDAGEM DE MÍDIAS (08/03/2026) ---
    # Se houver um PPTX na resposta, removemos tags de imagem individuais (img- ou img_)
    # para evitar poluição no chat, já que as imagens já estão dentro dos slides.
    if isinstance(msg.content, str) and ".pptx>" in msg.content:
        msg_content = msg.content
        # Regex flexível para img- ou img_ com qualquer extensão comum
        msg_content = re.sub(r'\n?<SEND_FILE:img[-_][^>]+>\n?', '', msg_content)
        if msg_content != msg.content:
            msg = msg.model_copy(update={"content": msg_content.strip()})
            logger.info(f"[{name}] Tags de imagem redundantes removidas agressivamente devido ao PPTX.")

    # Remove SEND_FILE tags que apontam para arquivos inexistentes (previne alucinação de filenames).
    if isinstance(msg.content, str) and "<SEND_FILE:" in msg.content:
        def _check_tag(m):
            tag_filename = m.group(1).strip()
            # Tenta o nome original, e também variações de hífen/underscore
            variants = [
                tag_filename,
                tag_filename.replace("-", "_"),
                tag_filename.replace("_", "-")
            ]
            
            for v in variants:
                fp = os.path.join(settings.DATA_OUTPUTS_PATH, v)
                if os.path.exists(fp):
                    # Se encontrou com uma variante, retorna a tag com o nome real do arquivo
                    return f"<SEND_FILE:{v}>"
            
            logger.warning(f"[{name}] SEND_FILE para arquivo inexistente removido: {tag_filename}")
            return ""
            
        cleaned = re.sub(r'<SEND_FILE:([^>]+)>', _check_tag, msg.content)
        if cleaned != msg.content:
            msg = msg.model_copy(update={"content": cleaned})

    msg.name = name
    return {
        "messages": [msg],
        "sender": name
    }

async def researcher_node(state): return await agent_node(state, researcher_agent, "arth_researcher")
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
    new_messages = list(state.get("messages", []))
    new_messages.append(SystemMessage(content=(
        "🚨 INSTRUÇÃO DE DOCUMENTAÇÃO (CRÍTICO): Se houver conteúdo de pesquisa feito pelo arth_researcher no histórico recente, "
        "você DEVE ler esse conteúdo e injetá-lo na íntegra DENTRO do argumento 'content' ao chamar as ferramentas de geração (PDF/DOCX/PPTX).\n"
        "Exemplo de formatação para o 'content':\n"
        "RELATÓRIO DE PESQUISA\n=====================\n[Cole o texto da pesquisa aqui]\n--- Fim do relatório ---\n\n"
        "🚨 INSTRUÇÃO DE SEGURANÇA: NUNCA crie (alucine) tags <SEND_FILE:> da sua cabeça. "
        "Você DEVE chamar as ferramentas (generate_pdf, generate_docx, generate_pptx, create_excel) AGORA ANTES de ditar a resposta final."
    )))
    return await agent_node({**state, "messages": new_messages}, analyst_agent, "arth_analyst")

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

# ANTES de qualquer decisão de roteamento
def validate_agent_choice(agent_name: str, state: dict) -> str:
    """Valida se o agente escolhido pode realmente fazer o que foi pedido."""
    messages = list(state.get("messages", []))
    last_human_idx = max((i for i, m in enumerate(messages) if m.type == "human"), default=0)
    user_input = messages[last_human_idx].content.lower() if messages else ""
    
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
    if any(kw in user_input for kw in ["imagem", "foto", "desenhe"]):
        file_types.append("image")
    
    if not file_types or agent_name == "FINISH":
        return agent_name  # sem arquivo ou terminando, pode seguir
    
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

    routing_result = await supervisor_chain.ainvoke(state)
    logger.info(f"[ROUTER] Decisão LLM: {routing_result.next_agent}")
    
    # Estrutural: Valida se a rota faz sentido para a capacidade
    validated_agent = validate_agent_choice(routing_result.next_agent, state)
    if validated_agent != routing_result.next_agent:
        routing_result.next_agent = validated_agent

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

    if routing_result.next_agent == "FINISH":
        messages = list(state.get("messages", []))
        last_human_idx = max((i for i, m in enumerate(messages) if m.type == "human"), default=0)
        msgs_this_turn = messages[last_human_idx + 1:]
        
        last_specialist_msg = next((m for m in reversed(msgs_this_turn) if m.type == "ai" and m.name in members), None)

        if last_specialist_msg:
            # Preserva a resposta rica do especialista (com ou sem arquivo, se ele falou algo útil)
            logger.info(f"[Supervisor] Finalizando. Preservando resposta de {last_specialist_msg.name}")
            return {"next_agent": "FINISH"}

        return {
            "next_agent": "FINISH",
            "messages": [AIMessage(content=routing_result.final_answer or "Tarefa concluída.", name="arth_orchestrator")]
        }

    # Correção do Handoff React Agent:
    # Se o último step foi um agente (AIMessage), o próximo agente React 
    # assumirá que a mensagem final já foi gerada e retornará imediatamente.
    # Precisamos injetar uma HumanMessage instrucionando-o a prosseguir.
    if messages and getattr(messages[-1], "type", "") == "ai":
        handoff_msg = HumanMessage(
            content=f"O Orquestrador alocou a tarefa para você ({routing_result.next_agent}). Analise o contexto acima e execute o que for necessário para atender o usuário.",
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
