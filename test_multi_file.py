import asyncio
import os
import sys
import logging

# Configuração básica de log para o teste
logging.basicConfig(level=logging.INFO)

# Adiciona o diretório atual ao sys.path para importar os módulos locais
sys.path.append(os.getcwd())

from router.message_handler import execute_brain
from config import settings

async def main():
    print("\n🚀 INICIANDO TESTE DE GERAÇÃO MÚLTIPLA (DOCX + PDF)...")
    print("Alvo: Validar resiliência de tags e evitar duplicidade de mensagens.")
    
    # Prompt que costumava causar o bug
    prompt = "Gere um breve arquivo DOCX e um arquivo PDF sobre 'O Futuro da IA em 2026'. Use o Manus AI Style."
    user_id = "test-user-123"
    
    async def mock_status(msg):
        print(f"⏳ [STATUS] {msg}")

    try:
        # Executa o cérebro do Arth
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
        
        # Validação simples
        has_docx = ".docx>" in response
        has_pdf = ".pdf>" in response
        has_duplicate = response.count("📄") > 1 # O título costuma começar com esse emoji no template
        
        print("\n📊 RESULTADOS DO TESTE:")
        print(f"✅ Arquivo DOCX detectado: {has_docx}")
        print(f"✅ Arquivo PDF detectado: {has_pdf}")
        print(f"✅ Duplicidade de cabeçalho: {'Detectada (FALHA)' if has_duplicate else 'Não detectada (SUCESSO)'}")
        
    except Exception as e:
        print(f"❌ Erro durante o teste: {e}")

if __name__ == "__main__":
    asyncio.run(main())
