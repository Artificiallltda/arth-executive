from fastapi import APIRouter, Request, BackgroundTasks
import logging
import platform
import asyncio
import re
import os
import time
from typing import Callable
from langchain_core.messages import HumanMessage

from src.config import settings
from src.core.engine import engine
from router.adapters.whatsapp import process_whatsapp_reply, send_whatsapp_message
from router.adapters.telegram import process_telegram_reply, send_telegram_message, safe_send_file

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

router = APIRouter()
logger = logging.getLogger(__name__)

# --- CONFIGURAÇÃO DE FILA E WORKERS (MANUS AI BLINDAGEM) ---
message_queue = asyncio.Queue()
NUM_WORKERS = 5

async def message_worker():
    """Worker que processa mensagens da fila de forma assíncrona."""
    while True:
        item = await message_queue.get()
        try:
            user_id = item["user_id"]
            text = item["text"]
            channel = item["channel"]
            user_name = item["user_name"]
            status_callback = item["status_callback"]
            media_data = item.get("media_data")

            logger.info(f"[WORKER] Processando mensagem de {user_id} ({channel})")
            
            # Executa o cérebro
            result = await execute_brain_logic(
                user_id=user_id, 
                text=text, 
                channel=channel, 
                status_callback=status_callback, 
                user_name=user_name,
                media_data=media_data
            )
            
            if isinstance(result, str) and result.startswith("Ops"):
                # Envia erro caso ocorra
                if channel == "telegram":
                    await send_telegram_message(user_id, f"⚠️ {result}")
                elif channel == "whatsapp":
                    await send_whatsapp_message(user_id, f"⚠️ {result}")

        except Exception as e:
            logger.error(f"[WORKER] Erro crítico no processamento: {e}", exc_info=True)
        finally:
            message_queue.task_done()

# Inicializa os workers
for _ in range(NUM_WORKERS):
    asyncio.create_task(message_worker())

# Controle de sessão e deduplicação
_user_locks: dict = {}

def _get_user_lock(user_id: str) -> asyncio.Lock:
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]

async def execute_brain_logic(user_id: str, text: str, channel: str, status_callback, user_name: str, media_data: dict):
    """Lógica interna de execução do grafo."""
    async with _get_user_lock(user_id):
        try:
            brain = await engine.get_brain()
            initial_state = {
                "messages": [HumanMessage(content=text)],
                "user_id": str(user_id),
                "channel": channel,
                "user_input": text,
                "content": "",
                "media_context": (media_data.get("b64") if media_data else None),
                "delivered_files": []
            }

            STATUS_NODES = {
                "arth_researcher": "Pesquisando dados relevantes... 🔍",
                "arth_executor": "Executando ferramentas e gerando arquivos... 💻",
                "arth_analyst": "Analisando dados estratégicos... 📊",
                "arth_planner": "Estruturando plano de ação... 📋",
                "arth_qa": "Revisando qualidade técnica... 🛡️",
            }
            
            sent_status = set()
            responses_pool = [] 

            config = {"configurable": {"thread_id": f"{channel}_{user_id}", "user_name": user_name}}

            async for event in brain.astream(initial_state, config=config):
                for node, state_update in event.items():
                    if node in STATUS_NODES and node not in sent_status:
                        if status_callback: await status_callback(STATUS_NODES[node])
                        sent_status.add(node)

                    msgs = state_update.get("messages", [])
                    for m in msgs:
                        content_str = str(m.content)
                        if hasattr(m, "type") and m.type == "ai" and len(content_str) > 10:
                            responses_pool.append({"node": node, "text": content_str})

            # Seleção de Resposta Final
            priority_nodes = ["arth_analyst", "arth_executor", "arth_researcher"]
            final_text = ""
            specialist_msgs = [r for r in responses_pool if r["node"] in priority_nodes]
            
            if specialist_msgs: final_text = max(specialist_msgs, key=lambda x: len(x["text"]))["text"]
            elif responses_pool: final_text = max(responses_pool, key=lambda x: len(x["text"]))["text"]
            else: final_text = "Tarefa processada com sucesso."

            # Extração de arquivos
            all_ai_text = " ".join([r["text"] for r in responses_pool])
            file_tags = re.findall(r'<(?:SEND_FILE|SEND_AUDIO):([^>]+)>', all_ai_text)
            unique_files = list(dict.fromkeys([t.strip() for t in file_tags]))

            clean_response = re.sub(r'<(?:SEND_FILE|SEND_AUDIO):[^>]+>', '', final_text).strip()
            
            # Envio da Mensagem de Texto
            if clean_response:
                if channel == "telegram": await send_telegram_message(user_id, clean_response)
                elif channel == "whatsapp": await send_whatsapp_message(user_id, clean_response)
            
            # Envio de Arquivos
            for filename in unique_files:
                full_path = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
                start_wait = time.time()
                file_ready = False
                while time.time() - start_wait < 20.0: # Aumentado para 20s
                    if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                        file_ready = True; break
                    await asyncio.sleep(1.0)
                
                if file_ready:
                    if channel == "telegram": await safe_send_file(user_id, full_path)
                    elif channel == "whatsapp":
                        from router.adapters.whatsapp import safe_send_whatsapp_file
                        await safe_send_whatsapp_file(user_id, full_path)

            return None 

        except Exception as e:
            logger.error(f"Erro execute_brain_logic: {e}")
            return f"Ops, falha técnica: {str(e)}"

@router.post("/telegram/webhook")
async def receive_telegram(request: Request):
    body = await request.json()
    if "message" not in body: return {"status": "ignored"}
    msg = body["message"]
    chat_id = str(msg.get("chat", {}).get("id", ""))
    if not chat_id: return {"status": "ignored"}
    
    user_name = msg.get("from", {}).get("first_name", "User")
    text = msg.get("text", "") or msg.get("caption", "")
    
    # 1. Resposta IMEDIATA (Blindagem Manus AI)
    await send_telegram_message(chat_id, "⏳ Processando sua mensagem...")
    
    # 2. Coloca na fila para os workers processarem
    async def status_cb(m: str): await send_telegram_message(chat_id, f"<i>{m}</i>")
    
    await message_queue.put({
        "user_id": chat_id,
        "text": text,
        "channel": "telegram",
        "user_name": user_name,
        "status_callback": status_cb
    })
    
    return {"status": "queued"}

@router.post("/whatsapp/webhook")
async def receive_whatsapp(request: Request):
    # Implementação análoga para WhatsApp se necessário
    return {"status": "ok"}
