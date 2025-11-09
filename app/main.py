"""
Aplicação principal FastAPI - BNCC-Gen
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.database import init_db
from app.api.v1.api import api_router
import logging

# Configuração de logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Cria a aplicação FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## 🎓 BNCC-Gen - Sistema Multiagente de Questões Educacionais
    
    Sistema de IA para gerar listas de exercícios personalizadas baseadas na BNCC.
    
    ### Funcionalidades:
    
    * **Análise Inteligente**: Identifica habilidades BNCC em questões
    * **Geração de Questões**: Cria questões similares automaticamente
    * **Correção Automática**: Corrige respostas e fornece feedback pedagógico
    * **Relatório Diagnóstico**: Identifica pontos fortes e áreas a melhorar
    
    ### Fluxo de Uso:
    
    1. **POST /api/v1/session/start**: Envia questão original, recebe lista de questões
    2. **POST /api/v1/session/{session_id}/submit**: Envia respostas, recebe relatório
    
    ### Tecnologias:
    
    * FastAPI + LangChain
    * OpenAI GPT-4
    * ChromaDB (RAG)
    * SQLite
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar origens permitidas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Evento executado ao iniciar a aplicação"""
    logger.info("=" * 60)
    logger.info(f"Iniciando {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 60)
    
    # Inicializa o banco de dados
    logger.info("Inicializando banco de dados...")
    init_db()
    logger.info("✓ Banco de dados inicializado")
    
    # Verifica configurações
    logger.info(f"LLM Provider: {settings.DEFAULT_LLM_PROVIDER}")
    logger.info(f"Model: {settings.DEFAULT_MODEL}")
    logger.info(f"ChromaDB: {settings.CHROMA_PERSIST_DIRECTORY}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    
    logger.info("=" * 60)
    logger.info("✓ Aplicação iniciada com sucesso!")
    logger.info("📖 Documentação: http://127.0.0.1:8000/docs")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Evento executado ao encerrar a aplicação"""
    logger.info("Encerrando aplicação...")


@app.get("/")
async def root():
    """Endpoint raiz com informações da API"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs": "/docs",
        "endpoints": {
            "start_session": "POST /api/v1/session/start",
            "submit_answers": "POST /api/v1/session/{session_id}/submit",
            "get_session": "GET /api/v1/session/{session_id}"
        }
    }


@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


# Inclui as rotas da API v1
app.include_router(
    api_router,
    prefix="/api/v1"
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )

