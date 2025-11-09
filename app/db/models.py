"""
Modelos SQLAlchemy para o banco de dados
"""
from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.db.database import Base
import uuid


def generate_uuid():
    """Gera um UUID único para usar como ID"""
    return str(uuid.uuid4())


class SessaoEstudo(Base):
    """
    Modelo para armazenar sessões de estudo.
    
    Uma sessão representa um ciclo completo:
    1. Usuário envia questão original
    2. Sistema gera lista de questões
    3. Sistema gera e salva gabarito mestre
    4. Usuário submete respostas
    5. Sistema corrige e gera relatório
    """
    __tablename__ = "sessoes_estudo"
    
    # ID único da sessão
    session_id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True
    )
    
    # Questão original enviada pelo usuário (texto extraído do OCR)
    questao_original = Column(Text, nullable=False)
    
    # Habilidades BNCC identificadas pelo Agente Interpretador
    habilidades_identificadas = Column(JSON, nullable=True)
    
    # Lista de questões geradas pelo Agente Criador
    lista_questoes = Column(JSON, nullable=False)
    
    # Gabarito mestre gerado pelo Agente Resolução
    gabarito_mestre = Column(JSON, nullable=False)
    
    # Respostas do aluno (quando submetidas)
    respostas_aluno = Column(JSON, nullable=True)
    
    # Relatório diagnóstico gerado pelo Agente Correção
    relatorio_diagnostico = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<SessaoEstudo(session_id={self.session_id})>"

