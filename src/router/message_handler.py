from fastapi import APIRouter, Request, BackgroundTasks, Query
import logging
import platform
import asyncio
import re
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
    """Motor de raciocínio integral com restauração de funcionalidades."""
    logger.info(f"[{channel.upper()}] Processando mensagem de {user_name} ({user_id})")
    
    # Captura contexto de mídia (Ex: base64 da imagem enviada)
    media_b64 = None
    if media_data and "b64" in media_data:
        media_b64 = media_data["b64"]

    config = {
        "configurable": {"thread_id": f"{channel}_{user_id}", "user_name": user_name},
        "recursion_limit": 50
    }
    
    try:
        brain = await engine.get_brain()

        content = text
        if media_b64:
            content = [
                {"type": "text", "text": text},
                {"type": "text", "text": "\n[SISTEMA: O Usuário enviou mídia de referência. Use-a se necessário.]"}
            ]

        initial_state = {
            "messages": [HumanMessage(content=content)],
            "user_id": str(user_id),
            "channel": channel,
            "media_context": media_b64,
        }

        sent_etas = set()
        async for event in brain.astream(initial_state, config=config):
            for node, state_update in event.items():
                status_messages = {
                    "arth_researcher": "Pesquisando dados relevantes... 🔍⏳",
                    "arth_executor": "Executando ferramentas e gerando artefatos... 💻⏳",
                    "arth_planner": "Estruturando o plano de ação... 📋⏳",
                    "arth_analyst": "Analisando dados e faturamentos... 📊⏳",
                    "arth_qa": "Revisando a qualidade técnica... 🛡️⏳"
                }
                if node in status_messages and node not in sent_etas:
                    if status_callback: await status_callback(status_messages[node])
                    sent_etas.add(node)

        # --- RESULTADO FINAL INTELIGENTE E ROBUSTO ---
        final_state = await brain.aget_state(config)
        messages = final_state.values.get("messages", [])

        # 1. Coleta todas as tags de mídias geradas nesta thread (Busca agressiva)
        all_tags = []
        for m in messages:
            content_str = str(m.content)
            # Detecta tags mesmo se o LLM as envolveu em lixo ou backticks
            found = re.findall(r'(?:SEND_FILE|SEND_AUDIO):[^> \n`]+', content_str)
            for f in found:
                all_tags.append(f"<{f}>")
        
        unique_tags = list(dict.fromkeys(all_tags))

        # 2. Busca a resposta textual da IA
        last_ai_msg = None
        for m in reversed(messages):
            if m.type == "ai":
                if getattr(m, "name", "") in ["arth_executor", "arth_researcher", "arth_analyst"] and m.content:
                    last_ai_msg = m.content
                    break
                if last_ai_msg is None and m.content:
                    last_ai_msg = m.content

        final_response = last_ai_msg or "Tarefa concluída."
        
        # Limpeza Anti-Hallucinação: remove [links] e !images markdown que o LLM ousar criar
        final_response = re.sub(r'!?\[.*?\]\(.*?\)', '', str(final_response))
        
        # 3. Garante que as tags de mídia reais estejam presentes
        for tag in unique_tags:
            if tag not in final_response:
                final_response += f"\n{tag}"
        
        return final_response
            
    except Exception as e:
        logger.error(f"Erro no execute_brain: {e}", exc_info=True)
        return f"Ops, a Squad Executiva teve uma falha técnica: {str(e)}"

# --- WEBHOOKS RESTAURADOS ---

@router.post("/whatsapp/webhook")
async def receive_whatsapp(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    if not isinstance(body, dict) or "data" not in body: return {"status": "ignored"}
    
    data = body.get("data", {})
    message_info = data.get("message", {})
    remote_jid = data.get("key", {}).get("remoteJid", "")
    push_name = data.get("pushName", "Usuário")
    
    if not remote_jid or data.get("key", {}).get("fromMe"): return {"status": "ignored"}

    text = message_info.get("conversation", "") or message_info.get("extendedTextMessage", {}).get("text", "")
    audio_msg = message_info.get("audioMessage")
    # Tenta pegar base64 de múltiplos lugares possíveis na Evolution v2
    media_b64 = data.get("base64") or message_info.get("base64")
    
    async def status_callback(msg: str): await send_whatsapp_message(remote_jid, f"_{msg}_")
        
    async def run_pipeline():
        final_text = text
        media_context = None
        
        # RESTAURAÇÃO: Trata áudio (com tratamento de erro robusto)
        if audio_msg and media_b64:
            await status_callback("Ouvindo seu áudio... 🎧⏳")
            temp_path = os.path.join(settings.DATA_OUTPUTS_PATH, f"in_{uuid.uuid4().hex[:8]}.ogg")
            try:
                # Remove prefixo data:audio/... se existir
                clean_b64 = media_b64.split(",")[-1] if "," in media_b64 else media_b64
                with open(temp_path, "wb") as f:
                    f.write(base64.b64decode(clean_b64))
                
                transcription = await transcribe_audio_file(temp_path)
                if transcription and not transcription.startswith("Falha"):
                    final_text = transcription
                    logger.info(f"[Audio] Transcrição concluída: {final_text[:50]}...")
                else:
                    await status_callback("Não consegui entender o áudio perfeitamente, pode repetir?")
                    return
            except Exception as e:
                logger.error(f"Erro ao processar áudio: {e}")
                await status_callback("Houve um erro técnico ao processar seu áudio.")
                return
            finally:
                if os.path.exists(temp_path): os.remove(temp_path)
        elif media_b64:
            media_context = {"b64": media_b64}

        if not final_text and not media_context: return
        
        response = await execute_brain(
            user_id=remote_jid, 
            text=final_text, 
            channel="whatsapp", 
            status_callback=status_callback, 
            user_name=push_name,
            media_data=media_context
        )
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
    user_name = msg.get("from", {}).get("first_name", "Usuário")
    
    if not text or not chat_id: return {"status": "ignored"}

    async def status_callback(msg: str): await send_telegram_message(chat_id, f"_{msg}_")

    async def run_pipeline():
        response = await execute_brain(
            user_id=chat_id, 
            text=text, 
            channel="telegram", 
            status_callback=status_callback, 
            user_name=user_name
        )
        await process_telegram_reply(chat_id, response)

    background_tasks.add_task(run_pipeline)
    return {"status": "queued"}

@router.get("/instagram/webhook")
async def verify_instagram(mode: str = Query(None, alias="hub.mode"), token: str = Query(None, alias="hub.verify_token"), challenge: str = Query(None, alias="hub.challenge")):
    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN: return int(challenge)
    return "Falha", 403

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
            response = await execute_brain(user_id=sender_id, text=text, channel="instagram", user_name="Usuário Instagram")
            await process_instagram_reply(sender_id, response)
        background_tasks.add_task(run_pipeline)
        return {"status": "ok"}
    except: return {"status": "error"}
