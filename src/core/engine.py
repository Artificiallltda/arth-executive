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
            
            # Configurações universais de compilação
            compile_kwargs = {
                "interrupt_before": ["arth_approval"]
            }

            # Persistência Cloud (Supabase / Postgres)
            if settings.SUPABASE_DATABASE_URL:
                try:
                    logger.info("[DB] Conectando ao Banco de Dados para persistência estável...")
                    if self._conn is None or (hasattr(self._conn, 'closed') and self._conn.closed):
                        self._conn = await AsyncConnection.connect(
                            settings.SUPABASE_DATABASE_URL,
                            autocommit=True,
                            prepare_threshold=None
                        )
                    
                    checkpointer = AsyncPostgresSaver(self._conn)
                    await checkpointer.setup()
                    compile_kwargs["checkpointer"] = checkpointer
                    logger.info("[OK] Persistência Cloud (Supabase) ativada.")
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
        """Fecha conexões ao encerrar o servidor."""
        if self._conn is not None:
             if not getattr(self._conn, 'closed', True):
                await self._conn.close()
                logger.info("[DB] Conexão com Supabase encerrada graciosamente.")

engine = ArthEngine()
