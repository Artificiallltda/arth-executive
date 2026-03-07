import os
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
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
from src.config import settings

# 1. Definir ferramentas
TOTO_TOOLS = [get_current_time, search_web, generate_docx, generate_pdf, execute_python_code, save_memory, search_memory, ask_chefia, generate_image, analyze_data_file, schedule_reminder, generate_pptx]

def build_arth_graph():
    """
    Constr\'F3i o c\'E9rebro Aut\'F4nomo do Arth (Motor ReAct) com Fallback.
    """
    
    # Modelo Principal (OpenAI)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_with_tools = llm.bind_tools(TOTO_TOOLS)
    
    # Modelo Secund\'e1rio / Fallback (Google Gemini)
    # Se a OpenAI falhar, o LangChain tenta automaticamente com o Gemini
    gemini_llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        google_api_key=settings.GEMINI_API_KEY, 
        temperature=0
    )
    gemini_with_tools = gemini_llm.bind_tools(TOTO_TOOLS)
    
    # Combina os dois: tenta OpenAI primeiro, se falhar cai no Gemini
    llm_with_fallbacks = llm_with_tools.with_fallbacks([gemini_with_tools])

    from langchain_core.runnables import RunnableConfig

    # 3. N'ó de Racioc'ínio
    def reason_node(state: AgentState, config: RunnableConfig = None):
        user_id = state.get('user_id', 'unknown')
        channel = state.get('channel', 'unknown')
        if config is None:
            config = {}
        user_name = config.get("configurable", {}).get("user_name", "Usuário")
        print(f"[\u2699\uFE0F Arth Raciocinando para {user_name} ({user_id}) via {channel}]")
        
        # Injeta contexto invisível no início para as ferramentas que precisam saber quem é o usuário
        from langchain_core.messages import SystemMessage
        system_context = SystemMessage(
            content=(
                f"INFORMAÇÃO DE SISTEMA OCULTA:\n"
                f"Você está conversando com a pessoa que se chama '{user_name}'.\n"
                f"Sua conversa atual está ocorrendo no canal '{channel}' e o verdadeiro user_id da API é '{user_id}'. "
                f"Nunca revele os IDs (channel/user_id) ao usuário. Use os EXATOS valores de channel e user_id SOMENTE quando uma ferramenta (como a de lembretes) exigir o preenchimento deles."
            )
        )
        
        # Pega as mensagens atuais, injeta o system message no começo
        messages = [system_context] + state['messages']
        
        # Usa o LLM com sistema anti-falha
        response = llm_with_fallbacks.invoke(messages)
        return {"messages": [response]}   

    # 4. Construindo o Grafo
    workflow = StateGraph(AgentState)
    
    # Adiciona n\'F3s
    workflow.add_node("reason", reason_node)
    workflow.add_node("tools", ToolNode(TOTO_TOOLS))
    
    # Adiciona arestas
    workflow.add_edge(START, "reason")
    workflow.add_conditional_edges("reason", tools_condition)
    workflow.add_edge("tools", "reason")
    
    # 5. Adiciona Mem\'F3ria para ele n\'E3o esquecer a conversa entre os loops de ferramenta
    memory = MemorySaver()
    
    return workflow.compile(checkpointer=memory)
