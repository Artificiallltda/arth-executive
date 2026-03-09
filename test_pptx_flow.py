import asyncio
import os
import sys
import logging
import re

# Configuração de log
logging.basicConfig(level=logging.INFO)
sys.path.append(os.getcwd())

from src.router.message_handler import execute_brain

async def main():
    print("\n🚀 INICIANDO TESTE DE FLUXO PPTX + IMAGENS...")
    print("Alvo: Verificar correção do NameError 're' e ocultação de imagens avulsas.")
    
    # Prompt focado em imagens e PPTX
    prompt = "Gere um PPTX de 2 slides sobre 'Inteligência Artificial' com uma imagem em cada slide. Use o Manus AI Style."
    user_id = "test-pptx-user"
    
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
        
        # Validação
        has_pptx = ".pptx>" in response
        image_tags = re.findall(r'<SEND_FILE:img-[^>]+\.png>', response)
        
        print("\n📊 RESULTADOS DO TESTE:")
        print(f"✅ Arquivo PPTX detectado: {has_pptx}")
        print(f"✅ Tags de imagem na resposta final: {len(image_tags)} (Esperado: 0)")
        
        if has_pptx and len(image_tags) == 0:
            print("\n✨ SUCESSO: O erro de 're' foi resolvido e as imagens estão embutidas (ocultas na resposta).")
        else:
            print("\n⚠️ ALERTA: Verifique se as imagens ainda estão vazando ou se o PPTX falhou.")
            
    except Exception as e:
        print(f"❌ Erro crítico no teste: {e}")

if __name__ == "__main__":
    asyncio.run(main())
