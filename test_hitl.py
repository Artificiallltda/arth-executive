import asyncio
from router.message_handler import execute_brain

async def status_callback(msg: str):
    print(f">> ETA STATUS: {msg}")

async def test_hitl():
    import uuid
    user_id = f"test_hitl_{uuid.uuid4().hex[:6]}"
    
    # 1. Trigger HITL
    prompt1 = "Execute este c\u00f3digo Python: print('Oi do Arth')"
    print(f"\n[PASSO 1] Enviando prompt cr\u00edtico: {prompt1}")
    
    response1 = await execute_brain(
        user_id=user_id,
        text=prompt1,
        channel="cli_test",
        status_callback=status_callback,
        user_name="Gean"
    )
    
    print(f"\nRESPOSTA 1 (Esperado: Pedido de Aprova\u00e7\u00e3o):\n{response1}")
    
    if "autoriza o Arth a prosseguir?" in response1:
        print("\n[OK] Interrup\u00e7\u00e3o detectada com sucesso!")
        
        # 2. Approve
        prompt2 = "Sim, pode prosseguir."
        print(f"\n[PASSO 2] Enviando aprova\u00e7\u00e3o: {prompt2}")
        
        response2 = await execute_brain(
            user_id=user_id,
            text=prompt2,
            channel="cli_test",
            status_callback=status_callback,
            user_name="Gean"
        )
        
        print(f"\nRESPOSTA 2 (Esperado: Execu\u00e7\u00e3o conclu\u00edda):\n{response2}")
    else:
        print("\n[ERRO] O sistema n\u00e3o parou para aprova\u00e7\u00e3o.")

if __name__ == "__main__":
    asyncio.run(test_hitl())
