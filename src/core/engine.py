import logging
import asyncio
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from src.core.graph import build_arth_graph
from src.config import settings

logger = logging.getLogger(__name__)

class ArthEngine:
    """
    Gerenciador do Ciclo de Vida do Grafo (Cérebro).
    Implementa Singleton e persistência resiliente com blindagem Supabase.
    """
    _instance = None
    _brain = None
    _pool = None
    _keepalive_task = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ArthEngine, cls).__new__(cls)
        return cls._instance

    async def get_brain(self):
        """Retorna a instância do cérebro (grafo) com pool validado."""
        # 1. Health-check: Validação agressiva do pool (Anti SSL SYSCALL)
        if self._brain is not None and self._pool is not None:
            try:
                # Tenta uma operação rápida para validar a conexão
                async with self._pool.connection(timeout=5) as conn:
                    await conn.execute("SELECT 1")
            except Exception as e:
                erro = str(e).lower()
                is_fatal = any(k in erro for k in [
                    "ssl syscall", "connection timed out", "connection reset",
                    "broken pipe", "could not receive data", "consuming input"
                ])
                if is_fatal:
                    logger.warning(f"[DB] Erro crítico de conexão detectado ({erro}). Reinicializando pool...")
                    await self.cleanup()
                    self._brain = None
                else:
                    logger.error(f"[DB] Erro de validação não fatal: {e}")

        # 2. Inicialização / Reconstrução
        if self._brain is None:
            workflow = build_arth_graph()
            compile_kwargs = {}

            if settings.SUPABASE_DATABASE_URL:
                try:
                    logger.info("[DB] Inicializando pool robusto com Supabase...")
                    
                    # Configurações de Keepalive TCP e Pool conforme Guia Manus AI
                    if self._pool is None:
                        self._pool = AsyncConnectionPool(
                            conninfo=settings.SUPABASE_DATABASE_URL,
                            min_size=1,
                            max_size=10,
                            kwargs={
                                "autocommit": True,
                                "prepare_threshold": None,
                                "tcp_keepalives_idle": 60,
                                "tcp_keepalives_interval": 10,
                                "tcp_keepalives_count": 5,
                                "sslmode": "require"
                            },
                            open=False,
                        )
                        await self._pool.open()

                    checkpointer = AsyncPostgresSaver(self._pool)
                    await checkpointer.setup()
                    compile_kwargs["checkpointer"] = checkpointer
                    
                    # Inicia Keepalive em background se não houver
                    if self._keepalive_task is None or self._keepalive_task.done():
                        self._keepalive_task = asyncio.create_task(self._db_keepalive())
                        
                    logger.info("[OK] Persistência Cloud (Supabase) blindada.")
                except Exception as e:
                    logger.error(f"[FAIL] Falha crítica no Supabase: {e}. Usando MemorySaver.")
                    compile_kwargs["checkpointer"] = MemorySaver()
            else:
                logger.warning("[!] DATABASE_URL não configurada. Usando MemorySaver.")
                compile_kwargs["checkpointer"] = MemorySaver()

            self._brain = workflow.compile(**compile_kwargs)
            logger.info("[OK] Cérebro compilado com sucesso.")

        return self._brain

    async def _db_keepalive(self):
        """Mantém a conexão com o Supabase viva (SELECT 1 a cada 5 min)."""
        while True:
            try:
                await asyncio.sleep(300) # 5 minutos
                if self._pool:
                    async with self._pool.connection() as conn:
                        await conn.execute("SELECT 1")
                    logger.debug("[DB] Keepalive Supabase: Conexão ativa.")
            except Exception as e:
                logger.warning(f"[DB] Keepalive falhou: {e}. O pool será renovado na próxima requisição.")

    async def cleanup(self):
        """Encerra conexões graciosamente."""
        if self._keepalive_task:
            self._keepalive_task.cancel()
            self._keepalive_task = None
        if self._pool is not None:
            try:
                await self._pool.close()
            except: pass
            self._pool = None
            logger.info("[DB] Pool de conexões encerrado.")

engine = ArthEngine()
