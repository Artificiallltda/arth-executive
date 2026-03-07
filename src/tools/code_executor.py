from langchain_core.tools import tool
import asyncio
import os
import uuid
from src.config import settings

@tool
async def execute_python_code(code: str) -> str:
    """
    Executa c\u00f3digo Python em um subprocesso isolado e retorna o resultado (stdout/stderr).
    
    Regras de Seguran\u00e7a: 
    - Bloqueia imports perigosos (os, subprocess, shutil, pickle, etc).
    - Limite de tempo de 30 segundos.
    """
    # Lista negra de seguran\u00e7a expandida
    blacklist = ["os.", "subprocess.", "shutil.", "pickle.", "socket.", "sys.", "eval(", "exec(", "__import__", "open(", "__builtins__"]
    for blocked in blacklist:
        if blocked in code:
            return f"ERRO DE SEGURAN\u00c7A: O uso do m\u00f3dulo ou fun\u00e7\u00e3o '{blocked}' n\u00e3o \u00e9 permitido."

    try:
        # Usa pasta tempor\u00e1ria configurada ou baseada no BASE_DIR
        temp_dir = os.path.join(settings.BASE_DIR, "data", "temp_scripts")
        os.makedirs(temp_dir, exist_ok=True)
        
        filename = f"script_{uuid.uuid4().hex[:8]}.py"
        filepath = os.path.join(temp_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
            
        # Executa de forma ass\u00edncrona para n\u00e3o travar o servidor
        process = await asyncio.create_subprocess_exec(
            "python", filepath,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            
            output = stdout.decode().strip()
            error = stderr.decode().strip()
            
            final_res = output
            if error:
                final_res += f"\nErros/Avisos:\n{error}"
                
            return final_res if final_res else "Script executado com sucesso (sem sa\u00edda)."
            
        except asyncio.TimeoutExpired:
            process.kill()
            return "Erro: A execu\u00e7\u00e3o excedeu o tempo limite de 30 segundos."
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
            
    except Exception as e:
        return f"Erro ao executar o c\u00f3digo: {str(e)}"
