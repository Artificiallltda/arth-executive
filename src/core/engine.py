import logging
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
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
    _conn = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ArthEngine, cls).__new__(cls)
        return cls._instance

    async def get_brain(self):
        if self._brain is None:
            workflow = build_arth_graph()
            
            # Persistência Profissional (Supabase / Postgres)
            if settings.SUPABASE_DATABASE_URL:
                try:
                    logger.info("[DB] Conectando ao Supabase para persistência estável...")
                    # Mantemos uma conexão persistente para evitar erros de ResourceWarning
                    if self._conn is None or self._conn.closed:
                        self._conn = await AsyncConnection.connect(
                            settings.SUPABASE_DATABASE_URL,
                            autocommit=True,
                            prepare_threshold=None
                        )
                    
                    checkpointer = AsyncPostgresSaver(self._conn)
                    await checkpointer.setup()
                    
                    self._brain = workflow.compile(
                        checkpointer=checkpointer,
                        interrupt_before=["arth_approval"]
                    )
                    logger.info("[OK] Cérebro compilado com Persistência Cloud.")
                except Exception as e:
                    logger.error(f"[FAIL] Erro no Supabase: {e}. Usando memória local.")
                    self._brain = workflow.compile(checkpointer=MemorySaver())
            else:
                logger.warning("[!] Usando MemorySaver (volátil).")
                self._brain = workflow.compile(checkpointer=MemorySaver())
        
        return self._brain

    async def cleanup(self):
        """Fecha conexões ao encerrar o servidor."""
        if self._conn and not self._conn.closed:
            await self._conn.close()
            logger.info("[DB] Conexão com Supabase encerrada graciosamente.")

engine = ArthEngine()
