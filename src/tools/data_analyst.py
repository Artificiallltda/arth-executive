import os
import uuid
import pandas as pd
import matplotlib.pyplot as plt
from langchain_core.tools import tool
import io
import contextlib
import asyncio
from src.config import settings

@tool
async def analyze_data_file(instruction: str, data_string: str) -> str:
    """
    Analisa dados como um Cientista de Dados e gera gr\u00e1ficos ou estat\u00edsticas.
    
    O script DEVE:
    1. Trabalhar com a vari\u00e1vel preexistente chamada `df`.
    2. Usar o matplotlib para gerar um gr\u00e1fico (se necess\u00e1rio) e salv\u00e1-lo 
       no caminho indicado pela vari\u00e1vel global `output_path`.
    3. Imprimir dados \u00fateis no console (usando print).
    """
    try:
        filename = f"{uuid.uuid4().hex[:8]}_grafico_analise.png"
        filepath = os.path.join(settings.DATA_OUTPUTS_PATH, filename)
        
        # Converter string em DataFrame
        try:
            df = pd.read_csv(io.StringIO(data_string))
        except Exception as e1:
            try:
                df = pd.read_json(io.StringIO(data_string))
            except Exception as e2:
                return f"Erro: Dados inv\u00e1lidos. (CSV: {e1}, JSON: {e2})"
            
        if df is None or df.empty:
            return "Erro: O conjunto de dados fornecido est\u00e1 vazio."

        # Executar o c\u00f3digo em um ambiente restrito
        safe_builtins = {
            "print": print, "len": len, "range": range, "enumerate": enumerate,
            "zip": zip, "list": list, "dict": dict, "str": str, "int": int,
            "float": float, "bool": bool, "round": round, "sum": sum,
            "min": min, "max": max, "abs": abs, "sorted": sorted, "type": type,
        }
        local_scope = {'df': df, 'pd': pd, 'plt': plt, 'output_path': filepath}
        output_buffer = io.StringIO()

        # Como o exec \u00e9 s\u00edncrono, rodamos no executor de thread para n\u00e3o travar o loop de eventos
        def _execute_analysis():
            with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
                exec(instruction, {"__builtins__": safe_builtins}, local_scope)

        await asyncio.to_thread(_execute_analysis)
        
        console_output = output_buffer.getvalue()
        
        if os.path.exists(filepath):
            return (
                f"An\u00e1lise conclu\u00edda com \u00eaxito!\n\n"
                f"Sa\u00edda Estat\u00edstica:\n{console_output}\n\n"
                f"Tag de Envio: <SEND_FILE:{filename}>"
            )
        else:
            return f"An\u00e1lise conclu\u00edda (sem gr\u00e1fico).\n\nSa\u00edda:\n{console_output}"
            
    except Exception as e:
        return f"Erro na Skill de An\u00e1lise: {str(e)}"
