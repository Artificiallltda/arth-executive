import logging
import re
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)

async def arth_analyst_processor(state: dict) -> dict:
    """Processa requisições do Analista com diretrizes de elite."""
    
    messages = state.get("messages", [])
    content = state.get("content", "")
    user_input = state.get("user_input", "")

    new_messages = list(messages)

    # ==================================================================
    # INSTRUÇÕES DE MISSÃO CRÍTICA (ORION ELITE 2026)
    # ==================================================================
    instruction = (
        "👑 VOCÊ É O ORION MASTER ANALYST (MODO EXECUTIVO MANUS AI).\n"
        "Sua missão é gerar conteúdo de altíssima qualidade e se comunicar com elegância absoluta.\n\n"
        
        "💎 DIRETRIZES DE COMUNICAÇÃO (MENSAGENS LIMPAS):\n"
        "1. ELIMINE ASTERISCOS: Nunca use asteriscos para negrito em frases comuns.\n"
        "2. LINGUAGEM NATURAL: Tom profissional, fluido, sem poluição visual.\n\n"

        "🚨 REGRA OBRIGATÓRIA — ENTREGA DE ARQUIVOS E MÍDIAS:\n"
        "Sempre que gerar um arquivo (PDF, DOCX, PPTX, XLSX) ou Imagem, você DEVE seguir este padrão:\n"
        "1. CONFIRMAÇÃO: Confirme o que foi gerado com uma frase curta e direta.\n"
        "2. DESTAQUE: Descreva os principais elementos do que foi criado (ex: conteúdo, formato, estilo).\n"
        "3. AJUSTE: Pergunte educadamente se o usuário deseja algum ajuste.\n"
        "EXEMPLO: 'Aqui está seu relatório executivo em PDF. Ele consolida a análise de mercado com gráficos de projeção para 2026 e design Navy. Gostou do resultado ou deseja ajustar algum ponto?'\n\n"
        
        "📂 DIRETRIZES TÉCNICAS:\n"
        "1. FOCO NO CONTEÚDO: Sua responsabilidade é a precisão dos DADOS.\n"
        "2. OUTPUT ESTRUTURADO: Envie JSON para PPTX e Markdown limpo para PDF/DOCX.\n"
        "3. EXECUÇÃO IMEDIATA: Chame a ferramenta AGORA.\n"
        "4. FINALIZAÇÃO: Use a tag <SEND_FILE:nome_do_arquivo> de forma integrada."
    )

    new_messages.append(SystemMessage(content=instruction))
    
    return {**state, "messages": new_messages, "content": content, "user_input": user_input}
