"""
Configurações da aplicação usando Pydantic Settings
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Configurações da aplicação carregadas do .env"""
    
    # API Keys
    OPENAI_API_KEY: Optional[str] = Field(None, description="Chave da API OpenAI")
    GOOGLE_API_KEY: str = Field(..., description="Chave da API Google")
    
    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./bncc_gen.db",
        description="URL de conexão do banco de dados"
    )
    
    # ChromaDB
    CHROMA_PERSIST_DIRECTORY: str = Field(
        default="./chroma_db",
        description="Diretório de persistência do ChromaDB"
    )
    
    # Aplicação
    APP_NAME: str = Field(default="BNCC-Gen", description="Nome da aplicação")
    APP_VERSION: str = Field(default="1.0.0", description="Versão da aplicação")
    DEBUG: bool = Field(default=False, description="Modo debug")
    
    # LLM Configurations
    DEFAULT_LLM_PROVIDER: str = Field(
        default="google",
        description="Provedor de LLM padrão (openai ou google)"
    )
    DEFAULT_MODEL: str = Field(
        default="gemini-2.5-flash",
        description="Modelo LLM padrão (Google: gemini-1.5-flash, gemini-1.5-pro, OpenAI: gpt-4-turbo-preview)"
    )
    TEMPERATURE: float = Field(
        default=0.7,
        description="Temperatura para geração de texto"
    )
    MAX_TOKENS: int = Field(
        default=4096,
        description="Número máximo de tokens na resposta"
    )
    
    # RAG Configurations
    EMBEDDING_PROVIDER: str = Field(
        default="google",
        description="Provedor de embeddings (openai ou google)"
    )
    EMBEDDING_MODEL: str = Field(
        default="models/embedding-001",
        description="Modelo de embeddings para RAG (Google: models/embedding-001, OpenAI: text-embedding-3-small)"
    )
    CHUNK_SIZE: int = Field(
        default=1000,
        description="Tamanho dos chunks para RAG"
    )
    CHUNK_OVERLAP: int = Field(
        default=200,
        description="Overlap entre chunks"
    )
    TOP_K_RESULTS: int = Field(
        default=5,
        description="Número de resultados a retornar na busca RAG"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Instância global de configurações
settings = Settings()

