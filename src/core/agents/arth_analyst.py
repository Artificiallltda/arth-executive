import logging
import re
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)

async def arth_analyst_processor(state: dict) -> dict:
    """Processa requisições do Analista com proteção contra None."""
    
    # ==================================================================
    # PROTEÇÃO CONTRA None (IMPEDE ERRO DE VALIDAÇÃO) (PARTE 3)
    # ==================================================================
    if state is None:
        logger.error("[Analyst] ❌ State é None! Criando vazio.")
        state = {}
    
    # Extrai e valida campos
    user_input = state.get("user_input", "")
    if user_input is None:
        user_input = ""
    
    content = state.get("content", "")
    if content is None:
        content = ""
    
    last_agent = state.get("last_agent", "")
    if last_agent is None:
        last_agent = ""
    
    # Garante que são strings
    user_input = str(user_input) if user_input is not None else ""
    content = str(content) if content is not None else ""
    last_agent = str(last_agent) if last_agent is not None else ""
    
    logger.info(f"[Analyst] Processando: '{user_input[:50]}...'")
    logger.info(f"[Analyst] Último agente: {last_agent}")
    
    # Extrai mensagens e detecta pesquisa
    new_messages = list(state.get("messages", []))
    has_research = any("pesquisa" in str(m.content).lower() or "resultado" in str(m.content).lower() for m in new_messages[-5:])
    
    # Prioriza content do estado (pesquisa/geração anterior)
    rich_content = str(content) if content else ""
    if not rich_content:
        # Se o content explícito estiver vazio, tenta inferir das mensagens
        last_ai_msg = next((m for m in reversed(new_messages) if m.type == "ai"), None)
        if last_ai_msg and len(str(last_ai_msg.content)) > 100:
            rich_content = str(last_ai_msg.content)
            logger.info(f"[Analyst] 📥 Recuperado conteúdo rico das mensagens: {len(rich_content)} chars")
        else:
            # NOVO: Se ainda não tem conteúdo, usa o input do usuário para redigir do zero
            rich_content = f"Documento redigido baseado no pedido: {user_input}"
            logger.warning(f"[Analyst] ⚠️ Sem pesquisa disponível. Redigindo do zero baseado no input.")

    logger.info(f"[Analyst] Conteúdo final para processamento: {len(rich_content)} caracteres")
    
    # ==================================================================
    # INSTRUÇÕES DE MISSÃO CRÍTICA (REFORÇO ORION 2.0)
    # ==================================================================
    instruction = (
        "🚨 MISSÃO CRÍTICA: Você é um Especialista em Geração de Documentos Executivos.\n"
        "1. VOCÊ DEVE GERAR O ARQUIVO AGORA. Não peça permissão, não faça perguntas.\n"
        "2. SE NÃO HOUVER PESQUISA, use seu próprio conhecimento para REDIGIR UM DOCUMENTO COMPLETO E PROFISSIONAL (ex: um contrato real, uma planilha de gastos reais, etc.).\n"
        "3. CHAME AS FERRAMENTAS: generate_pdf, generate_docx, generate_pptx ou create_excel IMEDIATAMENTE.\n"
        "4. O argumento 'content' da ferramenta deve conter o TEXTO COMPLETO do documento.\n"
        "5. Após a ferramenta confirmar o sucesso, finalize sua resposta citando a tag <SEND_FILE:nome_do_arquivo>."
    )
    
    if rich_content:
        instruction += f"\n\n--- CONTEÚDO PARA O DOCUMENTO ---\n{rich_content[:2000]}\n--- FIM DO CONTEÚDO ---"
    
    if has_research:
        instruction += "\n\n💡 DETECTEI DADOS DE PESQUISA RECENTES. Incorpore-os integralmente no documento."

    new_messages.append(SystemMessage(content=instruction))
    
    return {**state, "messages": new_messages, "content": content, "user_input": user_input}
