"""
Buffer de logs em memória — permite consultar os últimos N eventos do sistema
sem precisar acessar o painel do Railway.

Uso:
  - GET /api/v1/logs           → últimos 60 logs
  - GET /api/v1/logs?n=100     → últimos 100 logs
  - GET /api/v1/logs?level=ERROR → apenas erros
  - Telegram/WhatsApp: /logs   → envia os últimos 30 logs no chat
"""
import logging
from collections import deque
from datetime import datetime

_MAX = 400
_buffer: deque = deque(maxlen=_MAX)

_LEVEL_ICON = {
    "ERROR":    "❌",
    "WARNING":  "⚠️",
    "INFO":     "ℹ️",
    "DEBUG":    "🔍",
    "CRITICAL": "🔥",
}


class _BufferHandler(logging.Handler):
    """Handler que empurra cada LogRecord para o buffer circular."""

    def emit(self, record: logging.LogRecord):
        try:
            _buffer.append({
                "ts":      datetime.now().strftime("%H:%M:%S"),
                "level":   record.levelname,
                "module":  record.module,
                "message": self.format(record),
            })
        except Exception:
            pass


def setup_log_buffer(root_level: int = logging.INFO):
    """Chame uma vez no startup do app para ativar o buffer."""
    root = logging.getLogger()

    # Evita duplicar o handler se já estiver registrado
    if any(isinstance(h, _BufferHandler) for h in root.handlers):
        return

    handler = _BufferHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)

    # Garante que o root captura INFO (sem sobreescrever nível já mais verboso)
    if root.level == logging.NOTSET or root.level > root_level:
        root.setLevel(root_level)


def get_logs(n: int = 60, level: str = None) -> list[dict]:
    entries = list(_buffer)
    if level:
        entries = [e for e in entries if e["level"] == level.upper()]
    return entries[-n:]


def _safe_str(s: str, max_len: int = 250) -> str:
    """Remove surrogate characters que quebram UTF-8 no Telegram."""
    return s.encode("utf-8", errors="replace").decode("utf-8")[:max_len]


def get_logs_text(n: int = 30) -> str:
    """Versão compacta para enviar via chat."""
    entries = get_logs(n)
    if not entries:
        return "Nenhum log registrado ainda."
    lines = [f"Ultimos {len(entries)} logs do sistema:\n"]
    for e in entries:
        icon = _LEVEL_ICON.get(e["level"], "-")
        msg = _safe_str(e["message"]).replace("*", "").replace("`", "").replace("_", "-")
        lines.append(f"{icon} [{e['ts']}] {e['module']}: {msg}")
    return "\n".join(lines)


def get_logs_json(n: int = 60, level: str = None) -> list[dict]:
    return get_logs(n=n, level=level)
