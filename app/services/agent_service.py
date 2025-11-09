"""
Serviço de Agentes LangChain com Tool Calling
"""
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings
from app.prompts.prompt_loader import prompt_loader
from app.services.tools import (
    INTERPRETADOR_TOOLS,
    CRIADOR_TOOLS,
    RESOLUCAO_TOOLS,
    CORRECAO_TOOLS,
    salvar_gabarito_sessao,
    recuperar_gabarito_sessao,
)
import logging
import json
import re
import asyncio
import uuid
import random

logger = logging.getLogger(__name__)


# =========================
# Modelos estruturados (Pydantic) para saída JSON
# =========================
class QuestaoMCItem(BaseModel):
    numero: int
    enunciado: str
    habilidades_combinadas: List[str]
    # Novo campo: gabarito do criador (não exposto ao resolvedor)
    resposta_correta: Optional[str] = None

class QuestoesMC(BaseModel):
    questoes: List[QuestaoMCItem]

class GabaritoItem(BaseModel):
    """
    Schema para um item do gabarito.
    NOTA: O campo 'alternativas' (Dict[str, str]) NÃO está incluído aqui porque
    Gemini JSON schema não aceita Dict sem propriedades explícitas.
    As alternativas são adicionadas dinamicamente após a geração do gabarito.
    """
    numero_questao: int
    questao: str
    resposta_final: str
    passos_resolucao: List[str]
    conceitos_aplicados: List[str]
    erros_comuns: List[str]
    criterios_correcao: str
    alternativa_correta_letra: Optional[str] = None

    class Config:
        # Permite campos extras (como 'alternativas') serem adicionados dinamicamente
        extra = "allow"

class GabaritoMestre(BaseModel):
    gabarito: List[GabaritoItem]

class DistratoresSaida(BaseModel):
    distratores: List[str]
    observacoes: Optional[str] = None

class CorrecaoItem(BaseModel):
    questao: str
    sua_resposta: str
    gabarito_correto: str
    feedback: str
    acertou: bool
    tipo_erro: str

class RelatorioDiagnostico(BaseModel):
    resumo: str
    total_questoes: int
    total_acertos: int
    percentual_acerto: float
    correcao_detalhada: List[CorrecaoItem]
    habilidades_a_revisar: List[str]
    pontos_fortes: List[str]
    recomendacoes: str

class Consistencia(BaseModel):
    equivalentes: bool
    justificativa: str


