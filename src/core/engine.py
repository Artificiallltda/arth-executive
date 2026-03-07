import logging
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from src.core.graph import build_arth_graph
from src.config import settings

logger = logging.getLogger(__name__)

class ArthEngine:
    """
    Gerenciador do Ciclo de Vida do Grafo (C\u00e9rebro).
    Cuida da persist\u00eancia ass\u00edncrona e compila\u00e7\u00e3o do grafo.
    """
    _instance = None
    _brain = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ArthEngine, cls).__new__(cls)
        return cls._instance

    async def get_brain(self):
        if self._brain is None:
            workflow = build_arth_graph()
            
            # Se j\u00e1 veio compilado (fallback de mem\u00f3ria no graph.py)
            if hasattr(workflow, "astream"):
                self._brain = workflow
                return self._brain

            # Caso contr\u00e1rio, configuramos a persist\u00eancia profissional
            if settings.SUPABASE_DATABASE_URL:
                try:
                    logger.info("[\u2611\uFE0F] Conectando ao Supabase/Postgres para persist\u00eancia...")
                    conn = await AsyncConnection.connect(
                        settings.SUPABASE_DATABASE_URL,
                        autocommit=True,
                        prepare_threshold=None
                    )
                    checkpointer = AsyncPostgresSaver(conn)
                    await checkpointer.setup() # Cria tabelas se necess\u00e1rio
                    
                    self._brain = workflow.compile(
                        checkpointer=checkpointer,
                        interrupt_before=["arth_approval"]
                    )
                except Exception as e:
                    logger.error(f"[\u274C] Falha ao conectar no Postgres: {e}. Usando MemorySaver.")
                    self._brain = workflow.compile(checkpointer=MemorySaver())
            else:
                logger.warning("[!] SUPABASE_DATABASE_URL n\u00e3o configurada. Usando MemorySaver (vol\u00e1til).")
                self._brain = workflow.compile(checkpointer=MemorySaver())
        
        return self._brain

engine = ArthEngine()
