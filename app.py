import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.router.message_handler import router as message_router
from src.scheduler.reminder_worker import scheduler, load_pending_reminders
from src.core.engine import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[SERVER] Iniciando Arth Executive AI...")
    scheduler.start()
    load_pending_reminders()
    yield
    # Shutdown
    print("[SERVER] Encerrando conexões graciosamente...")
    await engine.cleanup()
    scheduler.shutdown()

app = FastAPI(title="Arth Executive AI", version="0.1.0", lifespan=lifespan)

app.include_router(message_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Arth Executive AI is running"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
