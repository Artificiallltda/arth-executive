import logging
import uvicorn
import sys
import os
import asyncio
import httpx
from fastapi import FastAPI, Query
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager

# INJEÇÃO DE PATH
current_dir = os.path.dirname(os.path.abspath(__file__))
if "src" not in sys.path:
    sys.path.append(os.path.join(current_dir, "src"))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from src.router.message_handler import router as message_router
from src.scheduler.reminder_worker import scheduler, load_pending_reminders
from src.core.engine import engine
from src.utils.log_buffer import setup_log_buffer, get_logs_json, get_logs_text
from src.config import settings

# ─── Logging Config ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
setup_log_buffer(root_level=logging.DEBUG)
logger = logging.getLogger(__name__)

def verificar_templates():
    """Confere se os templates persistentes estão disponíveis no repositório."""
    base = os.path.dirname(os.path.abspath(__file__))
    pasta = os.path.join(base, "data", "templates")
    if not os.path.exists(pasta):
        logger.error(f"⚠️ AVISO CRÍTICO: Pasta {pasta} não encontrada!")
        return False
    
    total = 0
    for root, dirs, files in os.walk(pasta):
        total += len([f for f in files if f.endswith(('.pptx', '.docx'))])
    
    if total == 0:
        logger.warning(f"⚠️ AVISO: Nenhum template (.pptx/.docx) encontrado em {pasta}")
    else:
        logger.info(f"✅ TEMPLATES PERSISTENTES: {total} arquivos encontrados em {pasta}")
    return True

async def keepalive_railway():
    """Ping no próprio servidor para evitar hibernação."""
    public_url = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if not public_url: return
    url = f"https://{public_url}/health"
    async with httpx.AsyncClient() as client:
        while True:
            await asyncio.sleep(480)
            try: await client.get(url, timeout=10)
            except: pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[SERVER] Iniciando Arth Executive AI (Elite v3.2)...")
    
    # Validação de Templates (Manus AI Rule)
    verificar_templates()
    
    # Serviços de background
    scheduler.start()
    load_pending_reminders()
    asyncio.create_task(keepalive_railway())
    
    yield
    
    logger.info("[SERVER] Encerrando conexões...")
    await engine.cleanup()
    scheduler.shutdown()

app = FastAPI(title="Arth Executive AI", version="0.3.2", lifespan=lifespan)

app.include_router(message_router, prefix="/api/v1")

@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok", "templates_ready": verificar_templates()}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
