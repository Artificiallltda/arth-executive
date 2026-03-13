import asyncio
import time
import logging
import os
from core.graph import build_arth_graph
from langchain_core.messages import HumanMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_graph():
    graph = build_arth_graph()
    graph_runnable = graph.compile()
    
    start_time = time.time()
    logger.info("Starting graph execution...")
    
    initial_state = {
        "messages": [HumanMessage(content="Gere um relatorio de teste basico em PDF de 2 linhas sobre mercado.")],
        "user_id": "test_local",
        "channel": "terminal"
    }

    try:
        async for event in graph_runnable.astream(initial_state, config={"configurable": {"thread_id": "test_123"}}):
            for node, state in event.items():
                logger.info(f"Node finished: {node} - Time elapsed: {time.time() - start_time:.2f}s")
                if "messages" in state and state["messages"]:
                    last_msg = state["messages"][-1]
                    logger.info(f"  [{last_msg.type}] {getattr(last_msg, 'name', 'user')}: {str(last_msg.content)[:100]}...")
    except Exception as e:
        logger.error(f"Error during graph execution: {e}", exc_info=True)

    logger.info(f"Total time: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    asyncio.run(test_graph())
