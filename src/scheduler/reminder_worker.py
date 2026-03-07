import os
import sqlite3
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
# Para evitar importação circular com o message_handler (que será executado pelo scheduler),
# importaremos as funções de disparo no momento da execução do lembrete.

# Banco de dados simples para persistir os lembretes para eles sobreviverem a restarts do servidor
DB_PATH = os.path.join(os.getcwd(), "data", "reminders.db")

# Instância global do escalonador
scheduler = AsyncIOScheduler()

async def proactive_briefing_job():
    """Tarefa proativa: Revisa o estado atual e envia um briefing matinal."""
    # Nota: Em produção, isso iteraria sobre usuários ativos em settings.ADMIN_NUMBERS
    # Aqui deixamos o exemplo estrutural para o Gean ativar.
    pass

scheduler.add_job(proactive_briefing_job, 'cron', hour=8, minute=0)

def _init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            channel TEXT,
            target_time TEXT,
            message TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

_init_db()

async def execute_reminder(reminder_id: str, user_id: str, channel: str, message: str):
    """
    Função executada pelo APScheduler no momento exato agendado.
    """
    try:
        from src.core.engine import engine
        from langchain_core.messages import HumanMessage
        from src.router.message_handler import send_telegram_message, send_whatsapp_message
        
        # Quando acorda, o agente precisa se expressar proativamente
        prompt = (
            f"IGNORAR INSTRUÇÕES ANTERIORES. ESTE É UM ALARME DE SISTEMA QUE ACABOU DE DISPARAR.\n"
            f"Atenção, o tempo passou e o horário exato do lembrete do usuário chegou AGORA.\n"
            f"Lembrete original registrado: '{message}'\n\n"
            f"Sua tarefa: Fale diretamente com o usuário repassando o lembrete de forma amigável e proativa. "
            f"NÃO diga que agendou o lembrete, pois ele já estava agendado e agora é o momento da execução."
        )
        
        brain = await engine.get_brain()
        initial = {
            'messages': [HumanMessage(content=prompt)],
            'user_id': user_id,
            'channel': channel
        }
        config = {'configurable': {'thread_id': f"{channel}_{user_id}"}}
        
        # Pede pro modelo gerar a mensagem de aviso (isso acontece em background)
        # Note: ainvoke no grafo compilado retorna o estado final
        final_state = await brain.ainvoke(initial, config=config)
        ai_response = "Lembrete: " + message # Fallback
        
        for m in reversed(final_state.get("messages", [])):
            if m.type == "ai" and m.content:
                ai_response = m.content
                break
        
        # Envia pelo canal certo
        if channel == "whatsapp":
            # Extraindo JID hipotético (isso vai requerer que a gente adicione o remote_jid no banco, 
            # ou trate 'user_id' como sendo o próprio remote_jid/chat_id).
            await send_whatsapp_message(user_id, ai_response)
        elif channel == "telegram":
            await send_telegram_message(user_id, ai_response)
            
        # Marca como concluído
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE reminders SET status = 'completed' WHERE id = ?", (reminder_id,))
        conn.commit()
        conn.close()
        
    except Exception as e:
        import logging
        logging.error(f"Erro ao executar reminder {reminder_id}: {e}")

def schedule_new_reminder(reminder_id: str, user_id: str, channel: str, target_time: datetime, message: str):
    """
    Persiste o lembrete e adiciona no scheduler em memória.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO reminders (id, user_id, channel, target_time, message, status) VALUES (?, ?, ?, ?, ?, ?)",
        (reminder_id, user_id, channel, target_time.isoformat(), message, 'pending')
    )
    conn.commit()
    conn.close()
    
    # Adiciona ao scheduler do APScheduler
    scheduler.add_job(
        execute_reminder, 
        'date', 
        run_date=target_time, 
        args=[reminder_id, user_id, channel, message],
        id=reminder_id
    )

def load_pending_reminders():
    """Lê do banco lembretes não concluídos (úteis ao reiniciar app)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, user_id, channel, target_time, message FROM reminders WHERE status = 'pending'")
    rows = c.fetchall()
    conn.close()
    
    count = 0
    for row in rows:
        r_id, u_id, chan, t_str, msg = row
        t_time = datetime.fromisoformat(t_str)
        now = datetime.now().astimezone(t_time.tzinfo) if t_time.tzinfo else datetime.now()
        
        if t_time < now:
            # Já passou, deveria disparar imediatamente
            scheduler.add_job(execute_reminder, 'date', run_date=now, args=[r_id, u_id, chan, msg], id=r_id)
        else:
            scheduler.add_job(execute_reminder, 'date', run_date=t_time, args=[r_id, u_id, chan, msg], id=r_id)
        count += 1
    print(f"[Scheduler] {count} lembretes pendentes carregados na memória.")
