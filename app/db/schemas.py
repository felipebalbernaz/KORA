"""
Schemas Pydantic para validação de dados da API
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


# ============================================================================
# Schemas de Request (Entrada)
# ============================================================================

class SessionStartRequest(BaseModel):
    """Request para iniciar uma sessão (arquivo de imagem será enviado via form-data)"""
    pass  # O arquivo será recebido via UploadFile no endpoint


class SessionSubmitRequest(BaseModel):
    """Request para submeter respostas (arquivo de imagem será enviado via form-data)"""
    pass  # O arquivo será recebido via UploadFile no endpoint


# ============================================================================
# Schemas de Response (Saída)
# ============================================================================

class SessionStartResponse(BaseModel):
    """Response ao iniciar uma sessão"""
    session_id: str = Field(..., description="ID único da sessão")
    lista_de_questoes: List[str] = Field(..., description="Lista de questões geradas")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "lista_de_questoes": [
                    "1. Calcule o vértice da função f(x) = x² - 4x + 3",
                    "2. Determine o ponto de máximo da função g(x) = -2x² + 8x - 5",
                    "3. Encontre as coordenadas do vértice de h(x) = 3x² - 12x + 10"
                ]
            }
        }


class CorrecaoDetalhada(BaseModel):
    """Detalhes da correção de uma questão individual"""
    questao: str = Field(..., description="Texto da questão")
    sua_resposta: str = Field(..., description="Resposta fornecida pelo aluno")
    gabarito_correto: str = Field(..., description="Gabarito correto")
    feedback: str = Field(..., description="Feedback sobre a resposta")
    acertou: bool = Field(..., description="Se o aluno acertou a questão")


class RelatorioDiagnostico(BaseModel):
    """Relatório diagnóstico completo"""
    resumo: str = Field(..., description="Resumo geral do desempenho")
    total_questoes: int = Field(..., description="Total de questões")
    total_acertos: int = Field(..., description="Total de acertos")
    percentual_acerto: float = Field(..., description="Percentual de acerto")
    correcao_detalhada: List[CorrecaoDetalhada] = Field(
        ...,
        description="Correção detalhada de cada questão"
    )
    habilidades_a_revisar: List[str] = Field(
        ...,
        description="Habilidades BNCC que precisam ser revisadas"
    )


class SessionSubmitResponse(BaseModel):
    """Response ao submeter respostas"""
    session_id: str = Field(..., description="ID da sessão")
    relatorio_diagnostico: RelatorioDiagnostico = Field(
        ...,
        description="Relatório diagnóstico completo"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "relatorio_diagnostico": {
                    "resumo": "Você acertou 2 de 3 questões (66.7%). Bom começo!",
                    "total_questoes": 3,
                    "total_acertos": 2,
                    "percentual_acerto": 66.7,
                    "correcao_detalhada": [
                        {
                            "questao": "1. Calcule o vértice...",
                            "sua_resposta": "V(2, -1)",
                            "gabarito_correto": "V(2, -1)",
                            "feedback": "Correto! Você aplicou corretamente a fórmula do vértice.",
                            "acertou": True
                        }
                    ],
                    "habilidades_a_revisar": ["EM13MAT503"]
                }
            }
        }


# ============================================================================
# Schemas Internos (Uso interno dos agentes)
# ============================================================================

class HabilidadeBNCC(BaseModel):
    """Representa uma habilidade da BNCC"""
    codigo_bncc: str
    habilidade_bncc: str
    ano: str
    unidades_tematicas: str
    objetos_de_conhecimento: str


class GabaritoQuestao(BaseModel):
    """Gabarito de uma questão individual"""
    numero_questao: int
    questao: str
    resposta_esperada: str
    passos_resolucao: List[str]
    conceitos_chave: List[str]

