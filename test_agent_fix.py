
from typing import Dict, Any, List


from fastapi.testclient import TestClient

from app.main import app
from app.services.agent_service import agent_service

QUESTION_TEXT = (
    "O arquiteto Renzo Piano exibiu a maquete da nova\n"
    "sede do Museu Whitney de Arte Americana, um prédio\n"
    "assimétrico que tem um vão aberto para a galeria principal,\n"
    "cuja medida da área é 1 672 m 2 .\n"
    "Considere que a escala da maquete exibida é 1 : 200.\n"
    "Época, n. 682, jun. 2011 (adaptado).\n"
    "A medida da área do vão aberto nessa maquete, em\n"
    "centímetro quadrado, é"
)


def test_backend_flow_e2e_with_patched_agents(monkeypatch):
    """Fluxo backend: /start -> /session -> /submit (mock dos agentes para não chamar LLM)."""
    habilidades_id = {
        "habilidades_identificadas": [
            {"codigo": "EM13MAT101", "descricao": "Escalas e proporcionalidade"},
            {"codigo": "EM13MAT201", "descricao": "Áreas e medidas"},
        ],
        "conceitos_principais": ["escala", "área", "conversão de unidades"],
        "ano_recomendado": "9º ano",
    }

    def _fake_item(i: int) -> Dict[str, Any]:
        enun = f"Questão {i}: Sobre escala e áreas em maquetes, determine a medida pedida."
        alternativas = {"A": "418 cm²", "B": "400 cm²", "C": "500 cm²", "D": "318 cm²", "E": "450 cm²"}
        return {
            "numero_questao": i,
            "questao": enun,
            "resposta_final": "418 cm²",
            "passos_resolucao": [
                "(1/200)^2 = 1/40000",
                "1672 m² / 40000 = 0,0418 m²",
                "0,0418 m² = 418 cm²",
            ],
            "conceitos_aplicados": ["escala", "área", "unidades"],
            "erros_comuns": ["escalar linear", "erro de m²→cm²"],
            "criterios_correcao": "Aceitar 418 cm² (±1).",
            "alternativa_correta_letra": "A",
            "alternativas": alternativas,
        }

    aprovadas_sim: List[Dict[str, Any]] = [
        {"numero": 1, "enunciado": _fake_item(1)["questao"], "habilidades_combinadas": ["EM13MAT101", "EM13MAT201"]},
        {"numero": 2, "enunciado": _fake_item(2)["questao"], "habilidades_combinadas": ["EM13MAT101", "EM13MAT201"]},
        {"numero": 3, "enunciado": _fake_item(3)["questao"], "habilidades_combinadas": ["EM13MAT101", "EM13MAT201"]},
    ]
    gabarito_sim: Dict[str, Any] = {"gabarito": [_fake_item(1), _fake_item(2), _fake_item(3)]}

    async def fake_interpretar_questao(txt: str):
        return habilidades_id

    async def fake_gerar_questoes_validadas(questao_original: str, habilidades_identificadas, conceitos_principais, ano_escolar, alvo: int = 3, max_tentativas: int = 3):
        return aprovadas_sim[:alvo], gabarito_sim

    async def fake_corrigir_respostas(session_id: str, respostas_aluno: str):
        escolha_map: Dict[str, str] = {}
        for ln in (respostas_aluno or "").splitlines():
            try:
                left, right = ln.split(":", 1)
                num = left.split()[-1].strip()
                letra = right.strip().upper()[:1]
                escolha_map[num] = letra
            except Exception:
                continue
        correcao = []
        total = len(gabarito_sim["gabarito"]) or 0
        acertos = 0
        for item in gabarito_sim["gabarito"]:
            i = str(item["numero_questao"])
            letra_certa = item.get("alternativa_correta_letra")
            alt = item.get("alternativas", {})
            sua = escolha_map.get(i)
            acertou = bool(sua and letra_certa and sua == letra_certa)
            if acertou:
                acertos += 1
            correcao.append({
                "questao": item.get("questao", f"Questão {i}"),
                "sua_resposta": f"{sua}) {alt.get(sua, '')}" if sua else "(não respondida)",
                "gabarito_correto": f"{letra_certa}) {alt.get(letra_certa, '')}" if letra_certa else "N/D",
                "feedback": "Revise escala e conversão de unidades." if not acertou else "Ótimo!",
                "acertou": acertou,
                "tipo_erro": "conceitual" if not acertou else "",
            })
        return {
            "resumo": f"Você acertou {acertos} de {total} ({(acertos/total*100 if total else 0):.0f}%).",
            "total_questoes": total,
            "total_acertos": acertos,
            "percentual_acerto": round(acertos/total*100, 1) if total else 0,
            "correcao_detalhada": correcao,
            "habilidades_a_revisar": ["EM13MAT101", "EM13MAT201"] if acertos < total else [],
            "pontos_fortes": ["EM13MAT101", "EM13MAT201"] if acertos > 0 else [],
            "recomendacoes": "Pratique escala (área) e m²↔cm².",
        }

    monkeypatch.setattr(agent_service, "interpretar_questao", fake_interpretar_questao, raising=True)
    monkeypatch.setattr(agent_service, "gerar_questoes_validadas", fake_gerar_questoes_validadas, raising=True)
    monkeypatch.setattr(agent_service, "corrigir_respostas", fake_corrigir_respostas, raising=True)

    with TestClient(app) as client:
        files = {"file": ("questao.txt", QUESTION_TEXT.encode("utf-8"), "text/plain")}
        r = client.post("/api/v1/session/start", files=files)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("session_id")
        assert isinstance(data.get("lista_de_questoes"), list) and len(data["lista_de_questoes"]) == 3
        sid = data["session_id"]

        r2 = client.get(f"/api/v1/session/{sid}")
        assert r2.status_code == 200, r2.text
        sess = r2.json()
        gb = (sess.get("gabarito_mestre") or {}).get("gabarito")
        assert isinstance(gb, list) and len(gb) == 3 and isinstance(gb[0].get("alternativas"), dict)

        respostas = {"respostas": {"1": "A", "2": "B", "3": "C"}}
        r3 = client.post(f"/api/v1/session/{sid}/submit", json=respostas)
        assert r3.status_code == 200, r3.text
        res = r3.json()
        rel = res.get("relatorio_diagnostico")
        assert rel and rel.get("total_questoes") == 3
        assert rel.get("total_acertos") == 1
        assert isinstance(rel.get("correcao_detalhada"), list) and len(rel["correcao_detalhada"]) == 3
