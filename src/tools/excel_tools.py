import pandas as pd
import os
import logging
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from src.config import settings

logger = logging.getLogger(__name__)

@tool
def read_excel(file_path: str, sheet_name: Optional[str] = 0) -> List[Dict[str, Any]]:
    """
    Lê uma planilha Excel e retorna os dados como uma lista de dicionários.
    
    Args:
        file_path (str): Nome do arquivo (ou caminho completo) dentro de DATA_OUTPUTS_PATH.
        sheet_name (str/int): Nome ou índice da aba a ser lida.
    """
    try:
        # Se não for caminho absoluto, assume que está na pasta de outputs
        if not os.path.isabs(file_path):
            file_path = os.path.join(settings.DATA_OUTPUTS_PATH, file_path)
            
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
            
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        # Converte para lista de dicionários para fácil consumo pelos agentes
        data = df.to_dict(orient="records")
        logger.info(f"Sucesso ao ler Excel: {file_path} ({len(data)} linhas)")
        return data
    except Exception as e:
        logger.error(f"Erro ao ler Excel {file_path}: {e}")
        return [{"error": str(e)}]

@tool
def create_excel(data: Any, file_path: str, sheet_name: str = "Sheet1") -> str:
    """
    Cria uma nova planilha Excel (.xlsx) a partir de dados.
    
    Args:
        data (Any): Os dados para a planilha. Pode ser uma lista de dicionários ou uma string JSON contendo a lista.
        file_path (str): Nome do arquivo (ex: 'relatorio-vendas.xlsx').
        sheet_name (str): Nome da aba.
    """
    try:
        import json
        # Se os dados vierem como string (comum em falhas de tool-calling), converte para lista
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                # Se falhar o JSON, tenta limpar possíveis caracteres de escape
                clean_data = data.replace('\\"', '"').replace("\\'", "'")
                data = json.loads(clean_data)

        if not file_path.endswith(".xlsx"):
            file_path += ".xlsx"
            
        full_path = os.path.join(settings.DATA_OUTPUTS_PATH, file_path)
        
        df = pd.DataFrame(data)
        df.to_excel(full_path, index=False, sheet_name=sheet_name)
        
        logger.info(f"Excel criado com sucesso: {full_path}")
        return f"Planilha '{file_path}' criada com sucesso com {len(data)} linhas.\n<SEND_FILE:{file_path}>"
    except Exception as e:
        logger.error(f"Erro ao criar Excel {file_path}: {e}")
        return f"Erro ao criar planilha: {e}. Certifique-se de que os dados estão no formato correto (Lista de Dicionários)."

@tool
def append_to_excel(data: List[Dict[str, Any]], file_path: str, sheet_name: str = "Sheet1") -> str:
    """
    Adiciona novas linhas a uma planilha Excel existente.
    
    Args:
        data (List[Dict]): Lista de novas linhas a adicionar.
        file_path (str): Nome do arquivo existente.
        sheet_name (str): Nome da aba.
    """
    try:
        if not os.path.isabs(file_path):
            full_path = os.path.join(settings.DATA_OUTPUTS_PATH, file_path)
        else:
            full_path = file_path
            
        if not os.path.exists(full_path):
            return create_excel.invoke({"data": data, "file_path": file_path, "sheet_name": sheet_name})
            
        # Carrega existente
        existing_df = pd.read_excel(full_path, sheet_name=sheet_name)
        new_df = pd.DataFrame(data)
        
        # Concatena
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        combined_df.to_excel(full_path, index=False, sheet_name=sheet_name)
        
        logger.info(f"Dados adicionados ao Excel: {full_path}")
        return f"Mais {len(data)} linhas adicionadas à planilha '{os.path.basename(full_path)}'.\n<SEND_FILE:{os.path.basename(full_path)}>"
    except Exception as e:
        logger.error(f"Erro ao atualizar Excel {file_path}: {e}")
        return f"Erro ao atualizar planilha: {e}"
