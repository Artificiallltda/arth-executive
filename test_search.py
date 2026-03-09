import asyncio
import os
import sys
import logging

# Adiciona o diretório atual ao sys.path
sys.path.append(os.getcwd())

from src.tools.web_search import search_web

async def main():
    logging.basicConfig(level=logging.INFO)
    print("🚀 TESTANDO FERRAMENTA DE PESQUISA WEB (DDG)...")
    
    query = "Notícias sobre Inteligência Artificial hoje"
    print(f"🔍 Buscando por: '{query}'")
    
    result = await search_web.ainvoke({"query": query})
    
    print("\n" + "="*50)
    print("🌐 RESULTADO DA PESQUISA:")
    print("="*50)
    print(result[:1000] + "..." if len(result) > 1000 else result)
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
