import asyncio
import os
import sys
import logging

# Adiciona o diretório atual ao sys.path
sys.path.append(os.getcwd())

from router.message_handler import execute_brain

async def main():
    logging.basicConfig(level=logging.INFO)
    print("\n🚀 TESTANDO CÉREBRO COMPLETO: PESQUISA WEB")
    print("Alvo: Verificar se o Orquestrador chama o Pesquisador e se ele usa a ferramenta.")
    
    # Pergunta que OBRIGA a pesquisa
    prompt = "Quais são as 3 principais notícias de economia no Brasil HOJE?"
    user_id = "test-search-brain"
    
    async def mock_status(msg):
        print(f"⏳ [STATUS] {msg}")

    try:
        response = await execute_brain(
            user_id=user_id,
            text=prompt,
            channel="telegram",
            status_callback=mock_status,
            user_name="Gean Teste"
        )
        
        print("\n" + "="*50)
        print("📥 RESPOSTA FINAL DO SISTEMA:")
        print("="*50)
        print(response)
        print("="*50)
        
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    asyncio.run(main())
