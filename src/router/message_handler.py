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
    """Fun\u00e7\u00e3o core para rodar o racioc\u00ednio independente do canal."""
    logger.info(f"[{channel.upper()}] Processando mensagem de {user_name} ({user_id})")
    
    # Captura contexto de m\u00eddia (Ex: base64 da imagem enviada)
    media_b64 = None
    if media_data and "b64" in media_data:
        media_b64 = media_data["b64"]

    content = text
    if media_data:
        content = [
            {"type": "text", "text": text},
            {"type": "text", "text": f"\n[SISTEMA: O Usu\u00e1rio enviou m\u00eddia de refer\u00eancia. Use-a se necess\u00e1rio.]"}
        ]

    initial_state = {
        "messages": [HumanMessage(content=content)],
        "user_id": str(user_id),
        "channel": channel,
        "media_context": media_b64 # Passa a imagem para o estado
    }
    
    config = {
        "configurable": {"thread_id": f"{channel}_{user_id}", "user_name": user_name},
        "recursion_limit": 50
    }
    
    try:
        sent_etas = set()
        brain = await engine.get_brain()
        
        async for event in brain.astream(initial_state, config=config):
            for node, state_update in event.items():
                # Notifica\u00e7\u00f5es de Status (ETA) baseadas nos n\u00f3s do grafo
                status_messages = {
                    "arth_researcher": "Pesquisando dados relevantes... \ud83d\udd0d\u23f3",
                    "arth_executor": "Executando ferramentas e gerando artefatos... \ud83d\udcbb\u23f3",
                    "arth_planner": "Estruturando o plano de a\u00e7\u00e3o... \ud83d\udccb\u23f3",
                    "arth_analyst": "Analisando dados e faturamentos... \ud83d\udcca\u23f3",
                    "arth_qa": "Revisando a qualidade t\u00e9cnica... \ud83d\udee1\ufe0f\u23f3"
                }
                if node in status_messages and node not in sent_etas:
                    if status_callback: await status_callback(status_messages[node])
                    sent_etas.add(node)
        
        final_state = await brain.aget_state(config)
        
        # HITL (Human-in-the-loop)
        if final_state.next and "arth_approval" in final_state.next:
            return (
                "[\u26A0\uFE0F A\u00e7\u00e3o Cr\u00edtica] Esta tarefa exige execu\u00e7\u00e3o de comandos ou agendamentos.\n\n"
                "**Voc\u00ea autoriza o Arth a prosseguir?** (Responda 'Sim' ou 'Ok')"
            )

        return final_state.values["messages"][-1].content
            
    except Exception as e:
        logger.error(f"Erro no execute_brain: {e}", exc_info=True)
        return f"Ops, a Squad Executiva teve uma falha t\u00e9cnica: {str(e)}"

# --- WEBHOOKS ---

@router.post("/whatsapp/webhook")
async def receive_whatsapp(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    if not isinstance(body, dict) or "data" not in body: return {"status": "ignored"}
    
    data = body.get("data", {})
    message_info = data.get("message", {})
    remote_jid = data.get("key", {}).get("remoteJid", "")
    push_name = data.get("pushName", "Usu\u00e1rio")
    
    if data.get("key", {}).get("fromMe"): return {"status": "ignored"}

    text = message_info.get("conversation", "") or message_info.get("extendedTextMessage", {}).get("text", "")
    audio_msg = message_info.get("audioMessage")
    
    # Processamento de M\u00eddia Base64 (Evolution API envia no n\u00edvel raiz do data)
    media_b64 = data.get("base64")
    
    async def status_callback(msg: str):
        await send_whatsapp_message(remote_jid, f"_{msg}_")
        
    async def run_pipeline():
        final_text = text
        # Se for \u00e1udio, intercepta e transcreve primeiro
        if audio_msg and media_b64:
            await status_callback("Ouvindo seu \u00e1udio... \ud83c\udfa7\u23f3")
            temp_path = os.path.join(settings.DATA_OUTPUTS_PATH, f"in_{uuid.uuid4().hex[:8]}.ogg")
            try:
                with open(temp_path, "wb") as f:
                    f.write(base64.b64decode(media_b64))
                transcription = await transcribe_audio_file(temp_path)
                final_text = transcription
                logger.info(f"[\ud83c\udfa4 Transcri\u00e7\u00e3o WhatsApp] {final_text}")
                # Avisa ao modelo que isso foi enviado por voz
                final_text += "\n[SISTEMA: O usu\u00e1rio te enviou a mensagem acima por \u00e1udio. Voc\u00ea pode responder com \u00e1udio se quiser usando a ferramenta generate_audio]."
            except Exception as e:
                logger.error(f"Erro na transcri\u00e7\u00e3o: {e}")
            finally:
                if os.path.exists(temp_path): os.remove(temp_path)
        
        if not final_text: return
        
        response = await execute_brain(user_id=remote_jid, text=final_text, channel="whatsapp", status_callback=status_callback, user_name=push_name)
        await process_whatsapp_reply(remote_jid, response)

    background_tasks.add_task(run_pipeline)
    return {"status": "queued"}

@router.post("/telegram/webhook")
async def receive_telegram(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    logger.info(f"[TELEGRAM Webhook] Payload recebido")
    if "message" not in body: return {"status": "ignored"}
    
    msg = body["message"]
    text = msg.get("text", "")
    chat_id = str(msg.get("chat", {}).get("id", ""))
    user_name = msg.get("from", {}).get("first_name", "Usu\u00e1rio")
    
    if not text or not chat_id: return {"status": "ignored"}

    async def status_callback(msg: str):
        await send_telegram_message(chat_id, f"_{msg}_")

    async def run_pipeline():
        response = await execute_brain(user_id=chat_id, text=text, channel="telegram", status_callback=status_callback, user_name=user_name)
        await process_telegram_reply(chat_id, response)

    background_tasks.add_task(run_pipeline)
    return {"status": "queued"}

@router.get("/instagram/webhook")
async def verify_instagram(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    """Verificação do webhook exigida pela Meta."""
    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("[INSTAGRAM] Webhook verificado com sucesso")
        return int(challenge)
    return "Falha na verificação", 403

@router.post("/instagram/webhook")
async def receive_instagram(request: Request, background_tasks: BackgroundTasks):
    """Webhook para Instagram (Direto via Meta Graph API)."""
    data = await request.json()
    logger.info(f"[INSTAGRAM Webhook] Payload Meta recebido")
    
    # Parsing do formato Meta Graph API
    try:
        entry = data.get("entry", [{}])[0]
        messaging = entry.get("messaging", [{}])[0]
        sender_id = messaging.get("sender", {}).get("id", "")
        message = messaging.get("message", {})
        text = message.get("text", "")
        
        # A Meta não envia o nome do usuário no payload do webhook, 
        # seria necessário uma chamada extra à API (/SENDER_ID) para obter.
        user_name = "Usuário Instagram"
        
        if not text or not sender_id: return {"status": "ignored"}

        async def status_callback(msg: str):
            # O Instagram direto não suporta status de digitando via API comum de forma simples
            pass
            
        async def run_pipeline():
            response = await execute_brain(user_id=sender_id, text=text, channel="instagram", status_callback=status_callback, user_name=user_name)
            await process_instagram_reply(sender_id, response)

        background_tasks.add_task(run_pipeline)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Erro ao processar webhook Instagram Meta: {e}")
        return {"status": "error"}
