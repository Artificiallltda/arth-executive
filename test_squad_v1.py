import asyncio
import sys
import io

# For\u00e7ar UTF-8 para o console do Windows n\u00e3o quebrar com emojis
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from router.message_handler import execute_brain

async def status_callback(msg: str):
    print(f">> ETA STATUS: {msg}")

async def test_squad():
    prompt = "Pesquise o clima em SP para amanhã, gere um relatório DOCX e analise os dados históricos da última semana."
    print(f"=================================================")
    print(f"=== INICIANDO TESTE DO AGENTIC SWARM SQUAD V1 ===")
    print(f"=================================================")
    print(f"PROMPT: {prompt}\n")
    
    response = await execute_brain(
        user_id="test_squad_001",
        text=prompt,
        channel="cli_test",
        status_callback=status_callback,
        user_name="Gean"
    )
    
    print("\n=================================================")
    print("=== RESPOSTA FINAL DO ORQUESTRADOR ===")
    print("=================================================")
    print(response)

if __name__ == "__main__":
    asyncio.run(test_squad())
