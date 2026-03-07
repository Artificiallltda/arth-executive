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
    """Função core para rodar o raciocínio com persistência de estado e HITL real."""
    logger.info(f"[{channel.upper()}] Processando mensagem de {user_name} ({user_id})")
    
    config = {
        "configurable": {"thread_id": f"{channel}_{user_id}", "user_name": user_name},
        "recursion_limit": 50
    }
    
    try:
        brain = await engine.get_brain()
        state = await brain.aget_state(config)
        
        approval_keywords = ["sim", "ok", "pode", "pode ir", "autorizado", "vai", "autorizo", "autorizada", "concordo", "fechado"]
        is_approval = any(word in text.lower().strip() for word in approval_keywords)

        # --- LÓGICA HITL CORRIGIDA ---
        if state.next and "arth_approval" in state.next and is_approval:
            logger.info(f"[{channel.upper()}] HITL: Injetando aprovação no histórico e retomando...")
            if status_callback: await status_callback("Aprovação registrada. Executando agora! 🚀⚙️")
            
            # 1. ATUALIZA O ESTADO: Injeta a mensagem do usuário no checkpoint antes de retomar
            # Isso garante que o Orchestrator veja o "Sim" no histórico.
            await brain.aupdate_state(config, {"messages": [HumanMessage(content=text)]})
            
            # 2. RETOMA: Inicia de onde parou (None indica continuação do checkpoint)
            async for event in brain.astream(None, config=config):
                for node, _ in event.items():
                    logger.debug(f"[Grafo] Executando nó: {node}")
        else:
            # Caso Normal: Nova tarefa ou o usuário disse outra coisa
            content = text
            if media_data and "b64" in media_data:
                content = [{"type": "text", "text": text}, {"type": "text", "text": "[SISTEMA: Mídia enviada]"}]

            initial_state = {"messages": [HumanMessage(content=content)], "user_id": str(user_id)}
            
            sent_etas = set()
            async for event in brain.astream(initial_state, config=config):
                for node, _ in event.items():
                    status_messages = {
                        "arth_researcher": "Pesquisando dados... 🔍⏳",
                        "arth_executor": "Executando tarefas... 💻⏳",
                        "arth_planner": "Criando plano... 📋⏳",
                        "arth_analyst": "Analisando... 📊⏳",
                        "arth_qa": "Revisando qualidade... 🛡️⏳"
                    }
                    if node in status_messages and node not in sent_etas:
                        if status_callback: await status_callback(status_messages[node])
                        sent_etas.add(node)

        # Captura o estado final para resposta
        final_state = await brain.aget_state(config)
        
        # Verifica se caiu em um novo ponto de aprovação
        if final_state.next and "arth_approval" in final_state.next:
            return (
                "[⚠️ Ação Crítica] Esta tarefa exige execução de comandos.\n\n"
                "**Você autoriza o Arth a prosseguir?** (Responda 'Sim' ou 'Ok')"
            )

        # Pega a última mensagem AI
        for m in reversed(final_state.values.get("messages", [])):
            if m.type == "ai" and m.content:
                return m.content
        
        return "Tarefa concluída, Comandante. O que mais posso fazer?"

    except Exception as e:
        logger.error(f"Erro no execute_brain: {e}", exc_info=True)
        return f"Ops, tive uma falha técnica executiva: {str(e)}"

# --- WEBHOOKS (Minimizados para clareza) ---

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
