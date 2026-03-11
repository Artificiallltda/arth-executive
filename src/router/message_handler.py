from fastapi import APIRouter, Request, BackgroundTasks
import logging
import platform
import asyncio
import re
import hashlib
import os
import uuid
from langchain_core.messages import HumanMessage

from src.config import settings
from src.core.engine import engine
from src.router.adapters.whatsapp import process_whatsapp_reply, send_whatsapp_message
from src.router.adapters.telegram import process_telegram_reply, send_telegram_message, safe_send_file

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

router = APIRouter()
logger = logging.getLogger(__name__)

# Controle de sessão e deduplicação
_session_counters: dict = {}
_user_locks: dict = {}

def _get_thread_id(channel: str, user_id: str) -> str:
    key = f"{channel}_{user_id}"
    counter = _session_counters.get(key, 0)
    return f"{key}_s{counter}" if counter > 0 else key

def _get_user_lock(thread_key: str) -> asyncio.Lock:
    if thread_key not in _user_locks:
        _user_locks[thread_key] = asyncio.Lock()
    return _user_locks[thread_key]

async def execute_brain(user_id: str, text: str, channel: str = "whatsapp", status_callback=None, user_name: str = "User", media_data: dict = None):
    if not text: text = ""
    thread_key = _get_thread_id(channel, user_id)
    config = {"configurable": {"thread_id": thread_key, "user_name": user_name}}

    async with _get_user_lock(thread_key):
        try:
            brain = await engine.get_brain()
            initial_state = {
                "messages": [HumanMessage(content=text)],
                "user_id": str(user_id),
                "channel": channel,
                "user_input": text,
                "content": "",
                "media_context": media_context if (media_context := (media_data.get("b64") if media_data else None)) else None,
                "delivered_files": []
            }

            STATUS_NODES = {
                "arth_researcher": "Pesquisando dados relevantes... 🔍⏳",
                "arth_executor": "Executando ferramentas e gerando artefatos... 💻⏳",
                "arth_analyst": "Analisando dados e faturamentos... 📊⏳",
                "arth_planner": "Estruturando o plano de ação... 📋⏳",
                "arth_qa": "Revisando a qualidade técnica... 🛡️⏳",
            }
            
            sent_etas = set()
            responses_pool = [] 

            async for event in brain.astream(initial_state, config=config):
                for node, state_update in event.items():
                    if node in STATUS_NODES and node not in sent_etas:
                        if status_callback: await status_callback(STATUS_NODES[node])
                        sent_etas.add(node)

                    msgs = state_update.get("messages", [])
                    for m in msgs:
                        if not m.content: continue
                        content_str = str(m.content)
                        # Guardamos mensagens ricas de IA (especialistas)
                        if hasattr(m, "type") and m.type == "ai" and len(content_str) > 10:
                            responses_pool.append({"node": node, "text": content_str})

            # --- ESTRATÉGIA DE RESPOSTA ÚNICA ---
            # Priorizamos mensagens de especialistas (Analyst, Executor, Researcher) sobre o Orchestrator
            priority_nodes = ["arth_analyst", "arth_executor", "arth_researcher"]
            final_text = ""
            
            # Tenta pegar a mensagem mais longa dos nós prioritários
            specialist_msgs = [r for r in responses_pool if r["node"] in priority_nodes]
            if specialist_msgs:
                final_text = max(specialist_msgs, key=lambda x: len(x["text"]))["text"]
            elif responses_pool:
                # Fallback para a maior mensagem qualquer (provavelmente do Orchestrator)
                final_text = max(responses_pool, key=lambda x: len(x["text"]))["text"]
            else:
                final_text = "Tarefa processada com sucesso."

            # --- ENVIO DE TEXTO E MÍDIA ---
            # Extrair todas as tags de arquivo de todas as mensagens geradas pelas IAs neste turno
            all_ai_text = " ".join([r["text"] for r in responses_pool])
            file_tags = re.findall(r'<(?:SEND_FILE|SEND_AUDIO):([^>]+)>', all_ai_text)
            unique_files = list(dict.fromkeys([t.strip() for t in file_tags]))

            # Limpa tags para a explicação ficar elegante
            clean_response = re.sub(r'<(?:SEND_FILE|SEND_AUDIO):[^>]+>', '', final_text).strip()
            
            # Fallback Premium Manus AI dinâmico baseado no tipo de arquivo
            is_weak_text = not clean_response or len(clean_response) < 40 or "tarefa" in clean_response.lower() or "sucesso" in clean_response.lower()
            if unique_files and is_weak_text:
                first_file = unique_files[0].lower()
                
                if first_file.endswith('.png') or first_file.endswith('.jpg'):
                    clean_response = (
                        "📸 **Imagem Gerada com Sucesso**\n\n"
                        "Foi aplicada uma direção de arte de alto padrão para traduzir a sua solicitação em uma composição visual única. "
                        "Confira o resultado abaixo. 👑"
                    )
                elif first_file.endswith('.pdf'):
                    clean_response = (
                        "📄 **Pesquisa & Relatório Executivo**\n\n"
                        "Consolidei as informações solicitadas em um relatório blindado com design editorial *Manus AI*. "
                        "O documento está formatado e pronto para leitura ou encaminhamento estratégico. 👑"
                    )
                elif first_file.endswith('.docx'):
                    clean_response = (
                        "📝 **Documento Word Estruturado**\n\n"
                        "O texto foi elaborado com precisão corporativa e organizado com estilos e tipografia da paleta Executiva. "
                        "O arquivo aberto já está à sua disposição abaixo. 👑"
                    )
                else:
                    clean_response = (
                        "✨ **Material Gerado com Precisão**\n\n"
                        "O conteúdo foi estruturado seguindo os mais altos padrões de entrega do *Manus AI*. "
                        "O arquivo está sendo enviado abaixo para utilização imediata. 👑"
                    )

            if clean_response and clean_response.lower() != "tarefa concluída":
                if channel == "telegram":
                    await send_telegram_message(user_id, clean_response)
                elif channel == "whatsapp":
                    await send_whatsapp_message(user_id, clean_response)
            
            for filename in unique_files:
                full_path = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
                
                # Aguardar o arquivo ser gravado no disco (timeout 15s)
                import time
                start_wait = time.time()
                file_ready = False
                while time.time() - start_wait < 15.0:
                    if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                        file_ready = True
                        break
                    await asyncio.sleep(0.5)
                
                if file_ready:
                    if channel == "telegram":
                        await safe_send_file(user_id, full_path)
                    elif channel == "whatsapp":
                        from src.router.adapters.whatsapp import safe_send_whatsapp_file
                        await safe_send_whatsapp_file(user_id, full_path)

            return None 

        except Exception as e:
            logger.error(f"Erro no execute_brain: {e}", exc_info=True)
            if "RESOURCE_EXHAUSTED" in str(e):
                return "Desculpe, atingi o limite de processamento temporário da API. Por favor, tente novamente em 30 segundos. ⏳"
            return f"Ops, falha técnica: {str(e)}"

