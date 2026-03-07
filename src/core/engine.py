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
    Cuida da persistência assíncrona e compilação do grafo.
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
            
            # Se já veio compilado (fallback de memória no graph.py)
            if hasattr(workflow, "astream"):
                self._brain = workflow
                return self._brain

            # Configurações padrão de compilação (HITL Ativado)
            compile_kwargs = {
                "interrupt_before": ["arth_approval"]
            }

            # Caso contrário, configuramos a persistência profissional
            if settings.SUPABASE_DATABASE_URL:
                try:
                    logger.info("[☑️] Conectando ao Supabase/Postgres para persistência...")
                    conn = await AsyncConnection.connect(
                        settings.SUPABASE_DATABASE_URL,
                        autocommit=True,
                        prepare_threshold=None
                    )
                    checkpointer = AsyncPostgresSaver(conn)
                    await checkpointer.setup() # Cria tabelas se necessário
                    compile_kwargs["checkpointer"] = checkpointer
                except Exception as e:
                    logger.error(f"[❌] Falha ao conectar no Postgres: {e}. Usando MemorySaver.")
                    compile_kwargs["checkpointer"] = MemorySaver()
            else:
                logger.warning("[!] SUPABASE_DATABASE_URL não configurada. Usando MemorySaver (volátil).")
                compile_kwargs["checkpointer"] = MemorySaver()
            
            # Compila com as configurações definidas
            self._brain = workflow.compile(**compile_kwargs)
        
        return self._brain

engine = ArthEngine()
