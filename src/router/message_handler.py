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
    """Função core para rodar o raciocínio independente do canal com suporte a HITL."""
    logger.info(f"[{channel.upper()}] Processando mensagem de {user_name} ({user_id})")
    
    # Contexto de mídia
    media_b64 = None
    if media_data and "b64" in media_data:
        media_b64 = media_data["b64"]

    content = text
    if media_data:
        content = [
            {"type": "text", "text": text},
            {"type": "text", "text": f"\n[SISTEMA: O Usuário enviou mídia de referência. Use-a se necessário.]"}
        ]

    config = {
        "configurable": {"thread_id": f"{channel}_{user_id}", "user_name": user_name},
        "recursion_limit": 50
    }
    
    try:
        brain = await engine.get_brain()
        state = await brain.aget_state(config)
        
        # --- LÓGICA DE HITL (RECORRÊNCIA) ---
        # Se o grafo está parado esperando aprovação E o usuário disse Sim/Ok
        approval_keywords = ["sim", "ok", "pode", "pode ir", "autorizado", "vai", "autorizo", "autorizada", "concordo"]
        is_approval = any(word in text.lower().strip() for word in approval_keywords)
        
        if state.next and "arth_approval" in state.next and is_approval:
            logger.info(f"[{channel.upper()}] Usuário APROVOU ação crítica. Retomando grafo...")
            if status_callback: await status_callback("Aprovação recebida! Prosseguindo com a execução... 🚀⚙️")
            
            # Atualiza o estado para marcar como aprovado e continua do ponto de parada
            # O input None sinaliza para o astream continuar de onde parou (checkpoint)
            async for event in brain.astream(None, config=config):
                pass # Execução interna dos nós retomados
        else:
            # Caso normal: Nova mensagem ou mensagem que não é um Sim/Ok (pode ser um Não ou outra dúvida)
            initial_state = {
                "messages": [HumanMessage(content=content)],
                "user_id": str(user_id),
                "channel": channel,
                "media_context": media_b64
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
        
        # Pega o estado final após a execução (seja nova ou retomada)
        final_state = await brain.aget_state(config)
        
        # Verifica se caiu em um novo ponto de aprovação
        if final_state.next and "arth_approval" in final_state.next:
            return (
                "[⚠️ Ação Crítica] Esta tarefa exige execução de comandos ou agendamentos.\n\n"
                "**Você autoriza o Arth a prosseguir?** (Responda 'Sim' ou 'Ok')"
            )

        # Retorna a última mensagem do assistente
        for m in reversed(final_state.values["messages"]):
            if m.type == "ai":
                return m.content
        
        return "Processo concluído sem resposta textual explícita."
            
    except Exception as e:
        logger.error(f"Erro no execute_brain: {e}", exc_info=True)
        return f"Ops, a Squad Executiva teve uma falha técnica: {str(e)}"

# --- WEBHOOKS (Mantidos sem alteração) ---

@router.post("/whatsapp/webhook")
async def receive_whatsapp(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    if not isinstance(body, dict) or "data" not in body: return {"status": "ignored"}
    data = body.get("data", {})
    message_info = data.get("message", {})
    remote_jid = data.get("key", {}).get("remoteJid", "")
    push_name = data.get("pushName", "Usuário")
    if data.get("key", {}).get("fromMe"): return {"status": "ignored"}
    text = message_info.get("conversation", "") or message_info.get("extendedTextMessage", {}).get("text", "")
    audio_msg = message_info.get("audioMessage")
    media_b64 = data.get("base64")
    async def status_callback(msg: str):
        await send_whatsapp_message(remote_jid, f"_{msg}_")
    async def run_pipeline():
        final_text = text
        if audio_msg and media_b64:
            await status_callback("Ouvindo seu áudio... 🎧⏳")
            temp_path = os.path.join(settings.DATA_OUTPUTS_PATH, f"in_{uuid.uuid4().hex[:8]}.ogg")
            try:
                with open(temp_path, "wb") as f:
                    f.write(base64.b64decode(media_b64))
                transcription = await transcribe_audio_file(temp_path)
                final_text = transcription
                final_text += "\n[SISTEMA: O usuário te enviou a mensagem acima por áudio. Você pode responder com áudio se quiser]."
            except Exception as e:
                logger.error(f"Erro na transcrição: {e}")
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
    if "message" not in body: return {"status": "ignored"}
    msg = body["message"]
    text = msg.get("text", "")
    chat_id = str(msg.get("chat", {}).get("id", ""))
    user_name = msg.get("from", {}).get("first_name", "Usuário")
    if not text or not chat_id: return {"status": "ignored"}
    async def status_callback(msg: str):
        await send_telegram_message(chat_id, f"_{msg}_")
    async def run_pipeline():
        response = await execute_brain(user_id=chat_id, text=text, channel="telegram", status_callback=status_callback, user_name=user_name)
        await process_telegram_reply(chat_id, response)
    background_tasks.add_task(run_pipeline)
    return {"status": "queued"}

@router.get("/instagram/webhook")
async def verify_instagram(mode: str = Query(None, alias="hub.mode"), token: str = Query(None, alias="hub.verify_token"), challenge: str = Query(None, alias="hub.challenge")):
    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN: return int(challenge)
    return "Falha na verificação", 403

@router.post("/instagram/webhook")
async def receive_instagram(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        entry = data.get("entry", [{}])[0]
        messaging = entry.get("messaging", [{}])[0]
        sender_id = messaging.get("sender", {}).get("id", "")
        message = messaging.get("message", {})
        text = message.get("text", "")
        if not text or not sender_id: return {"status": "ignored"}
        async def run_pipeline():
            response = await execute_brain(user_id=sender_id, text=text, channel="instagram", user_name="Usuário Instagram")
            await process_instagram_reply(sender_id, response)
        background_tasks.add_task(run_pipeline)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Erro ao processar webhook Instagram: {e}")
        return {"status": "error"}
