from fastapi import APIRouter, Request, BackgroundTasks, Query
import logging
import platform
import asyncio
from langchain_core.messages import HumanMessage

from src.config import settings
from src.core.engine import engine
from src.router.adapters.whatsapp import process_whatsapp_reply, send_whatsapp_message
from src.router.adapters.telegram import process_telegram_reply, send_telegram_message
from src.router.adapters.instagram import process_instagram_reply, send_instagram_message
from src.utils.audio_transcriber import transcribe_audio_file
import os
import uuid
import base64

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

router = APIRouter()
logger = logging.getLogger(__name__)

async def execute_brain(user_id: str, text: str, channel: str = "whatsapp", status_callback=None, user_name: str = "User", media_data: dict = None):
    """Função core para rodar o raciocínio com bypass de HITL injetado."""
    logger.info(f"[{channel.upper()}] Mensagem: {text[:50]}...")
    
    config = {
        "configurable": {"thread_id": f"{channel}_{user_id}", "user_name": user_name},
        "recursion_limit": 50
    }
    
    try:
        brain = await engine.get_brain()
        state = await brain.aget_state(config)
        
        approval_keywords = ["sim", "ok", "pode", "pode ir", "autorizado", "vai", "autorizo", "autorizada", "concordo", "fechado", "pode executar"]
        is_approval = any(word in text.lower().strip() for word in approval_keywords)

        # --- RECOVERY / HITL BYPASS ---
        # Se estamos num breakpoint E o usuário disse 'Sim'
        if state.next and "arth_approval" in state.next and is_approval:
            logger.info(f"[HITL] Injetando aprovação manual para {user_id}")
            if status_callback: await status_callback("Autorização confirmada. Executando agora! 🚀")
            
            # Injetamos o estado 'approved' manualmente para o supervisor ver
            await brain.aupdate_state(config, {"approval_status": "approved", "messages": [HumanMessage(content=text)]})
            
            # Retomamos o grafo enviando None (continuar do checkpoint)
            async for event in brain.astream(None, config=config):
                pass
        else:
            # Caso normal ou dúvida nova
            initial_state = {
                "messages": [HumanMessage(content=text)],
                "user_id": str(user_id),
                "approval_status": "none"
            }
            
            sent_etas = set()
            async for event in brain.astream(initial_state, config=config):
                for node, _ in event.items():
                    status_messages = {
                        "arth_researcher": "Pesquisando... 🔍",
                        "arth_executor": "Executando... 💻",
                        "arth_planner": "Planejando... 📋",
                        "arth_analyst": "Analisando... 📊",
                        "arth_qa": "Revisando... 🛡️"
                    }
                    if node in status_messages and node not in sent_etas:
                        if status_callback: await status_callback(status_messages[node])
                        sent_etas.add(node)

        # Resposta Final
        final_state = await brain.aget_state(config)
        
        if final_state.next and "arth_approval" in final_state.next:
            return "[⚠️ Ação Crítica] Esta tarefa exige execução de comandos.\n\n**Você autoriza o Arth a prosseguir?** (Responda 'Sim' ou 'Ok')"

        for m in reversed(final_state.values.get("messages", [])):
            if m.type == "ai" and m.content:
                return m.content
        
        return "Concluído conforme solicitado."

    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
        return f"Ops, tive uma falha técnica executiva: {str(e)}"

# --- WEBHOOKS (Simplified) ---

@router.post("/whatsapp/webhook")
async def receive_whatsapp(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    if not isinstance(body, dict) or "data" not in body: return {"status": "ignored"}
    data = body.get("data", {})
    remote_jid = data.get("key", {}).get("remoteJid", "")
    if data.get("key", {}).get("fromMe"): return {"status": "ignored"}
    text = data.get("message", {}).get("conversation", "") or data.get("message", {}).get("extendedTextMessage", {}).get("text", "")
    
    async def status_callback(msg: str): await send_whatsapp_message(remote_jid, f"_{msg}_")
    async def run_pipeline():
        response = await execute_brain(user_id=remote_jid, text=text, channel="whatsapp", status_callback=status_callback, user_name=data.get("pushName", "User"))
        await process_whatsapp_reply(remote_jid, response)
    background_tasks.add_task(run_pipeline)
    return {"status": "queued"}

@router.post("/telegram/webhook")
async def receive_telegram(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    if "message" not in body: return {"status": "ignored"}
    msg = body["message"]
    text = msg.get("text", "")
    chat_id = str(msg.get("chat", {}).get("id", ""))
    async def status_callback(msg: str): await send_telegram_message(chat_id, f"_{msg}_")
    async def run_pipeline():
        response = await execute_brain(user_id=chat_id, text=text, channel="telegram", status_callback=status_callback, user_name=msg.get("from", {}).get("first_name", "User"))
        await process_telegram_reply(chat_id, response)
    background_tasks.add_task(run_pipeline)
    return {"status": "queued"}

@router.get("/instagram/webhook")
async def verify_instagram(mode: str = Query(None, alias="hub.mode"), token: str = Query(None, alias="hub.verify_token"), challenge: str = Query(None, alias="hub.challenge")):
    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN: return int(challenge)
    return "Error", 403

@router.post("/instagram/webhook")
async def receive_instagram(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        entry = data.get("entry", [{}])[0]
        messaging = entry.get("messaging", [{}])[0]
        sender_id = messaging.get("sender", {}).get("id", "")
        text = messaging.get("message", {}).get("text", "")
        if not text or not sender_id: return {"status": "ignored"}
        async def run_pipeline():
            response = await execute_brain(user_id=sender_id, text=text, channel="instagram")
            await process_instagram_reply(sender_id, response)
        background_tasks.add_task(run_pipeline)
        return {"status": "ok"}
    except: return {"status": "error"}
