from fastapi import APIRouter, Request, BackgroundTasks, Query
import logging
import platform
import asyncio
import re
import hashlib
import os
import uuid
import base64
from langchain_core.messages import HumanMessage

from src.config import settings
from src.core.engine import engine
from src.router.adapters.whatsapp import process_whatsapp_reply, send_whatsapp_message
from src.router.adapters.telegram import process_telegram_reply, send_telegram_message, safe_send_file
from src.router.adapters.instagram import process_instagram_reply, send_instagram_message
from src.utils.audio_transcriber import transcribe_audio_file

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

router = APIRouter()
logger = logging.getLogger(__name__)

# Controle de sessão e deduplicação
_session_counters: dict = {}
_user_locks: dict = {}
_last_messages: dict = {} 
_RESET_KEYWORDS = {"resetar", "reset", "/reset", "limpar histórico", "nova conversa"}

def _get_thread_id(channel: str, user_id: str) -> str:
    key = f"{channel}_{user_id}"
    counter = _session_counters.get(key, 0)
    return f"{key}_s{counter}" if counter > 0 else key

def _get_user_lock(thread_key: str) -> asyncio.Lock:
    if thread_key not in _user_locks:
        _user_locks[thread_key] = asyncio.Lock()
    return _user_locks[thread_key]

def _is_duplicate(user_id: str, text: str) -> bool:
    msg_hash = hashlib.md5(text.encode()).hexdigest()
    if _last_messages.get(user_id) == msg_hash: return True
    _last_messages[user_id] = msg_hash
    return False

async def execute_brain(user_id: str, text: str, channel: str = "whatsapp", status_callback=None, user_name: str = "User", media_data: dict = None):
    if text is None: text = ""
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
                "media_context": media_data.get("b64") if media_data else None,
            }

            STATUS_NODES = {
                "arth_researcher": "Pesquisando dados relevantes... 🔍⏳",
                "arth_executor": "Executando ferramentas e gerando artefatos... 💻⏳",
                "arth_analyst": "Analisando dados e faturamentos... 📊⏳",
                "arth_planner": "Estruturando o plano de ação... 📋⏳",
                "arth_qa": "Revisando a qualidade técnica... 🛡️⏳",
            }
            
            sent_etas = set()
            collected_tags = []
            final_text = "Tarefa concluída com sucesso."

            async for event in brain.astream(initial_state, config=config):
                for node, state_update in event.items():
                    # ⏳ Dispara ETA imediatamente ao entrar no nó
                    if node in STATUS_NODES and node not in sent_etas:
                        if status_callback: await status_callback(STATUS_NODES[node])
                        sent_etas.add(node)

                    msgs = state_update.get("messages", [])
                    for m in msgs:
                        if not m.content: continue
                        content_str = str(m.content)
                        # Coleta tags de arquivos
                        tags = re.findall(r'<(?:SEND_FILE|SEND_AUDIO):([^>]+)>', content_str)
                        collected_tags.extend(tags)
                        # A última mensagem AI com conteúdo vira o texto final
                        if hasattr(m, "type") and m.type == "ai" and len(content_str) > 5:
                            final_text = content_str

            # 1. Limpa o texto final (remove tags para a mensagem de explicação ficar limpa)
            clean_response = re.sub(r'<(?:SEND_FILE|SEND_AUDIO):[^>]+>', '', final_text).strip()
            
            # 2. Envia a Mensagem de Texto (Explicação) PRIMEIRO
            if channel == "telegram":
                await send_telegram_message(user_id, clean_response)
            elif channel == "whatsapp":
                await send_whatsapp_message(user_id, clean_response)

            # 3. Envia os Arquivos Físicos LOGO EM SEGUIDA
            unique_tags = list(dict.fromkeys(collected_tags))
            output_dir = os.path.abspath(settings.DATA_OUTPUTS_PATH)
            
            for filename in unique_tags:
                filename = filename.strip()
                full_path = os.path.join(output_dir, filename)
                
                # Espera o arquivo estar pronto no disco
                from src.core.graph import wait_for_file
                if await wait_for_file(full_path, max_wait=10.0):
                    if channel == "telegram":
                        await safe_send_file(user_id, full_path)
                    elif channel == "whatsapp":
                        # Lógica de envio de arquivo whatsapp se disponível
                        pass
                else:
                    logger.error(f"[Brain] Arquivo não encontrado para entrega: {full_path}")

            return None # Retorna None porque as mensagens já foram enviadas via adapters

        except Exception as e:
            logger.error(f"Erro no execute_brain: {e}", exc_info=True)
            return f"Ops, falha técnica: {str(e)}"

# --- Webhooks (Mantidos) ---

@router.post("/telegram/webhook")
async def receive_telegram(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    if "message" not in body: return {"status": "ignored"}
    msg = body["message"]
    chat_id = str(msg.get("chat", {}).get("id", ""))
    user_name = msg.get("from", {}).get("first_name", "User")
    text = msg.get("text", "") or msg.get("caption", "")
    
    if not chat_id or not text: return {"status": "ignored"}

    async def status_callback(m: str): await send_telegram_message(chat_id, f"<i>{m}</i>")

    async def run_pipeline():
        await execute_brain(user_id=chat_id, text=text, channel="telegram", status_callback=status_callback, user_name=user_name)

    background_tasks.add_task(run_pipeline)
    return {"status": "queued"}
