"""
Agregador de rotas da API v1
"""
from fastapi import APIRouter
from app.api.v1.endpoints import session

api_router = APIRouter()

# Inclui as rotas de sessão
api_router.include_router(
    session.router,
    prefix="/session",
    tags=["session"]
)

