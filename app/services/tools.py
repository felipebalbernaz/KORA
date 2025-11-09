"""
Ferramentas (Tools) para os agentes LangChain
"""
from typing import List, Dict, Any, Optional
from langchain.tools import tool
from app.services.rag_service import rag_service
from app.db.database import SessionLocal
from app.db.models import SessaoEstudo
from sqlalchemy.sql import func
import json
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Tools para Busca BNCC (Agente Interpretador e Criador)
# ============================================================================

@tool
def buscar_habilidades_bncc(query: str, ano_escolar: Optional[str] = None) -> str:
    """
    Busca habilidades da BNCC de Matemática usando busca semântica.
    
    Args:
        query: Texto descrevendo o conceito ou questão matemática
        ano_escolar: Filtro opcional por ano (ex: "8º", "9º", "1ª", "2ª")
    
    Returns:
        JSON string com lista de habilidades encontradas
    
    Exemplo de uso:
        buscar_habilidades_bncc("função quadrática vértice", "9º")
    """
    try:
        filtros = {"ano": ano_escolar} if ano_escolar else None
        documentos = rag_service.buscar_habilidades(query, filtros=filtros)
        habilidades = rag_service.formatar_habilidades(documentos)
        
        return json.dumps(habilidades, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Erro em buscar_habilidades_bncc: {e}")
        return json.dumps({"erro": str(e)})


@tool
def buscar_por_conceitos(conceitos: List[str], ano_escolar: Optional[str] = None) -> str:
    """
    Busca habilidades BNCC por conceitos matemáticos específicos.
    
    Args:
        conceitos: Lista de conceitos matemáticos (ex: ["função quadrática", "vértice"])
        ano_escolar: Filtro opcional por ano
    
    Returns:
        JSON string com lista de habilidades encontradas
    
    Exemplo de uso:
        buscar_por_conceitos(["geometria", "triângulos"], "8º")
    """
    try:
        documentos = rag_service.buscar_por_conceitos(conceitos, ano_escolar)
        habilidades = rag_service.formatar_habilidades(documentos)
        
        return json.dumps(habilidades, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Erro em buscar_por_conceitos: {e}")
        return json.dumps({"erro": str(e)})


# ============================================================================
# Tools para Gabarito (Agente Resolução e Correção)
# ============================================================================

@tool
def salvar_gabarito_sessao(session_id: str, gabarito: Dict[str, Any]) -> str:
    """
    Salva o gabarito mestre de uma sessão no banco de dados.
    
    Args:
        session_id: ID da sessão
        gabarito: Dicionário com o gabarito completo
    
    Returns:
        Mensagem de confirmação ou erro
    
    Exemplo de uso:
        salvar_gabarito_sessao("abc-123", {"gabarito": [...]})
    """
    db = SessionLocal()
    try:
        # Busca a sessão
        sessao = db.query(SessaoEstudo).filter(
            SessaoEstudo.session_id == session_id
        ).first()
        
        if not sessao:
            return json.dumps({
                "erro": f"Sessão {session_id} não encontrada"
            })
        
        # Atualiza o gabarito
        sessao.gabarito_mestre = gabarito
        sessao.updated_at = func.now()
        
        db.commit()
        
        logger.info(f"Gabarito salvo para sessão {session_id}")
        return json.dumps({
            "sucesso": True,
            "mensagem": f"Gabarito salvo com sucesso para sessão {session_id}"
        })
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar gabarito: {e}")
        return json.dumps({"erro": str(e)})
    finally:
        db.close()


@tool
def recuperar_gabarito_sessao(session_id: str) -> str:
    """
    Recupera o gabarito mestre de uma sessão do banco de dados.
    
    Args:
        session_id: ID da sessão
    
    Returns:
        JSON string com o gabarito ou mensagem de erro
    
    Exemplo de uso:
        recuperar_gabarito_sessao("abc-123")
    """
    db = SessionLocal()
    try:
        # Busca a sessão
        sessao = db.query(SessaoEstudo).filter(
            SessaoEstudo.session_id == session_id
        ).first()
        
        if not sessao:
            return json.dumps({
                "erro": f"Sessão {session_id} não encontrada"
            })
        
        if not sessao.gabarito_mestre:
            return json.dumps({
                "erro": f"Gabarito não encontrado para sessão {session_id}"
            })
        
        logger.info(f"Gabarito recuperado para sessão {session_id}")
        return json.dumps(sessao.gabarito_mestre, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Erro ao recuperar gabarito: {e}")
        return json.dumps({"erro": str(e)})
    finally:
        db.close()


# ============================================================================
# Lista de todas as ferramentas disponíveis
# ============================================================================

# Tools para Agente Interpretador
INTERPRETADOR_TOOLS = [
    buscar_habilidades_bncc,
    buscar_por_conceitos
]

# Tools para Agente Criador
CRIADOR_TOOLS = [
    buscar_habilidades_bncc
]

# Tools para Agente Resolução
RESOLUCAO_TOOLS = [
    salvar_gabarito_sessao
]

# Tools para Agente Correção
CORRECAO_TOOLS = [
    recuperar_gabarito_sessao
]

# Todas as tools
ALL_TOOLS = [
    buscar_habilidades_bncc,
    buscar_por_conceitos,
    salvar_gabarito_sessao,
    recuperar_gabarito_sessao
]

