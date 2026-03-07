import uuid
from datetime import datetime
from langchain_core.tools import tool
from src.scheduler.reminder_worker import schedule_new_reminder

@tool
def schedule_reminder(user_id: str, channel: str, target_datetime_iso: str, message_to_remind: str) -> str:
    """
    Agenda um lembrete no Sistema para notificar o usuário de forma proativa no futuro.
    
    IMPORTANTE: Ao usar esta ferramenta, certifique-se de preencher `user_id` e 
    `channel` exatamente como eles estão no estado da conversa (state['user_id'] 
    e state['channel']). Você deve ter recebido esses valores ou descobrir quem 
    é o usuário no chat.
    
    `target_datetime_iso` deve ser uma string ISO 8601 exata no futuro (por exemplo, 
    "2026-03-05T15:30:00-03:00"). Use a ferramenta de `get_current_time` para 
    ajudar a calcular o tempo futuro exato.
    `message_to_remind` é o texto principal que ele pediu para ser lembrado.
    """
    try:
        # Tenta converter a string ISO em objeto datetime
        try:
            target_dt = datetime.fromisoformat(target_datetime_iso)
        except ValueError:
            return f"Erro: Formato de data e hora inválido. '{target_datetime_iso}' não é um ISO 8601 válido."
            
        now = datetime.now().astimezone(target_dt.tzinfo) if target_dt.tzinfo else datetime.now()
        
        if target_dt < now:
            return f"Erro: O tempo alvo {target_dt} já está no passado. O sistema exige uma data futura."

        # Identificador único para a tarefa
        reminder_id = f"rem_{uuid.uuid4().hex[:8]}"
        
        schedule_new_reminder(
            reminder_id=reminder_id, 
            user_id=user_id, 
            channel=channel, 
            target_time=target_dt, 
            message=message_to_remind
        )
        
        return f"Lembrete agendado com sucesso para {target_datetime_iso}. O Id interno é {reminder_id}."
        
    except Exception as e:
        return f"Falha ao agendar lembrete no Scheduler: {str(e)}"
