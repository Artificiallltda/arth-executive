"""
AGENTE COMPLETO - Railway + Supabase + Gemini
Resolve TODOS os problemas:
  - SSL SYSCALL error / Connection timed out (Supabase)
  - Servidor hibernando (Railway free tier)
  - Lentidão e falta de resposta (Gemini)
  - Múltiplos usuários simultâneos
  - Erros silenciosos sem feedback ao usuário
"""

import os
import asyncio
import time
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, Optional

import google.generativeai as genai

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ── Variáveis de ambiente ──
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL     = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # Flash = mais rápido
DATABASE_URL     = os.getenv("DATABASE_URL", "")                   # URL do Supabase/PostgreSQL
RAILWAY_URL      = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")         # URL pública do Railway
MAX_RETRIES      = 3
RETRY_DELAY      = 2
TIMEOUT_SEG      = 90
KEEPALIVE_MIN    = 8   # Ping a cada 8 minutos (Railway hiberna após 10min)

genai.configure(api_key=GEMINI_API_KEY)


# ══════════════════════════════════════════════════════
# MÓDULO 1 — CONEXÃO SUPABASE COM RECONEXÃO AUTOMÁTICA
# ══════════════════════════════════════════════════════

class ConexaoSupabase:
    """
    Gerencia conexão com Supabase/PostgreSQL de forma robusta.
    Resolve: SSL SYSCALL error, Connection timed out, conexões zumbi.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
        self._lock = asyncio.Lock()

    async def inicializar(self):
        """Cria o pool de conexões com configurações anti-timeout."""
        try:
            import asyncpg

            # Converter URL do Supabase para formato asyncpg
            url = self.database_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgres://", 1)

            self.pool = await asyncpg.create_pool(
                dsn=url,
                min_size=1,
                max_size=10,
                max_inactive_connection_lifetime=300,  # Fecha conexões ociosas após 5min
                command_timeout=30,                    # Timeout por query
                server_settings={
                    "application_name": "agente_ia",
                    "tcp_keepalives_idle": "60",       # Keepalive TCP a cada 60s
                    "tcp_keepalives_interval": "10",
                    "tcp_keepalives_count": "5",
                },
                ssl="require"  # Supabase exige SSL
            )
            log.info("✅ Pool de conexões Supabase inicializado")

        except ImportError:
            log.warning("asyncpg não instalado. Use: pip install asyncpg")
        except Exception as e:
            log.error(f"Erro ao conectar ao Supabase: {e}")

    async def executar(self, query: str, *args, retries: int = 3):
        """
        Executa query com reconexão automática em caso de falha SSL/timeout.
        """
        for tentativa in range(1, retries + 1):
            try:
                async with self.pool.acquire() as conn:
                    # Verifica se a conexão está viva antes de usar
                    await conn.execute("SELECT 1")
                    resultado = await conn.fetch(query, *args)
                    return resultado

            except Exception as e:
                erro = str(e).lower()
                is_conexao = any(k in erro for k in [
                    "ssl syscall", "connection timed out", "connection reset",
                    "broken pipe", "could not receive data", "consuming input"
                ])

                if is_conexao and tentativa < retries:
                    log.warning(f"Erro de conexão Supabase (tentativa {tentativa}): {e}")
                    log.info("Reinicializando pool de conexões...")
                    await self._reinicializar_pool()
                    await asyncio.sleep(RETRY_DELAY * tentativa)
                else:
                    log.error(f"Erro no Supabase após {tentativa} tentativas: {e}")
                    raise

    async def _reinicializar_pool(self):
        """Fecha e recria o pool de conexões."""
        async with self._lock:
            try:
                if self.pool:
                    await self.pool.close()
                await self.inicializar()
            except Exception as e:
                log.error(f"Erro ao reinicializar pool: {e}")

    async def keepalive(self):
        """Mantém conexão viva com queries periódicas."""
        while True:
            try:
                await asyncio.sleep(KEEPALIVE_MIN * 60)
                async with self.pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                log.info("🔄 Keepalive Supabase: conexão ativa")
            except Exception as e:
                log.warning(f"Keepalive falhou, reconectando: {e}")
                await self._reinicializar_pool()

    async def fechar(self):
        if self.pool:
            await self.pool.close()
            log.info("Pool de conexões fechado")


# ══════════════════════════════════════════════════════
# MÓDULO 2 — GEMINI COM RETRY + STREAMING
# ══════════════════════════════════════════════════════

async def responder_streaming(
    mensagem: str,
    system_prompt: str = "Você é um assistente inteligente e prestativo.",
    historico: list = None
) -> AsyncGenerator[str, None]:
    """
    Resposta em streaming com retry automático.
    O texto vai chegando aos poucos — sensação de velocidade.
    """
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.7,
            max_output_tokens=2048,
        )
    )
    chat = model.start_chat(history=historico or [])

    for tentativa in range(1, MAX_RETRIES + 1):
        try:
            log.info(f"Gemini streaming (tentativa {tentativa})")
            response = await asyncio.wait_for(
                asyncio.to_thread(lambda: chat.send_message(mensagem, stream=True)),
                timeout=TIMEOUT_SEG
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
            return

        except asyncio.TimeoutError:
            log.warning(f"Timeout Gemini (tentativa {tentativa})")
            if tentativa < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
            else:
                yield "\n\n⚠️ Tempo de resposta esgotado. Tente novamente."

        except Exception as e:
            log.error(f"Erro Gemini (tentativa {tentativa}): {type(e).__name__}: {e}")
            if tentativa < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * tentativa)
            else:
                yield "\n\n⚠️ Erro ao processar. Tente novamente em instantes."


async def responder_completo(
    mensagem: str,
    system_prompt: str = "Você é um assistente inteligente e prestativo.",
    historico: list = None
) -> str:
    """Resposta completa com retry. Retorna string final."""
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(temperature=0.7, max_output_tokens=2048)
    )
    chat = model.start_chat(history=historico or [])

    for tentativa in range(1, MAX_RETRIES + 1):
        try:
            inicio = time.time()
            response = await asyncio.wait_for(
                asyncio.to_thread(lambda: chat.send_message(mensagem)),
                timeout=TIMEOUT_SEG
            )
            log.info(f"Gemini respondeu em {time.time()-inicio:.2f}s")
            return response.text

        except asyncio.TimeoutError:
            log.warning(f"Timeout Gemini (tentativa {tentativa})")
            if tentativa < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
        except Exception as e:
            log.error(f"Erro Gemini (tentativa {tentativa}): {e}")
            if tentativa < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * tentativa)

    return "⚠️ Não consegui processar sua mensagem agora. Tente novamente em instantes."


# ══════════════════════════════════════════════════════
# MÓDULO 3 — AGENTE PRINCIPAL (Telegram/WhatsApp)
# ══════════════════════════════════════════════════════

class AgenteIA:
    """
    Agente completo com:
    - Resposta imediata ao usuário
    - Streaming de resposta
    - Histórico por usuário
    - Fila para múltiplos usuários
    - Integração robusta com Supabase
    """

    def __init__(self, system_prompt: str, db: ConexaoSupabase = None):
        self.system_prompt = system_prompt
        self.db = db
        self.historicos = {}       # {user_id: [mensagens]}
        self.fila = asyncio.Queue()
        self._workers_ativos = False

    async def iniciar(self, num_workers: int = 5):
        """Inicia os workers de processamento."""
        self._workers_ativos = True
        workers = [asyncio.create_task(self._worker(i)) for i in range(num_workers)]
        log.info(f"✅ {num_workers} workers iniciados")
        return workers

    async def receber_mensagem(
        self,
        user_id: str,
        mensagem: str,
        enviar_fn: Callable,
        editar_fn: Callable = None
    ):
        """
        Ponto de entrada: recebe mensagem e coloca na fila.
        Envia resposta imediata para o usuário não ficar no vácuo.
        """
        # Resposta imediata — NUNCA deixa o usuário esperando em silêncio
        msg_id = await enviar_fn(user_id, "⏳ Processando sua mensagem...")
        log.info(f"📨 Mensagem recebida de {user_id}: {mensagem[:50]}...")

        await self.fila.put({
            "user_id": user_id,
            "mensagem": mensagem,
            "msg_id": msg_id,
            "enviar_fn": enviar_fn,
            "editar_fn": editar_fn,
        })

    async def _worker(self, worker_id: int):
        """Worker que processa mensagens da fila."""
        while self._workers_ativos:
            try:
                item = await asyncio.wait_for(self.fila.get(), timeout=1.0)
                user_id   = item["user_id"]
                mensagem  = item["mensagem"]
                msg_id    = item["msg_id"]
                enviar_fn = item["enviar_fn"]
                editar_fn = item["editar_fn"]

                log.info(f"Worker {worker_id} processando {user_id}")
                historico = self.historicos.get(user_id, [])

                resposta_completa = ""

                if editar_fn:
                    # Streaming: edita a mensagem aos poucos
                    ultimo_update = time.time()
                    async for chunk in responder_streaming(mensagem, self.system_prompt, historico):
                        resposta_completa += chunk
                        if time.time() - ultimo_update > 0.5:
                            try:
                                await editar_fn(user_id, msg_id, resposta_completa + " ▌")
                                ultimo_update = time.time()
                            except Exception:
                                pass
                    # Atualização final sem cursor
                    try:
                        await editar_fn(user_id, msg_id, resposta_completa)
                    except Exception:
                        await enviar_fn(user_id, resposta_completa)
                else:
                    # Sem streaming: gera tudo e envia
                    resposta_completa = await responder_completo(mensagem, self.system_prompt, historico)
                    await enviar_fn(user_id, resposta_completa)

                # Salvar histórico (máx 20 mensagens = 10 trocas)
                self.historicos[user_id] = (historico + [
                    {"role": "user",  "parts": [mensagem]},
                    {"role": "model", "parts": [resposta_completa]},
                ])[-20:]

                # Salvar no Supabase (se disponível)
                if self.db and self.db.pool:
                    try:
                        await self.db.executar(
                            "INSERT INTO mensagens (user_id, mensagem, resposta, criado_em) VALUES ($1, $2, $3, NOW())",
                            user_id, mensagem, resposta_completa
                        )
                    except Exception as e:
                        log.warning(f"Erro ao salvar no Supabase: {e}")

                self.fila.task_done()
                log.info(f"✅ Worker {worker_id} concluiu {user_id}")

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log.error(f"Worker {worker_id} erro crítico: {e}")


# ══════════════════════════════════════════════════════
# MÓDULO 4 — KEEP-ALIVE RAILWAY
# ══════════════════════════════════════════════════════

async def keepalive_railway(url: str = None):
    """
    Faz ping no próprio servidor a cada 8 minutos.
    Railway hiberna após 10 minutos de inatividade no plano gratuito.
    """
    if not url:
        url = f"https://{RAILWAY_URL}/health" if RAILWAY_URL else None

    if not url:
        log.warning("RAILWAY_PUBLIC_DOMAIN não configurado. Keep-alive desativado.")
        return

    import aiohttp
    while True:
        await asyncio.sleep(KEEPALIVE_MIN * 60)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    log.info(f"🔄 Keep-alive Railway: {r.status}")
        except Exception as e:
            log.warning(f"Keep-alive falhou: {e}")


# ══════════════════════════════════════════════════════
# MÓDULO 5 — INICIALIZAÇÃO COMPLETA
# ══════════════════════════════════════════════════════

async def inicializar_sistema(system_prompt: str) -> AgenteIA:
    """
    Inicializa todos os módulos do sistema de forma segura.
    Chame isso no startup da sua aplicação (FastAPI, Flask, etc.)
    """
    log.info("🚀 Inicializando sistema...")

    # Banco de dados
    db = None
    if DATABASE_URL:
        db = ConexaoSupabase(DATABASE_URL)
        await db.inicializar()
        asyncio.create_task(db.keepalive())
        log.info("✅ Supabase conectado com keepalive ativo")
    else:
        log.warning("DATABASE_URL não configurado. Supabase desativado.")

    # Agente
    agente = AgenteIA(system_prompt=system_prompt, db=db)
    await agente.iniciar(num_workers=5)

    # Keep-alive Railway
    asyncio.create_task(keepalive_railway())

    log.info("✅ Sistema completamente inicializado")
    return agente


# ══════════════════════════════════════════════════════
# EXEMPLO DE USO COM FASTAPI
# ══════════════════════════════════════════════════════

"""
from fastapi import FastAPI

