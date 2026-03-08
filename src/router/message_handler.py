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

# Controle de sessão e lock por usuário
_session_counters: dict = {}
_user_locks: dict = {}
_RESET_KEYWORDS = {"resetar", "reset", "/reset", "limpar histórico", "limpar historico", "nova conversa", "começar do zero", "comecar do zero"}

def _get_thread_id(channel: str, user_id: str) -> str:
    key = f"{channel}_{user_id}"
    counter = _session_counters.get(key, 0)
    return f"{key}_s{counter}" if counter > 0 else key

def _get_user_lock(thread_key: str) -> asyncio.Lock:
    if thread_key not in _user_locks:
        _user_locks[thread_key] = asyncio.Lock()
    return _user_locks[thread_key]

def _reset_session(channel: str, user_id: str):
    key = f"{channel}_{user_id}"
    _session_counters[key] = _session_counters.get(key, 0) + 1
    logger.info(f"[Reset] Nova sessão iniciada para {key} (sessão {_session_counters[key]})")

async def execute_brain(user_id: str, text: str, channel: str = "whatsapp", status_callback=None, user_name: str = "User", media_data: dict = None):
    """Motor de raciocínio integral com restauração de funcionalidades."""
    logger.info(f"[{channel.upper()}] Processando mensagem de {user_name} ({user_id})")
    
    # Captura contexto de mídia (Ex: base64 da imagem enviada)
    media_b64 = None
    if media_data and "b64" in media_data:
        media_b64 = media_data["b64"]

    # Verifica comando de reset antes de qualquer processamento
    if text.lower().strip() in _RESET_KEYWORDS:
        _reset_session(channel, user_id)
        return "Histórico apagado! Pode começar uma nova conversa do zero."

    thread_key = _get_thread_id(channel, user_id)
    config = {
        "configurable": {"thread_id": thread_key, "user_name": user_name},
        "recursion_limit": 50
    }

    # Lock por usuário: evita que mensagens simultâneas conflitem no mesmo thread_id
    # (geração de imagem leva ~60s — sem lock, a 2ª mensagem corromperia o estado)
    async with _get_user_lock(thread_key):
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

            STATUS_NODES = {
                "arth_researcher": "Pesquisando dados relevantes... 🔍⏳",
                "arth_executor": "Executando ferramentas e gerando artefatos... 💻⏳",
                "arth_planner": "Estruturando o plano de ação... 📋⏳",
                "arth_analyst": "Analisando dados e faturamentos... 📊⏳",
                "arth_qa": "Revisando a qualidade técnica... 🛡️⏳",
            }
            SPECIALIST_NODES = {"arth_executor", "arth_researcher", "arth_analyst"}

            sent_etas = set()
            collected_tags = []        # tags capturadas durante o stream
            last_specialist_text = None

            async for event in brain.astream(initial_state, config=config):
                for node, state_update in event.items():
                    # Status callback — uma única vez por nó
                    if node in STATUS_NODES and node not in sent_etas:
                        if status_callback:
                            await status_callback(STATUS_NODES[node])
                        sent_etas.add(node)

                    # Captura tags e texto dos especialistas direto do delta do stream
                    for msg in state_update.get("messages", []):
                        if not hasattr(msg, "content") or not msg.content:
                            continue
                        content_str = str(msg.content)
                        tags = re.findall(r'<(?:SEND_FILE|SEND_AUDIO):[^>]+>', content_str)
                        collected_tags.extend(tags)
                        if node in SPECIALIST_NODES:
                            last_specialist_text = content_str

            # Monta resposta final
            final_response = last_specialist_text or "Tarefa concluída."
            final_response = re.sub(r'!?\[.*?\]\(.*?\)', '', final_response).strip()

            # Garante que todas as tags capturadas no stream estejam na resposta (sem duplicatas)
            unique_tags = list(dict.fromkeys(collected_tags))
            for tag in unique_tags:
                if tag not in final_response:
                    final_response += f"\n{tag}"

            logger.info(f"[Brain] Resposta final pronta. Tags={unique_tags}")
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
