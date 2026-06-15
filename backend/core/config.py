# backend/core/config.py
import os
from dotenv import load_dotenv
import os
from dotenv import load_dotenv

load_dotenv()

print("GROQ KEY LOADED:", os.getenv("GROQ_API_KEY", "NOT FOUND"))  # add this line
load_dotenv()

class Settings:
    # Groq
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MAIN_MODEL: str = os.getenv("GROQ_MAIN_MODEL", "llama-3.1-70b-versatile")
    GROQ_FAST_MODEL: str = os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant")

    # App
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./interview_simulator.db")

    # ChromaDB
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")

    # Whisper
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")

    # Interview behaviour
    SATISFACTION_THRESHOLD: float = float(os.getenv("SATISFACTION_THRESHOLD", "0.65"))
    MAX_FOLLOW_UPS: int = int(os.getenv("MAX_FOLLOW_UPS_PER_QUESTION", "3"))
    MIN_QUESTIONS_PER_TOPIC: int = int(os.getenv("MIN_QUESTIONS_PER_TOPIC", "2"))
    MAX_QUESTIONS_PER_TOPIC: int = int(os.getenv("MAX_QUESTIONS_PER_TOPIC", "5"))

settings = Settings()
