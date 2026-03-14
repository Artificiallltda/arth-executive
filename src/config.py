import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # --- APP INFO ---
    APP_NAME: str = "Arth Executive AI"
    VERSION: str = "0.1.1"
    
    # --- PATHS ---
    # Base do projeto (arth-executive/)
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Pasta de saídas de dados (Blindagem Docker/Railway)
    # Se estiver rodando no Linux (Docker), usa caminho absoluto /app
    DATA_OUTPUTS_PATH: str = "/app/data/outputs" if os.name != 'nt' else os.path.join(BASE_DIR, "data", "outputs")

    # Pasta das Personas (Skins)
    SQUAD_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents")


    # --- MODELS ---
    PRIMARY_MODEL: str = os.getenv("PRIMARY_MODEL", "gemini-3-pro-preview") 
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gemini-3-pro-preview") 
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    
    # --- KEYS ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    
    # --- CHANNELS (Evolution API / Telegram) ---
    EVOLUTION_API_URL: str = os.getenv("EVOLUTION_API_URL", "")
    EVOLUTION_API_KEY: str = os.getenv("EVOLUTION_API_KEY", "")
    INSTANCE_NAME: str = os.getenv("INSTANCE_NAME", "arth_instance")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # --- META DIRECT API (Instagram/WhatsApp Business) ---
    INSTAGRAM_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "arth_executive_verify" # Token para validação do webhook na Meta
    META_API_VERSION: str = "v18.0"
    
    # --- DATABASE (SUPABASE/POSTGRES) ---
    SUPABASE_DATABASE_URL: str = ""
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Garantir que a pasta de outputs existe
os.makedirs(settings.DATA_OUTPUTS_PATH, exist_ok=True)