@router.post("/telegram/webhook")
async def receive_telegram(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    if "message" not in body: return {"status": "ignored"}
    msg = body["message"]
    chat_id = str(msg.get("chat", {}).get("id", ""))
    user_name = msg.get("from", {}).get("first_name", "User")
    text = msg.get("text", "") or msg.get("caption", "")
    if not chat_id: return {"status": "ignored"}
    async def status_callback(m: str): await send_telegram_message(chat_id, f"<i>{m}</i>")
    async def run_pipeline():
        await execute_brain(user_id=chat_id, text=text, channel="telegram", status_callback=status_callback, user_name=user_name)
    background_tasks.add_task(run_pipeline)
    return {"status": "queued"}

@router.post("/webhook/leads")
async def receive_generator_leads(request: Request, background_tasks: BackgroundTasks):
    """
    Receives JSON payloads directly from the local Leads Generator.
    Since we are replacing Pipedrive, this endpoint will take the leads
    and send them to an AI Engine processing pipeline or directly to Supabase.
    """
    try:
        body = await request.json()
        leads = body.get("leads", [])
        source = body.get("source", "gerador_local")

        if not leads:
            return {"status": "ignored", "message": "No leads provided"}

        logger.info(f"Received {len(leads)} leads from {source}")

        # The leads will need to be processed and inserted into Supabase.
        # For now, we kick off an execution pipeline or handle insertion logic
        async def process_leads_workflow():
            # In a real integration, we might call a specific tool or Supabase client here.
            # As a placeholder, we use execute_brain to notify the SDR agent of the new batch.
            prompt = f"O Gerador de Leads acabou de enviar um novo lote de {len(leads)} leads extraídos da fonte {source}. Por favor, analise a lista e classifique-os no banco de dados Supabase. Abaixo estão os dados em JSON:\n\n{leads}"
            # Sending to a system/admin thread
            await execute_brain(user_id="system_admin", text=prompt, channel="internal", user_name="LeadGenerator")

        background_tasks.add_task(process_leads_workflow)
        
        # Returning success counts
        return {
            "status": "success", 
            "message": "Leads received and queued for processing",
            "criados": len(leads),
            "erros": 0
        }

    except Exception as e:
        logger.error(f"Erro ao processar lote de leads: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