class AgentService:
    """
    Serviço para gerenciar os 4 agentes do sistema:
    1. Agente Interpretador - Identifica habilidades BNCC
    2. Agente Criador - Gera questões similares
    3. Agente Resolução - Resolve questões e cria gabarito
    4. Agente Correção - Corrige respostas e gera relatório
    """

    def __init__(self):
        """Inicializa o serviço de agentes"""
        # Seleciona o provedor de LLM
        if settings.DEFAULT_LLM_PROVIDER == "google":
            self.llm = ChatGoogleGenerativeAI(
                model=settings.DEFAULT_MODEL,
                temperature=settings.TEMPERATURE,
                max_output_tokens=settings.MAX_TOKENS,
                google_api_key=settings.GOOGLE_API_KEY,
                convert_system_message_to_human=True  # Gemini não suporta SystemMessage nativamente
            )
            logger.info(f"Usando Google Gemini: {settings.DEFAULT_MODEL}")
        else:
            self.llm = ChatOpenAI(
                model=settings.DEFAULT_MODEL,
                temperature=settings.TEMPERATURE,
                max_tokens=settings.MAX_TOKENS,
                openai_api_key=settings.OPENAI_API_KEY
            )
            logger.info(f"Usando OpenAI: {settings.DEFAULT_MODEL}")

        # LLMs estruturados para garantir JSON (evita MAX_TOKENS com pensamento oculto)
        try:
            self.llm_criador_json = self.llm.with_structured_output(QuestoesMC, method="json_schema")
            self.llm_resolucao_json = self.llm.with_structured_output(GabaritoMestre, method="json_schema")
            self.llm_item_json = self.llm.with_structured_output(GabaritoItem, method="json_schema")
            self.llm_correcao_json = self.llm.with_structured_output(RelatorioDiagnostico, method="json_schema")
            self.llm_julgamento_json = self.llm.with_structured_output(Consistencia, method="json_schema")
        except Exception as e:
            logger.warning(f"Falha ao configurar structured output: {e}")
            self.llm_criador_json = None
            self.llm_resolucao_json = None
            self.llm_item_json = None
            self.llm_correcao_json = None
            self.llm_julgamento_json = None

        # Carrega os prompts
        self.prompts = {
            'interpretador': prompt_loader.get_agent_prompts('interpretador'),
            'criador': prompt_loader.get_agent_prompts('criador'),
            'resolucao': prompt_loader.get_agent_prompts('resolucao'),
            'correcao': prompt_loader.get_agent_prompts('correcao'),
            'distratores': prompt_loader.get_agent_prompts('distratores')
        }

        # Inicializa os agentes
        self.agente_interpretador = self._create_agent(
            'interpretador',
            INTERPRETADOR_TOOLS
        )
        self.agente_criador = self._create_agent(
            'criador',
            CRIADOR_TOOLS
        )
        self.agente_resolucao = self._create_agent(
            'resolucao',
            RESOLUCAO_TOOLS
        )
        self.agente_correcao = self._create_agent(
            'correcao',
            CORRECAO_TOOLS
        )
        # Agente de distratores nao usa ferramentas (MVP)
        self.agente_distratores = self._create_agent(
            'distratores',
            []
        )
        try:
            self.llm_distratores_json = self.llm.with_structured_output(DistratoresSaida, method="json_schema")
        except Exception:
            self.llm_distratores_json = None

    def _create_agent(self, agent_name: str, tools: List) -> Any:
        """
        Cria um agente com ferramentas específicas (LangChain 1.x create_agent)

        Args:
            agent_name: Nome do agente
            tools: Lista de ferramentas disponíveis

        Returns:
            CompiledStateGraph (agente) configurado
        """
        prompts = self.prompts[agent_name]

        # Extrai as variáveis do template human (apenas para log/debug)
        human_template = prompts['human']
        variables = re.findall(r'\{(\w+)\}', human_template)
        variables = list(dict.fromkeys(variables))  # remove duplicatas mantendo ordem
        logger.info(f"Variáveis encontradas no prompt {agent_name}: {variables}")

        # Cria o agente usando a nova API (não requer agent_scratchpad)
        agent_graph = create_agent(
            model=self.llm,
            tools=tools,
            system_prompt=prompts['system'],
            debug=settings.DEBUG,
        )

        logger.info(f"Agente {agent_name} criado com sucesso")
        return agent_graph

    async def _run_agent(self, agent, human_template: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Formata a mensagem humana e executa o agente retornando o estado."""
        prompt = ChatPromptTemplate.from_messages([
            ("human", human_template)
        ])
        messages = prompt.format_messages(**variables)
        return await agent.ainvoke({"messages": messages})

    def _extract_output_text(self, result: Dict[str, Any]) -> str:
        """Extrai o texto do último AIMessage não vazio do resultado do agente."""
        messages = result.get("messages") or []
        # Procura do fim para o início o primeiro AIMessage com conteúdo textual não vazio
        for m in reversed(messages):
            if getattr(m, "type", None) == "ai":
                content = getattr(m, "content", "")
                # Converte blocos em texto quando necessário
                if isinstance(content, list):
                    parts = []
                    for part in content:
                        if isinstance(part, dict) and "text" in part:
                            parts.append(part["text"])
                    content = "\n".join(parts) if parts else str(content)
                if isinstance(content, str) and content.strip():
                    return content
        return ""

    def _maybe_unfence_json(self, text: str) -> str:
        """Remove cercas ```json ... ``` se presentes para permitir json.loads."""
        try:
            m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
            if m:
                return m.group(1).strip()
        except Exception:
            pass
        return text

    # ==== Persistência direta no banco (evita depender do LLM para chamar tools)
    def _save_gabarito_to_db(self, session_id: str, gabarito: Dict[str, Any]) -> None:
        try:
            from app.db.database import SessionLocal
            from app.db.models import SessaoEstudo
            from sqlalchemy.sql import func
            db = SessionLocal()
            try:
                s = db.query(SessaoEstudo).filter(SessaoEstudo.session_id == session_id).first()
                if not s:
                    logger.warning(f"Sessão {session_id} não encontrada para salvar gabarito")
                    return
                s.gabarito_mestre = gabarito
                s.updated_at = func.now()
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Falha ao salvar gabarito no banco: {e}")

    def _get_gabarito_from_db(self, session_id: str) -> Dict[str, Any]:
        try:
            from app.db.database import SessionLocal
            from app.db.models import SessaoEstudo
            db = SessionLocal()
            try:
                s = db.query(SessaoEstudo).filter(SessaoEstudo.session_id == session_id).first()
                return s.gabarito_mestre if s and s.gabarito_mestre else {}
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Falha ao recuperar gabarito do banco: {e}")
            return {}


    async def interpretar_questao(self, questao_texto: str) -> Dict[str, Any]:
        """
        Agente Interpretador: Analisa questão e identifica habilidades BNCC

        Args:
            questao_texto: Texto da questão original

        Returns:
            Dicionário com habilidades identificadas e análise
        """
        logger.info("Executando Agente Interpretador")

        try:
            result = await self._run_agent(
                self.agente_interpretador,
                self.prompts['interpretador']['human'],
                {"questao_texto": questao_texto}
            )

            # Extrai o output (LangChain 1.x retorna messages)
            output = self._extract_output_text(result)
            output = self._maybe_unfence_json(output)

            # Tenta parsear como JSON
            try:
                analise = json.loads(output)
            except json.JSONDecodeError:
                # Se não for JSON válido, cria estrutura básica
                analise = {
                    "habilidades_identificadas": [],
                    "conceitos_principais": [],
                    "ano_recomendado": "Não identificado",
                    "analise_geral": output
                }

            logger.info("Agente Interpretador concluído")
            return analise

        except Exception as e:
            logger.error(f"Erro no Agente Interpretador: {e}")
            raise

    async def criar_questoes(
        self,
        questao_original: str,
        habilidades_identificadas: List[Dict],
        conceitos_principais: List[str],
        ano_escolar: str
    ) -> List[Dict[str, Any]]:
        """
        Agente Criador: Gera 3 questões similares com ENUNCIADO, HABILIDADES COMBINADAS e a RESPOSTA_CORRETA (gabarito do criador).

        Observação: a resposta correta do criador é usada apenas para validação interna de solvabilidade.
        O Agente de Resolução NÃO terá acesso a esse gabarito.

        Args:
            questao_original: Questão original
            habilidades_identificadas: Habilidades BNCC identificadas
            conceitos_principais: Conceitos matemáticos principais
            ano_escolar: Ano escolar recomendado

        Returns:
            Lista de objetos com as chaves:
            - numero (int)
            - enunciado (str)
            - habilidades_combinadas (List[str])
            - resposta_correta_criador (str)  [somente para validação interna]
        """
        logger.info("Executando Agente Criador")

        try:
            # Formata as habilidades para o prompt
            habilidades_str = json.dumps(
                habilidades_identificadas,
                ensure_ascii=False,
                indent=2
            )
            conceitos_str = ", ".join(conceitos_principais)

            questoes_objs: List[Dict[str, Any]] = []

            # 1) Preferir saida estruturada com JSON schema (mais robusto com Gemini)
            if getattr(self, "llm_criador_json", None) is not None:
                logger.info("Criador: tentativa estruturada (JSON schema)")
                from langchain_core.prompts import ChatPromptTemplate
                prompts = self.prompts['criador']
                prompt = ChatPromptTemplate.from_messages([
                    ("system", prompts['system']),
                    ("human", prompts['human'])
                ])
                try:
                    data = await (prompt | self.llm_criador_json).ainvoke({
                        "questao_original": questao_original,
                        "habilidades_identificadas": habilidades_str,
                        "conceitos_principais": conceitos_str,
                        "ano_escolar": ano_escolar
                    })
                    if hasattr(data, "model_dump"):
                        payload = data.model_dump()
                    elif isinstance(data, dict):
                        payload = data
                    else:
                        payload = {}
                    if isinstance(payload, dict) and payload.get("questoes"):
                        questoes_objs = list(payload["questoes"])
                    elif isinstance(payload, list):
                        questoes_objs = list(payload)
                except Exception as e:
                    logger.warning(f"Criador estruturado falhou: {e}")

            # 2) Fallback: usar agente com ferramentas e parsear a saida textual
            if not questoes_objs:
                result = await self._run_agent(
                    self.agente_criador,
                    self.prompts['criador']['human'],
                    {
                        "questao_original": questao_original,
                        "habilidades_identificadas": habilidades_str,
                        "conceitos_principais": conceitos_str,
                        "ano_escolar": ano_escolar
                    }
                )
                output = self._extract_output_text(result)
                output = self._maybe_unfence_json(output)
                try:
                    data = json.loads(output)
                    if isinstance(data, dict) and data.get("questoes"):
                        questoes_objs = list(data["questoes"])
                    elif isinstance(data, list):
                        questoes_objs = list(data)
                except Exception:
                    pass

            # 3) Ultimo recurso: converte texto em skeleton
            if not questoes_objs:
                linhas = [
                    line.strip() for line in (output or "").split('\n')
                    if line.strip() and any(c.isdigit() for c in line[:3])
                ]
                for i, ln in enumerate(linhas[:3], start=1):
                    # Remove o numero inicial, se houver
                    enun = ln
                    m = re.match(r"^\s*\d+[\.)\-]\s*(.*)$", ln)
                    if m:
                        enun = m.group(1).strip()
                    questoes_objs.append({
                        "numero": i,
                        "enunciado": enun,
                        "habilidades_combinadas": [c.strip() for c in conceitos_str.split(',') if c.strip()][:2] or ["habilidade_1", "habilidade_2"],
                    })

            # Normaliza e garante campos
            norm: List[Dict[str, Any]] = []
            for i, q in enumerate(questoes_objs[:3], start=1):
                item = {
                    "numero": int(q.get("numero", i)),
                    "enunciado": q.get("enunciado", ""),
                    "habilidades_combinadas": q.get("habilidades_combinadas", [])[0:3] or [
                        c.strip() for c in conceitos_str.split(',') if c.strip()
                    ][:2] or ["habilidade_1", "habilidade_2"],
                    # Mantemos o gabarito do criador apenas neste objeto para validacao interna
                    "resposta_correta_criador": (
                        q.get("resposta_correta")
                        or q.get("resposta")
                        or q.get("resposta_final")
                        or q.get("gabarito")
                    ) or None,
                }
                # descarta itens sem enunciado
                if str(item["enunciado"]).strip():
                    norm.append(item)

            logger.info(f"Agente Criador gerou {len(norm)} questoes (enunciado + habilidades + gabarito oculto do criador)")
            return norm

        except Exception as e:
            logger.error(f"Erro no Agente Criador: {e}")
            raise

    async def resolver_questoes(
        self,
        session_id: str,
        questoes: List[Any]
    ) -> Dict[str, Any]:
        """
        Agente Resolução: Resolve questões e salva gabarito.

        Resolve de forma independente (sem gabarito de entrada). Usa fallback por item
        caso o JSON completo falhe.
        """
        logger.info("Executando Agente Resolução")

        try:
            # Extrai enunciados preservando numeração
            def _enun(q):
                if isinstance(q, dict):
                    return str(q.get("enunciado", "")).strip()
                return str(q).strip()

            blocos = []
            for i, q in enumerate(questoes, start=1):
                blocos.append(f"{i}. {_enun(q)}")
            questoes_str = "\n\n".join(blocos)

            # 1) Tenta via agente (com tool calling)
            result = await self._run_agent(
                self.agente_resolucao,
                self.prompts['resolucao']['human'],
                {
                    "session_id": session_id,
                    "questoes": questoes_str
                }
            )

            output = self._extract_output_text(result)
            output = self._maybe_unfence_json(output)

            gabarito: Dict[str, Any] = {}

            # 1a) Parse direto do output do agente
            if output:
                try:
                    parsed = json.loads(output)
                    if isinstance(parsed, dict) and parsed.get("gabarito"):
                        gabarito = parsed
                except json.JSONDecodeError:
                    pass

            # 2) Fallback estruturado (JSON) se necessário
            if not gabarito and self.llm_resolucao_json is not None:
                logger.info("Fallback estruturado: gerando gabarito com JSON schema")
                prompts = self.prompts['resolucao']
                prompt = ChatPromptTemplate.from_messages([
                    ("system", prompts['system']),
                    ("human", prompts['human'])
                ])
                try:
                    data = await (prompt | self.llm_resolucao_json).ainvoke({
                        "session_id": session_id,
                        "questoes": questoes_str
                    })
                    if hasattr(data, "model_dump"):
                        gabarito = data.model_dump()
                    elif isinstance(data, dict):
                        gabarito = data
                except Exception as e:
                    logger.warning(f"Falha no fallback estruturado do gabarito: {e}")

            # 2b) Fallback por questão (divide e conquista) para reduzir tokens
            if not gabarito and getattr(self, "llm_item_json", None) is not None:
                logger.info("Fallback item a item: resolvendo cada questão separadamente")
                items: List[Dict[str, Any]] = []
                prompts = self.prompts['resolucao']
                item_prompt = ChatPromptTemplate.from_messages([
                    ("system", prompts['system']),
                    ("human", (
                        "Resolva apenas a questão abaixo e retorne EXCLUSIVAMENTE o objeto da questão (JSON).\n\n"
                        "Número da questão: {numero}\n"
                        "Questão:\n{questao}\n\n"
                        "Instruções: gere 'resposta_final' (valor textual/numérico), 'passos_resolucao',\n"
                        "'alternativa_correta_letra' (A–E) e, se possível, 'alternativas' (mapa a→e)."
                    ))
                ])
                for idx, q in enumerate(questoes, start=1):
                    try:
                        questao_txt = _enun(q)

                        data = await (item_prompt | self.llm_item_json).ainvoke({
                            "numero": idx,
                            "questao": questao_txt,
                        })
                        if hasattr(data, "model_dump"):
                            item = data.model_dump()
                        elif isinstance(data, dict):
                            item = data
                        else:
                            item = {}

                        # Garante chaves obrigatórias
                        base = {
                            "numero_questao": idx,
                            "questao": questao_txt,
                            "resposta_final": "",
                            "passos_resolucao": [],
                            "conceitos_aplicados": [],
                            "erros_comuns": [],
                            "criterios_correcao": "",
                            "alternativas": {}
                        }
                        if not isinstance(item, dict):
                            item = {}
                        base.update({k: v for k, v in item.items() if v is not None})

                        # Sanitiza letra
                        if base.get("alternativa_correta_letra") not in ["A","B","C","D","E"]:
                            base["alternativa_correta_letra"] = "A"

                        items.append(base)
                    except Exception as e:
                        logger.warning(f"Falha no item {idx} do gabarito: {e}")
                if items:
                    gabarito = {"gabarito": items}

            # 3) Último recurso: texto livre
            if not gabarito:
                gabarito = {
                    "gabarito": [],
                    "observacao": "Gabarito gerado em formato texto",
                    "texto_completo": output or ""
                }

            # 4) Persiste no banco diretamente (independente do LLM/tool)
            try:
                self._save_gabarito_to_db(session_id, gabarito)
            except Exception as e:
                logger.warning(f"Falha ao salvar gabarito no banco: {e}")

            logger.info("Agente Resolução concluído")
            return gabarito

        except Exception as e:
            logger.error(f"Erro no Agente Resolução: {e}")
            raise

    def _parse_number(self, s: Any) -> Optional[float]:
        try:
            if s is None:
                return None
            if isinstance(s, (int, float)):
                return float(s)
            txt = str(s).strip()
            txt = txt.replace("%", "")
            txt = txt.replace(",", ".")
            m = re.findall(r"[-+]?[0-9]*\.?[0-9]+", txt)
            if not m:
                return None
            return float(m[0])
        except Exception:
            return None

    def _numeric_equiv(self, a: Any, b: Any, tol: float = 1e-2) -> Optional[bool]:
        va = self._parse_number(a)
        vb = self._parse_number(b)
        if va is None or vb is None:
            return None
        try:
            return abs(va - vb) <= tol
        except Exception:
            return None

    async def _julgar_equivalencia(self, questao: str, resp_a: str, resp_b: str) -> bool:
        try:
            from langchain_core.prompts import ChatPromptTemplate
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Você é um juiz matemático rigoroso. Julgue se as duas respostas são matematicamente equivalentes. Considere: tolerância numérica ±0,01; equivalência algébrica (ex.: 2x+4 == 4+2x); sinonímia textual quando apropriado. Responda apenas em JSON conforme o schema."),
                ("human", (
                    "Questão:\n{questao}\n\n"
                    "Resposta A:\n{a}\n\n"
                    "Resposta B:\n{b}\n\n"
                    "Diga se são equivalentes."
                )),
            ])
            data = await (prompt | self.llm_julgamento_json).ainvoke({
                "questao": questao,
                "a": str(resp_a),
                "b": str(resp_b),
            })
            if hasattr(data, "model_dump"):
                payload = data.model_dump()
            elif isinstance(data, dict):
                payload = data
            else:
                payload = {}
            return bool(payload.get("equivalentes", False))
        except Exception as e:
            logger.warning(f"Falha no juiz de equivalência (LLM): {e}")
            return False

    async def _resolver_item_independente(self, numero: int, questao_txt: str, variante: str = "A") -> Dict[str, Any]:
        # Resolve uma única questão sem acesso a gabaritos prévios
        prompts = self.prompts['resolucao']
        from langchain_core.prompts import ChatPromptTemplate
        item_prompt = ChatPromptTemplate.from_messages([
            ("system", prompts['system']),
            ("human", (
                "Resolva a questão abaixo de forma independente e retorne EXCLUSIVAMENTE o objeto JSON dessa questão.\n\n"
                "Número da questão: {numero}\nVariante independente: {variante}\n"
                "Questão:\n{questao}\n\n"
                "Inclua: 'resposta_final', 'passos_resolucao', 'alternativa_correta_letra' (A–E) e, se possível, 'alternativas' (mapa a–e)."
            )),
        ])
        try:
            if getattr(self, "llm_item_json", None) is None:
                raise RuntimeError("llm_item_json indisponível")
            data = await (item_prompt | self.llm_item_json).ainvoke({
                "numero": numero,
                "questao": questao_txt,
                "variante": variante,
            })
            if hasattr(data, "model_dump"):
                item = data.model_dump()
            elif isinstance(data, dict):
                item = data
            else:
                item = {}
        except Exception as e:
            logger.error(f"ERRO ao resolver item {numero} ({variante}): {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            item = {}
        # Normaliza base
        base = {
            "numero_questao": numero,
            "questao": questao_txt,
            "resposta_final": "",
            "passos_resolucao": [],
            "conceitos_aplicados": [],
            "erros_comuns": [],
            "criterios_correcao": "",
            "alternativa_correta_letra": None,
            "alternativas": {}
        }
        if isinstance(item, dict):
            base.update({k: v for k, v in item.items() if v is not None})
        if base.get("alternativa_correta_letra") not in ["A","B","C","D","E"]:
            base["alternativa_correta_letra"] = "A"
        return base

    async def gerar_distratores(self, enunciado: str, resposta_final: str, n: int = 4) -> List[str]:
        """Gera n distratores plausíveis para a questão, evitando a resposta correta."""
        candidatos: List[str] = []
        try:
            # 1) Tenta via agente (texto -> JSON)
            result = await self._run_agent(
                self.agente_distratores,
                self.prompts['distratores']['human'],
                {
                    "enunciado": enunciado,
                    "resposta_correta": str(resposta_final),
                    "n": n,
                }
            )
            output = self._extract_output_text(result)
            output = self._maybe_unfence_json(output)
            try:
                parsed = json.loads(output)
                if isinstance(parsed, dict) and isinstance(parsed.get("distratores"), list):
                    candidatos = [str(x).strip() for x in parsed["distratores"] if str(x).strip()]
            except Exception:
                pass
        except Exception:
            pass

        # 2) Fallback estruturado (JSON schema)
        if not candidatos and getattr(self, "llm_distratores_json", None) is not None:
            from langchain_core.prompts import ChatPromptTemplate
            prompts = self.prompts['distratores']
            prompt = ChatPromptTemplate.from_messages([
                ("system", prompts['system']),
                ("human", prompts['human'])
            ])
            try:
                data = await (prompt | self.llm_distratores_json).ainvoke({
                    "enunciado": enunciado,
                    "resposta_correta": str(resposta_final),
                    "n": n,
                })
                payload = data.model_dump() if hasattr(data, "model_dump") else (data if isinstance(data, dict) else {})
                candidatos = [str(x).strip() for x in payload.get("distratores", []) if str(x).strip()]
            except Exception:
                candidatos = []

        # 3) Último recurso: heurística simples
        def _num(x: Any) -> Optional[float]:
            try:
                t = str(x).replace('%','').replace(',','.')
                m = re.findall(r"[-+]?[0-9]*\.?[0-9]+", t)
                return float(m[0]) if m else None
            except Exception:
                return None
        if len(candidatos) < n:
            base_n = _num(resposta_final)
            extras: List[str] = []
            if base_n is not None:
                # Gera perturbações numéricas
                for mult in [0.9, 1.1, 0.8, 1.2, 0.95, 1.05]:
                    extras.append(str(round(base_n*mult, 3)))
            else:
                # Gera variações textuais simples
                rf = str(resposta_final).strip()
                extras = [
                    f"{rf} (incompleto)",
                    f"{rf} + 1",
                    f"{rf} - 1",
                    f"opção semelhante porém incorreta"
                ]
            # Completa até n
            for e in extras:
                if len(candidatos) >= n:
                    break
                if str(e).strip() and str(e).strip().lower() != str(resposta_final).strip().lower():
                    candidatos.append(str(e).strip())

        # Dedup e corta
        seen = set()
        out = []
        for c in candidatos:
            key = c.lower().strip()
            if key and key != str(resposta_final).lower().strip() and key not in seen:
                seen.add(key)
                out.append(c)
        return out[:max(0, n)]

    def _embaralhar_alternativas(self, resposta_correta: str, distratores: List[str]) -> Tuple[Dict[str, str], str]:
        """Monta mapa A–E embaralhado e retorna (alternativas_map, letra_correta)."""
        pool = [str(resposta_correta).strip()] + [str(d).strip() for d in distratores]
        # Dedup preservando correta
        dedup = []
        seen = set()
        for x in pool:
            k = x.lower().strip()
            if not k:
                continue
            if k not in seen:
                seen.add(k)
                dedup.append(x)
        # Completa até 5 com placeholders se necessário
        while len(dedup) < 5:
            dedup.append(f"opção {len(dedup)+1}")
        # Limita a 5: 1 correta + 4 distratores
        dedup = dedup[:5]
        # Embaralha
        random.shuffle(dedup)
        letras = ["A","B","C","D","E"]
        alt_map = {letras[i]: dedup[i] for i in range(5)}
        # Encontra a letra correta
        letra_certa = next((L for L, txt in alt_map.items() if txt.strip().lower() == str(resposta_correta).strip().lower()), None)
        if not letra_certa:
            # Se a correta foi alterada por normalização, força posição A
            alt_map["A"] = str(resposta_correta).strip()
            letra_certa = "A"
        return alt_map, letra_certa

    async def _completar_e_embaralhar_alternativas(self, questoes: List[Dict[str, Any]], gabarito: Dict[str, Any]) -> Dict[str, Any]:
        """Garante que cada item do gabarito tenha 5 alternativas (A–E) com a correta embaralhada."""
        if not isinstance(gabarito, dict) or not isinstance(gabarito.get("gabarito"), list):
            return gabarito
        itens = gabarito.get("gabarito", [])
        for idx, item in enumerate(itens):
            try:
                alt_map = item.get("alternativas") or {}
                tem_5 = isinstance(alt_map, dict) and len(alt_map.keys()) >= 5
                resp_correta = item.get("resposta_final", "")
                if not resp_correta:
                    continue
                if not tem_5:
                    # Gera distratores
                    enun = None
                    if idx < len(questoes):
                        enun = (questoes[idx] or {}).get("enunciado")
                    if not enun:
                        enun = item.get("questao", "")
                    distr = await self.gerar_distratores(enun or "", resp_correta, n=4)
                    alt_map, letra = self._embaralhar_alternativas(resp_correta, distr)
                    item["alternativas"] = alt_map
                    item["alternativa_correta_letra"] = letra
                else:
                    # Já existe, apenas normaliza letra
                    letra = item.get("alternativa_correta_letra")
                    if str(letra).upper() not in ["A","B","C","D","E"]:
                        # tenta inferir
                        alvo = str(resp_correta).strip().lower()
                        letra = next((L for L, v in alt_map.items() if str(v).strip().lower() == alvo), "A")
                        item["alternativa_correta_letra"] = letra
            except Exception as e:
                logger.warning(f"Falha ao completar alternativas do item {idx+1}: {e}")
        return gabarito




    async def gerar_questoes_validadas(
        self,
        questao_original: str,
        habilidades_identificadas: List[Dict],
        conceitos_principais: List[str],
        ano_escolar: str,
        alvo: int = 3,
        max_tentativas: int = 3,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Gera questões (criador) com gabarito do criador (oculto ao resolvedor), valida solvabilidade
        comparando a resposta do Agente de Resolução (independente) com a resposta do criador
        usando equivalência numérica/semântica. Se o criador não fornecer gabarito, cai no
        fallback de dupla resolução independente. Retorna até `alvo` questões aprovadas + gabarito mestre.
        """
        aprovadas: List[Dict[str, Any]] = []
        tentativa = 0
        while len(aprovadas) < alvo and tentativa < max_tentativas:
            tentativa += 1
            batch = await self.criar_questoes(
                questao_original=questao_original,
                habilidades_identificadas=habilidades_identificadas,
                conceitos_principais=conceitos_principais,
                ano_escolar=ano_escolar,
            )
            for q in batch:
                if len(aprovadas) >= alvo:
                    break
                enun = str(q.get("enunciado", "")).strip()
                if not enun:
                    logger.warning(f"Questão {q.get('numero', '?')} sem enunciado, pulando")
                    continue

                logger.info(f"Validando questão {q.get('numero', '?')}: {enun[:80]}...")

                # Preferencia: comparar solucao independente com o gabarito do criador (sem expor ao resolvedor)
                resposta_criador = str(q.get("resposta_correta_criador") or q.get("resposta_correta") or "").strip()
                consistente = False

                if resposta_criador:
                    logger.info(f"  Criador forneceu gabarito: {resposta_criador}")
                    item_s = await self._resolver_item_independente(q.get("numero", len(aprovadas)+1), enun, variante="S")
                    resp_solver = item_s.get("resposta_final", "")
                    logger.info(f"  Solver resolveu: {resp_solver}")

                    num_eq = self._numeric_equiv(resposta_criador, resp_solver)
                    if num_eq is True:
                        logger.info(f"  ✓ Validação numérica OK")
                        consistente = True
                    elif num_eq is False:
                        logger.warning(f"  ✗ Validação numérica falhou: {resposta_criador} ≠ {resp_solver}")
                        consistente = False
                    else:
                        # Julgamento semantico/algebrico
                        logger.info(f"  Tentando validação semântica...")
                        consistente = await self._julgar_equivalencia(enun, resposta_criador, resp_solver)
                        logger.info(f"  Validação semântica: {consistente}")
                else:
                    logger.info(f"  Criador NÃO forneceu gabarito, usando dupla resolução independente")
                    # Fallback: dupla resolucao independente A vs B
                    item_a = await self._resolver_item_independente(q.get("numero", len(aprovadas)+1), enun, variante="A")
                    item_b = await self._resolver_item_independente(q.get("numero", len(aprovadas)+1), enun, variante="B")
                    # 1) Letras iguais
                    letra_a = (item_a.get("alternativa_correta_letra") or "").upper()
                    letra_b = (item_b.get("alternativa_correta_letra") or "").upper()
                    logger.info(f"  Solver A: letra={letra_a}, resposta={item_a.get('resposta_final', '')}")
                    logger.info(f"  Solver B: letra={letra_b}, resposta={item_b.get('resposta_final', '')}")

                    if letra_a in ["A","B","C","D","E"] and letra_a == letra_b:
                        logger.info(f"  ✓ Letras iguais: {letra_a}")
                        consistente = True
                    else:
                        # 2) Numerica
                        num_eq = self._numeric_equiv(item_a.get("resposta_final"), item_b.get("resposta_final"))
                        if num_eq is True:
                            logger.info(f"  ✓ Validação numérica OK")
                            consistente = True
                        elif num_eq is False:
                            logger.warning(f"  ✗ Validação numérica falhou")
                            consistente = False
                        else:
                            # 3) Julgamento via LLM
                            logger.info(f"  Tentando validação semântica...")
                            consistente = await self._julgar_equivalencia(enun, item_a.get("resposta_final", ""), item_b.get("resposta_final", ""))
                            logger.info(f"  Validação semântica: {consistente}")

                if consistente:
                    logger.info(f"  ✓✓ Questão APROVADA")
                    aprovadas.append({
                        "numero": len(aprovadas) + 1,
                        "enunciado": enun,
                        "habilidades_combinadas": q.get("habilidades_combinadas", [])[:3],
                    })
                else:
                    logger.warning(f"  ✗✗ Questão REJEITADA (validação falhou)")

            # Evita loop apertado
            if len(aprovadas) < alvo:
                await asyncio.sleep(0)

        # Gera gabarito mestre final para aprovadas
        gabarito = await self.resolver_questoes(session_id=str(uuid.uuid4()), questoes=aprovadas)
        # Completa alternativas (distratores) e embaralha
        try:
            gabarito = await self._completar_e_embaralhar_alternativas(aprovadas, gabarito)
        except Exception as e:
            logger.warning(f"Falha ao completar alternativas: {e}")
        return aprovadas, gabarito

    async def corrigir_respostas(
        self,
        session_id: str,
        respostas_aluno: str
    ) -> Dict[str, Any]:

        """
        Agente Correção: Corrige respostas e gera relatório diagnóstico

        Args:
            session_id: ID da sessão
            respostas_aluno: Respostas fornecidas pelo aluno

        Returns:
            Relatório diagnóstico completo
        """
        logger.info("Executando Agente Correção")

        try:
            # 1) Tenta via agente (com tool calling)
            result = await self._run_agent(
                self.agente_correcao,
                self.prompts['correcao']['human'],
                {
                    "session_id": session_id,
                    "respostas_aluno": respostas_aluno
                }
            )

            output = self._extract_output_text(result)
            output = self._maybe_unfence_json(output)

            relatorio: Dict[str, Any] = {}

            # 1a) Parse direto
            if output:
                try:
                    relatorio = json.loads(output)
                except json.JSONDecodeError:
                    pass

            # 2) Fallback estruturado (JSON) passando o gabarito mestre explicitamente
            if (not relatorio) and self.llm_correcao_json is not None:
                logger.info("Fallback estruturado: gerando relatório com JSON schema")
                try:
                    # Recupera gabarito do banco e injeta no prompt
                    gb_dict = self._get_gabarito_from_db(session_id)
                    if not isinstance(gb_dict, dict):
                        try:
                            gb_dict = json.loads(gb_dict)
                        except Exception:
                            gb_dict = {}
                    gb_json = json.dumps(gb_dict, ensure_ascii=False, indent=2)

                    prompts = self.prompts['correcao']
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", prompts['system']),
                        ("human", prompts['human']),
                        ("human", "Gabarito Mestre (JSON):\n{gabarito_mestre}")
                    ])

                    data = await (prompt | self.llm_correcao_json).ainvoke({
                        "session_id": session_id,
                        "respostas_aluno": respostas_aluno,
                        "gabarito_mestre": gb_json
                    })
                    if hasattr(data, "model_dump"):
                        relatorio = data.model_dump()
                    elif isinstance(data, dict):
                        relatorio = data
                except Exception as e:
                    logger.warning(f"Falha no fallback estruturado da correção: {e}")

            # 3) Último recurso
            if not relatorio:
                relatorio = {
                    "resumo": "Relatório gerado",
                    "total_questoes": 3,
                    "total_acertos": 0,
                    "percentual_acerto": 0.0,
                    "correcao_detalhada": [],
                    "habilidades_a_revisar": [],
                    "texto_completo": output or ""
                }

            logger.info("Agente Correção concluído")
            return relatorio

        except Exception as e:
            logger.error(f"Erro no Agente Correção: {e}")
            raise


# Instância global do serviço de agentes
agent_service = AgentService()

