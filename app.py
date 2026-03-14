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

async def keepalive_railway():
    """Ping no próprio servidor a cada 8 minutos para evitar hibernação."""
    public_url = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if not public_url:
        logger.warning("[INFRA] RAILWAY_PUBLIC_DOMAIN não configurado. Keep-alive desativado.")
        return

    url = f"https://{public_url}/health"
    logger.info(f"[INFRA] Iniciando keep-alive para {url}")
    
    async with httpx.AsyncClient() as client:
        while True:
            await asyncio.sleep(480) # 8 minutos
            try:
                response = await client.get(url, timeout=10)
                logger.info(f"[INFRA] Keep-alive Railway: {response.status_code}")
            except Exception as e:
                logger.warning(f"[INFRA] Keep-alive falhou: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[SERVER] Iniciando Arth Executive AI (Modo Blindado v3)...")
    
    # Inicia serviços de background
    scheduler.start()
    load_pending_reminders()
    
    # Inicia keep-alive do Railway
    asyncio.create_task(keepalive_railway())
    
    yield
    
    logger.info("[SERVER] Encerrando conexões graciosamente...")
    await engine.cleanup()
    scheduler.shutdown()

app = FastAPI(title="Arth Executive AI - Auditoria Orion", version="0.3.0", lifespan=lifespan)

@app.middleware("http")
async def monitor_infra(request, call_next):
    # Log simplificado de requisição
    return await call_next(request)

app.include_router(message_router, prefix="/api/v1")

@app.get("/")
@app.get("/health")
async def health():
    """Rota de saúde usada pelo monitoramento e keep-alive."""
    return {"status": "ok", "service": "Arth Executive AI", "version": "0.3.0"}

@app.get("/api/v1/logs", response_class=PlainTextResponse)
async def view_logs(
    n: int = Query(default=60, description="Número de entradas"),
    level: str = Query(default=None, description="Filtro"),
    fmt: str = Query(default="text", description="Formato"),
):
    if fmt == "json":
        from fastapi.responses import JSONResponse
        return JSONResponse(content=get_logs_json(n=n, level=level))
    return get_logs_text(n=min(n, 100))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