app = FastAPI()
agente: AgenteIA = None

@app.on_event("startup")
async def startup():
    global agente
    agente = await inicializar_sistema(
        system_prompt="Você é um assistente especializado em gastronomia e IA."
    )

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/mensagem")
async def receber(user_id: str, mensagem: str):
    respostas = []

    async def enviar(uid, texto):
        respostas.append(texto)
        return len(respostas) - 1

    await agente.receber_mensagem(user_id, mensagem, enviar_fn=enviar)
    await asyncio.sleep(0.1)  # Aguarda processamento
    return {"resposta": respostas[-1] if respostas else "Processando..."}
"""


# ══════════════════════════════════════════════════════
# TESTE LOCAL
# ══════════════════════════════════════════════════════

async def _teste():
    print("🤖 Testando sistema completo...\n")

    respostas = []
    async def mock_enviar(uid, texto):
        print(f"[ENVIAR] {uid}: {texto}")
        respostas.append(texto)
        return len(respostas) - 1

    async def mock_editar(uid, msg_id, texto):
        print(f"\r[STREAMING] {texto[-80:]}", end="", flush=True)

    agente = await inicializar_sistema("Você é um assistente de testes.")

    await agente.receber_mensagem(
        user_id="user_123",
        mensagem="O que é inteligência artificial? Responda em 2 linhas.",
        enviar_fn=mock_enviar,
        editar_fn=mock_editar
    )

    await asyncio.sleep(15)
    print("\n\n✅ Teste concluído!")

if __name__ == "__main__":
    asyncio.run(_teste())
