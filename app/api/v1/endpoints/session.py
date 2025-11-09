"""
Endpoints da API para gerenciamento de sessões de estudo
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Body, Request
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.db.database import get_db
from app.db.models import SessaoEstudo
from app.db.schemas import SessionStartResponse, SessionSubmitResponse
from app.services.ocr_service import ocr_service
from app.services.agent_service import agent_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/start", response_model=SessionStartResponse)
async def start_session(
    file: UploadFile = File(..., description="Imagem da questão original"),
    db: Session = Depends(get_db)
):
    """
    Inicia uma nova sessão de estudo.

    Fluxo:
    1. Recebe imagem/arquivo de texto da questão original
    2. Extrai texto (OCR mock quando imagem)
    3. Agente Interpretador identifica habilidades BNCC
    4. Pipeline Criador → Solver → Validação gera 3 questões aprovadas
    5. Agente Resolução cria gabarito mestre final das aprovadas
    6. Salva tudo no banco e retorna session_id + questões
    """
    try:
        logger.info("=== Iniciando nova sessão ===")
        
        # 1. Extrai texto da imagem (OCR Mock)
        logger.info("Passo 1: Extraindo texto da questão")
        # Se recebermos um arquivo de texto (enviado pelo Streamlit), usamos o conteúdo diretamente.
        if getattr(file, "content_type", None) == "text/plain":
            raw_bytes = await file.read()
            questao_texto = raw_bytes.decode("utf-8", errors="ignore").strip()
            logger.info("Texto recebido diretamente (text/plain)")
        else:
            # Caso contrário, usa o OCR mock (MVP)
            questao_texto = await ocr_service.extrair_texto_questao(file.file)
            logger.info("Texto extraído via OCR (mock)")
        logger.info(f"Texto extraído: {questao_texto[:100]}...")
        
        # 2. Agente Interpretador: Identifica habilidades BNCC
        logger.info("Passo 2: Identificando habilidades BNCC")
        analise = await agent_service.interpretar_questao(questao_texto)
        logger.info(f"Habilidades identificadas: {len(analise.get('habilidades_identificadas', []))}")
        
        # 3. Pipeline Criador → Solver → Validação: gera 3 questões aprovadas
        logger.info("Passo 3: Gerando e validando questões (alvo=3)")
        aprovadas, gabarito = await agent_service.gerar_questoes_validadas(
            questao_original=questao_texto,
            habilidades_identificadas=analise.get('habilidades_identificadas', []),
            conceitos_principais=analise.get('conceitos_principais', []),
            ano_escolar=analise.get('ano_recomendado', 'Não especificado'),
            alvo=3,
            max_tentativas=3,
        )
        logger.info(f"Questões aprovadas: {len(aprovadas)}")

        # Converte para lista de strings para resposta (mantém objetos no banco)
        questoes_strings = []
        for i, q in enumerate(aprovadas, start=1):
            if isinstance(q, dict):
                num = q.get('numero', i)
                enun = q.get('enunciado', '')
                questoes_strings.append(f"{num}. {enun}")
            else:
                questoes_strings.append(str(q))

        # 4. Cria sessão no banco
        logger.info("Passo 4: Criando sessão no banco")
        sessao = SessaoEstudo(
            questao_original=questao_texto,
            habilidades_identificadas=analise,
            lista_questoes=aprovadas,
            gabarito_mestre=gabarito
        )
        db.add(sessao)
        db.commit()
        db.refresh(sessao)
        logger.info(f"Sessão criada: {sessao.session_id}")

        # 5. Retorna resposta
        logger.info("=== Sessão iniciada com sucesso ===")
        return SessionStartResponse(
            session_id=sessao.session_id,
            lista_de_questoes=questoes_strings
        )
        
    except Exception as e:
        logger.error(f"Erro ao iniciar sessão: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar questão: {str(e)}"
        )


@router.post("/{session_id}/submit", response_model=SessionSubmitResponse)
async def submit_answers(
    session_id: str,
    request: Request,
    file: UploadFile = File(None, description="Imagem/arquivo de respostas do aluno (opcional)"),
    db: Session = Depends(get_db)
):
    """
    Submete respostas do aluno e retorna relatório diagnóstico.

    Aceita duas formas de entrada:
    - JSON com {"respostas": {"1":"A","2":"C","3":"B"}}
    - Arquivo (texto ou imagem) com respostas livres (MVP legado)
    """
    try:
        logger.info(f"=== Submetendo respostas para sessão {session_id} ===")

        # 1. Busca a sessão
        logger.info("Passo 1: Buscando sessão")
        sessao = db.query(SessaoEstudo).filter(
            SessaoEstudo.session_id == session_id
        ).first()

        if not sessao:
            raise HTTPException(
                status_code=404,
                detail=f"Sessão {session_id} não encontrada"
            )

        respostas_texto = None
        payload = None
        # 2. Tenta ler JSON do corpo
        try:
            if request.headers.get("content-type", "").startswith("application/json"):
                payload = await request.json()
        except Exception:
            payload = None

        if payload and isinstance(payload, dict) and payload.get("respostas"):
            # Converte mapa de alternativas para texto legível pelo agente de correção
            mapa = payload.get("respostas") or {}
            linhas = []
            for k, v in mapa.items():
                linhas.append(f"Questão {k}: {str(v).upper()}")
            respostas_texto = "\n".join(linhas)
            logger.info("Respostas recebidas em JSON (alternativas)")
        elif file is not None:
            # 3. Extrai texto das respostas (OCR Mock)
            logger.info("Passo 2: Extraindo texto das respostas (arquivo)")
            if getattr(file, "content_type", None) == "text/plain":
                raw_bytes = await file.read()
                respostas_texto = raw_bytes.decode("utf-8", errors="ignore").strip()
                logger.info("Respostas recebidas diretamente (text/plain)")
            else:
                # Caso contrário, usa o OCR mock (MVP)
                respostas_texto = await ocr_service.extrair_texto_respostas(file.file)
                logger.info("Respostas extraídas via OCR (mock)")
        else:
            raise HTTPException(status_code=400, detail="Envie um JSON com 'respostas' ou um arquivo de respostas.")

        logger.info(f"Respostas processadas (preview): {(respostas_texto or '')[:100]}...")

        # 3. Agente Correção: Corrige e gera relatório
        logger.info("Passo 3: Corrigindo respostas")
        relatorio = await agent_service.corrigir_respostas(
            session_id=session_id,
            respostas_aluno=respostas_texto or ""
        )
        logger.info("Relatório diagnóstico gerado")

        # 4. Atualiza sessão no banco
        logger.info("Passo 4: Atualizando sessão no banco")
        sessao.respostas_aluno = payload if payload else {"texto": respostas_texto}
        sessao.relatorio_diagnostico = relatorio
        sessao.submitted_at = func.now()
        sessao.updated_at = func.now()
        db.commit()
        logger.info("Sessão atualizada")

        # 5. Retorna resposta
        logger.info("=== Respostas submetidas com sucesso ===")
        return SessionSubmitResponse(
            session_id=session_id,
            relatorio_diagnostico=relatorio
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao submeter respostas: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar respostas: {str(e)}"
        )


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Retorna informações de uma sessão específica.
    """
    sessao = db.query(SessaoEstudo).filter(
        SessaoEstudo.session_id == session_id
    ).first()
    
    if not sessao:
        raise HTTPException(
            status_code=404,
            detail=f"Sessão {session_id} não encontrada"
        )
    
    return {
        "session_id": sessao.session_id,
        "questao_original": sessao.questao_original,
        "lista_questoes": sessao.lista_questoes,
        "gabarito_mestre": sessao.gabarito_mestre,
        "habilidades_identificadas": sessao.habilidades_identificadas,
        "created_at": sessao.created_at,
        "submitted_at": sessao.submitted_at,
        "has_relatorio": sessao.relatorio_diagnostico is not None
    }

