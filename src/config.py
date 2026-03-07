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
    # Pasta de saídas de dados
    DATA_OUTPUTS_PATH: str = os.path.join(BASE_DIR, "data", "outputs")
    # Pasta das Personas (Skins) - Localizada dentro de src/agents
    SQUAD_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents")

    # --- MODELS ---
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_MODEL: str = "gemini-2.0-flash" # Estável e performático
    
    # --- KEYS ---
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    
    # --- CHANNELS (Evolution API / Telegram) ---
    EVOLUTION_API_URL: str = ""
    EVOLUTION_API_KEY: str = ""
    INSTANCE_NAME: str = "arth_instance"
    TELEGRAM_BOT_TOKEN: str = ""
    
    # --- META DIRECT API (Instagram/WhatsApp Business) ---
    INSTAGRAM_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "arth_executive_verify" # Token para validação do webhook na Meta
    META_API_VERSION: str = "v18.0"
    
    # --- DATABASE (SUPABASE/POSTGRES) ---
    SUPABASE_DATABASE_URL: str = ""
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Garantir que a pasta de outputs existe
os.makedirs(settings.DATA_OUTPUTS_PATH, exist_ok=True)
