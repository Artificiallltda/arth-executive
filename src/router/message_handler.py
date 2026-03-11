from fastapi import APIRouter, Request, BackgroundTasks, Query
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
_RESET_KEYWORDS = {"resetar", "reset", "/reset", "limpar histórico"}

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
                "media_context": media_data.get("b64") if media_data else None,
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
            rich_responses = [] # Guardará todas as mensagens AI detalhadas

            async for event in brain.astream(initial_state, config=config):
                for node, state_update in event.items():
                    if node in STATUS_NODES and node not in sent_etas:
                        if status_callback: await status_callback(STATUS_NODES[node])
                        sent_etas.add(node)

                    msgs = state_update.get("messages", [])
                    for m in msgs:
                        if not m.content: continue
                        content_str = str(m.content)
                        # Se for uma resposta de um especialista (não o orquestrador dando tchau), guardamos
                        if hasattr(m, "name") and m.name != "arth_orchestrator" and len(content_str) > 20:
                            rich_responses.append(content_str)
                        elif not hasattr(m, "name") and len(content_str) > 20:
                            rich_responses.append(content_str)

            # Escolhe a resposta mais longa do turno (geralmente a explicação detalhada)
            if rich_responses:
                final_text = max(rich_responses, key=len)
            else:
                final_text = "Tarefa concluída com sucesso. O material solicitado foi entregue."

            # Limpa tags para o texto final ficar elegante
            clean_response = re.sub(r'<(?:SEND_FILE|SEND_AUDIO):[^>]+>', '', final_text).strip()
            
            # Envia a EXPLICAÇÃO PREMIUM
            if clean_response:
                if channel == "telegram":
                    await send_telegram_message(user_id, clean_response)
                elif channel == "whatsapp":
                    await send_whatsapp_message(user_id, clean_response)

            return None 

        except Exception as e:
            logger.error(f"Erro no execute_brain: {e}", exc_info=True)
            return f"Ops, falha técnica: {str(e)}"

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
