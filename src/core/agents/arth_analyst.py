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
    logger.info(f"[Analyst] Conteúdo recebido: {len(content)} caracteres")
    
    # ==================================================================
    # CONTINUA COM O CÓDIGO NORMAL DO ANALISTA (GERADORES)
    # ==================================================================
    # Injetamos as instruções de documentação no estado
    new_messages = list(state.get("messages", []))
    new_messages.append(SystemMessage(content=(
        "🚨 INSTRUÇÃO DE DOCUMENTAÇÃO (CRÍTICO): Se houver conteúdo de pesquisa feito pelo arth_researcher no histórico recente, "
        "você DEVE ler esse conteúdo e injetá-lo na íntegra DENTRO do argumento 'content' ao chamar as ferramentas de geração (PDF/DOCX/PPTX).\n"
        "Exemplo de formatação para o 'content':\n"
        "RELATÓRIO DE PESQUISA\n=====================\n[Cole o texto da pesquisa aqui]\n--- Fim do relatório ---\n\n"
        "🚨 INSTRUÇÃO DE SEGURANÇA: NUNCA crie (alucine) tags <SEND_FILE:> da sua cabeça. "
        "Você DEVE chamar as ferramentas (generate_pdf, generate_docx, generate_pptx, create_excel) AGORA ANTES de ditar a resposta final.\n\n"
        "📊 REGRA PARA EXCEL: Ao gerar Excel, finalize sua RESPOSTA de texto com a tag <SEND_FILE:nome.xlsx> e garanta que os dados sejam reais e estruturados. "
        "Se você estiver retornando um objeto estruturado, inclua 'force_delivery': True."
    )))
    
    # Atualizamos o estado para ser retornado ou passado para o executor
    return {**state, "messages": new_messages, "content": content, "user_input": user_input}
