from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_default_model: str = "llama3"

    # Database
    database_url: str = "sqlite+aiosqlite:///./loomin.db"

    # FAISS
    faiss_index_path: str = "./faiss_index"

    # Embedding model
    embedding_model: str = "all-MiniLM-L6-v2"

    # Server
    backend_port: int = 8000

    # Context window sizes per model (tokens)
    context_windows: dict = {
        "llama3": 8192,
        "llama3:latest": 8192,
        "mistral": 8192,
        "mistral:latest": 8192,
        "loomin-assistant": 4096,
        "loomin-assistant:latest": 4096,
    }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()