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
from src.router.adapters.telegram import process_telegram_reply, send_telegram_message
from src.router.adapters.instagram import process_instagram_reply, send_instagram_message
from src.utils.audio_transcriber import transcribe_audio_file

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

router = APIRouter()
logger = logging.getLogger(__name__)

# Controle de sessão e deduplicação
_session_counters: dict = {}
_user_locks: dict = {}
_last_messages: dict = {} # {user_id: hash}
_RESET_KEYWORDS = {"resetar", "reset", "/reset", "limpar histórico", "limpar historico", "nova conversa", "começar do zero", "comecar do zero"}

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
    if _last_messages.get(user_id) == msg_hash:
        return True
    _last_messages[user_id] = msg_hash
    return False

def _reset_session(channel: str, user_id: str):
    key = f"{channel}_{user_id}"
    _session_counters[key] = _session_counters.get(key, 0) + 1
    logger.info(f"[Reset] Nova sessão iniciada para {key}")

async def execute_brain(user_id: str, text: str, channel: str = "whatsapp", status_callback=None, user_name: str = "User", media_data: dict = None):
    """Motor de raciocínio integral com suporte a documentos e sanitização HTML."""
    
    # ==================================================================
    # VALIDAÇÃO ABSOLUTA (IMPEDE None DE CHEGAR NO PYDANTIC)
    # ==================================================================
    if text is None:
        logger.error("[Brain] ❌ text (user_input) é None! Corrigindo para string vazia.")
        text = ""
    
    if not isinstance(text, str):
        logger.warning(f"[Brain] text não é string: {type(text)}. Convertendo.")
        text = str(text) if text is not None else ""
    
    if user_id is None:
        logger.error("[Brain] ❌ user_id é None! Usando 'unknown'.")
        user_id = "unknown"
    
    # LOG DETALHADO DO QUE ESTÁ CHEGANDO
    logger.debug(f"[Brain] user_input type: {type(text)}, value: {repr(text)[:100]}")
    logger.debug(f"[Brain] user_id type: {type(user_id)}, value: {user_id}")
    
    logger.info(f"[{channel.upper()}] Processando mensagem de {user_name} ({user_id}): '{text[:50]}...'")
    
    if _is_duplicate(str(user_id), text):
        logger.info(f"[Deduplication] Ignorando mensagem repetida de {user_id}")
        return None

    if text.lower().strip() == "/logs":
        from src.utils.log_buffer import get_logs_text
        return get_logs_text(n=30)

    if text.lower().strip() in _RESET_KEYWORDS:
        _reset_session(channel, user_id)
        return "Histórico apagado! Pode começar uma nova conversa do zero."

    thread_key = _get_thread_id(channel, user_id)
    config = {"configurable": {"thread_id": thread_key, "user_name": user_name}, "recursion_limit": 50}

    async with _get_user_lock(thread_key):
        try:
            brain = await engine.get_brain()
            initial_state = {
                "messages": [HumanMessage(content=text)],
                "user_id": str(user_id),
                "channel": channel,
                "media_context": media_data.get("b64") if media_data else None,
            }

            STATUS_NODES = {
                "arth_researcher": "Pesquisando dados relevantes... 🔍⏳",
                "arth_executor": "Executando ferramentas e gerando artefatos... 💻⏳",
                "arth_planner": "Estruturando o plano de ação... 📋⏳",
                "arth_analyst": "Analisando dados e faturamentos... 📊⏳",
                "arth_qa": "Revisando a qualidade técnica... 🛡️⏳",
            }
            SPECIALIST_NODES = {"arth_executor", "arth_researcher", "arth_analyst", "arth_planner", "arth_qa", "arth_orchestrator"}

            sent_etas = set()
            collected_tags = []
            last_specialist_text = None

            async for event in brain.astream(initial_state, config=config):
                for node, state_update in event.items():
                    if node in STATUS_NODES and node not in sent_etas:
                        if status_callback: await status_callback(STATUS_NODES[node])
                        sent_etas.add(node)

                    msgs = state_update.get("messages", [])
                    for m in msgs:
                        if not hasattr(m, "content") or not m.content: continue
                        content_str = str(m.content)
                        tags = re.findall(r'<(?:SEND_FILE|SEND_AUDIO):[^>]+>', content_str)
                        collected_tags.extend(tags)
                        if node in SPECIALIST_NODES:
                            last_specialist_text = content_str

            final_response = last_specialist_text or "Tarefa concluída."
            final_response = re.sub(r'!?\[.*?\]\(.*?\)', '', final_response).strip()

            unique_tags = list(dict.fromkeys(collected_tags))
            for tag in unique_tags:
                if tag not in final_response: final_response += f"\n{tag}"

            # Sanitização Final para Telegram HTML
            if channel == "telegram":
                # Extrai tags de arquivo para restaurá-las intocadas depois do escape HTML
                file_tags_to_restore = re.findall(r'<(?:SEND_FILE|SEND_AUDIO):[^>]+>', final_response)
                
                # Escapa os caracteres HTML básicos
                final_response = final_response.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                
                # Converte Markdown básico para HTML suportado pelo Telegram
                final_response = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', final_response)
                final_response = re.sub(r'\*(.*?)\*', r'<i>\1</i>', final_response)
                final_response = re.sub(r'_(.*?)_', r'<i>\1</i>', final_response)
                
                # Restaura as tags de arquivo/áudio que foram escapadas
                for tag in file_tags_to_restore:
                    escaped_tag = tag.replace("<", "&lt;").replace(">", "&gt;")
                    final_response = final_response.replace(escaped_tag, tag)

            return final_response

        except Exception as e:
            logger.error(f"Erro no execute_brain: {e}", exc_info=True)
            return f"Ops, falha técnica: {str(e)}"

