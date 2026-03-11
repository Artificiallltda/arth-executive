from langchain_core.tools import tool

@tool
def get_current_time(timezone: str = "America/Sao_Paulo") -> str:
    """
    Retorna a hora e data atual para o fuso hor\'E1rio fornecido.
    Use esta ferramenta sempre que precisar saber quando uma mensagem foi enviada
    ou para planejar agendamentos.
    """
    import datetime
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(timezone)
    now = datetime.datetime.now(tz)
    return f"A data e hora atual em {timezone} é {now.strftime('%Y-%m-%d %H:%M:%S')}"
