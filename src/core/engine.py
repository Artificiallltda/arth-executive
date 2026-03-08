import logging
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from src.core.graph import build_arth_graph
from src.config import settings

logger = logging.getLogger(__name__)

class ArthEngine:
    """
    Gerenciador do Ciclo de Vida do Grafo (Cérebro).
    Implementa Singleton e persistência resiliente.
    """
    _instance = None
    _brain = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ArthEngine, cls).__new__(cls)
        return cls._instance

    async def get_brain(self):
        # Health-check: se o pool morreu, reconstrói o brain
        if self._brain is not None and self._pool is not None:
            try:
                async with self._pool.connection() as conn:
                    await conn.execute("SELECT 1")
            except Exception:
                logger.warning("[DB] Pool perdido detectado. Reconstruindo brain com novo pool...")
                self._brain = None
                await self._pool.close()
                self._pool = None

        if self._brain is None:
            workflow = build_arth_graph()

            # Configurações universais de compilação
            compile_kwargs = {
                "interrupt_before": ["arth_approval"]
            }

            # Persistência Cloud (Supabase / Postgres)
            if settings.SUPABASE_DATABASE_URL:
                try:
                    logger.info("[DB] Criando pool de conexões para persistência estável...")
                    if self._pool is None:
                        self._pool = AsyncConnectionPool(
                            conninfo=settings.SUPABASE_DATABASE_URL,
                            max_size=20,
                            kwargs={
                                "autocommit": True,
                                "prepare_threshold": 0,
                            },
                            open=False,
                        )
                        await self._pool.open()

                    checkpointer = AsyncPostgresSaver(self._pool)
                    await checkpointer.setup()
                    compile_kwargs["checkpointer"] = checkpointer
                    logger.info("[OK] Persistência Cloud (Supabase) ativada via pool.")
                except Exception as e:
                    logger.error(f"[FAIL] Erro ao conectar no Supabase: {e}. Usando MemorySaver.")
                    compile_kwargs["checkpointer"] = MemorySaver()
            else:
                logger.warning("[!] SUPABASE_DATABASE_URL não configurada. Usando MemorySaver (volátil).")
                compile_kwargs["checkpointer"] = MemorySaver()

            # Compila o grafo com as configurações de segurança e persistência
            self._brain = workflow.compile(**compile_kwargs)
            logger.info("[OK] Cérebro (Grafo) compilado com sucesso.")

        return self._brain

    async def cleanup(self):
        """Fecha o pool ao encerrar o servidor."""
        if self._pool is not None:
            await self._pool.close()
            logger.info("[DB] Pool de conexões com Supabase encerrado graciosamente.")

engine = ArthEngine()