# --- WEBHOOKS ---

@router.post("/whatsapp/webhook")
async def receive_whatsapp(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    if not isinstance(body, dict) or "data" not in body: return {"status": "ignored"}
    data = body.get("data", {})
    message_info = data.get("message", {})
    remote_jid = data.get("key", {}).get("remoteJid", "")
    if not remote_jid or data.get("key", {}).get("fromMe"): return {"status": "ignored"}
    text = message_info.get("conversation", "") or message_info.get("extendedTextMessage", {}).get("text", "")
    async def run_pipeline():
        response = await execute_brain(user_id=remote_jid, text=text, channel="whatsapp", user_name=data.get("pushName", "User"))
        if response: await process_whatsapp_reply(remote_jid, response)
    background_tasks.add_task(run_pipeline)
    return {"status": "queued"}

@router.post("/telegram/webhook")
async def receive_telegram(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    if "message" not in body: return {"status": "ignored"}
    msg = body["message"]
    chat_id = str(msg.get("chat", {}).get("id", ""))
    user_name = msg.get("from", {}).get("first_name", "User")
    
    text = msg.get("text", "") or msg.get("caption", "")
    document = msg.get("document")
    
    if not chat_id: return {"status": "ignored"}

    async def status_callback(m: str): await send_telegram_message(chat_id, f"<i>{m}</i>")

    async def run_pipeline():
        final_text = text
        if document:
            file_id = document.get("file_id")
            file_name = document.get("file_name", f"doc_{uuid.uuid4().hex[:6]}")
            safe_name = re.sub(r'[^\w\s.-]', '', file_name).replace(' ', '_')
            await status_callback(f"Recebi seu arquivo '{safe_name}', estou baixando para analisar... 📥")
            from src.router.adapters.telegram import download_telegram_file
            local_path = await download_telegram_file(file_id, safe_name)
            if local_path:
                instruction = f"\n\n[SISTEMA: O usuário enviou o arquivo '{safe_name}'. Use read_document para analisá-lo.]"
                final_text = (final_text + instruction) if final_text else instruction
            else:
                await status_callback("Falha ao baixar arquivo.")
                return

        if not final_text: return
        response = await execute_brain(user_id=chat_id, text=final_text, channel="telegram", status_callback=status_callback, user_name=user_name)
        if response: await process_telegram_reply(chat_id, response)

    background_tasks.add_task(run_pipeline)
    return {"status": "queued"}

@router.post("/instagram/webhook")
async def receive_instagram(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        entry = data.get("entry", [{}])[0]
        messaging = entry.get("messaging", [{}])[0]
        sender_id = messaging.get("sender", {}).get("id", "")
        text = messaging.get("message", {}).get("text", "")
        async def run_pipeline():
            response = await execute_brain(user_id=sender_id, text=text, channel="instagram")
            if response: await process_instagram_reply(sender_id, response)
        background_tasks.add_task(run_pipeline)
        return {"status": "ok"}
    except: return {"status": "error"}
