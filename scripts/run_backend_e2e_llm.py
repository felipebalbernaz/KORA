import json
import os
import sys
import time
from typing import Dict

# Fix Windows console encoding para suportar Unicode (π, etc.)
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    # Também configura variável de ambiente para subprocessos
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from fastapi.testclient import TestClient

# Garante que o diretrio raiz do repo esteja no sys.path para importar 'app'
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.main import app

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


def _print_header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def run_e2e():
    # Checagem básica de credenciais (apenas aviso)
    provider = os.getenv("DEFAULT_LLM_PROVIDER", "google")
    google_key = os.getenv("GOOGLE_API_KEY")
    if provider == "google" and not google_key:
        print("[AVISO] GOOGLE_API_KEY não encontrado no ambiente. A chamada ao LLM pode falhar.")

    with TestClient(app) as client:
        _print_header("1) Iniciando sessão (/api/v1/session/start)")
        files = {"file": ("questao.txt", QUESTION_TEXT.encode("utf-8"), "text/plain")}
        t0 = time.time()
        r = client.post("/api/v1/session/start", files=files)
        dt = time.time() - t0
        print(f"Status: {r.status_code} | Tempo: {dt:.1f}s")
        if r.status_code != 200:
            print("Erro:", r.text)
            sys.exit(1)
        data = r.json()
        session_id = data.get("session_id")
        print("session_id:", session_id)
        questoes = data.get("lista_de_questoes", [])
        print(f"Questões geradas ({len(questoes)}):")
        for q in questoes:
            print("-", q)

        _print_header("2) Inspecionando sessão (/api/v1/session/{id})")
        r2 = client.get(f"/api/v1/session/{session_id}")
        print("Status:", r2.status_code)
        if r2.status_code != 200:
            print("Erro:", r2.text)
            sys.exit(1)
        sess = r2.json()
        gb = (sess.get("gabarito_mestre") or {}).get("gabarito")
        if isinstance(gb, list):
            print(f"Gabarito mestre possui {len(gb)} itens")
            # Mostra só um resumo das alternativas da primeira questão
            if gb:
                alt = gb[0].get("alternativas", {})
                print("Alternativas Q1 (amostra):", {k: alt.get(k) for k in list(alt.keys())[:5]})
        else:
            print("Gabarito mestre ausente ou inválido:", gb)

        _print_header("3) Submetendo respostas (/api/v1/session/{id}/submit)")
        respostas: Dict[str, str] = {"1": "A", "2": "B", "3": "C"}
        r3 = client.post(
            f"/api/v1/session/{session_id}/submit",
            json={"respostas": respostas}
        )
        print("Status:", r3.status_code)
        if r3.status_code != 200:
            print("Erro:", r3.text)
            sys.exit(1)
        payload = r3.json()
        rel = payload.get("relatorio_diagnostico")
        print("Resumo:", rel.get("resumo"))
        print("Total/Acertos/Percentual:", rel.get("total_questoes"), rel.get("total_acertos"), rel.get("percentual_acerto"))
        print("- Habilidades a revisar:", rel.get("habilidades_a_revisar"))
        print("- Pontos fortes:", rel.get("pontos_fortes"))

        detalhes = rel.get("correcao_detalhada") or []
        print(f"\nCorreção detalhada ({len(detalhes)}):")
        for i, d in enumerate(detalhes, 1):
            print(f"Q{i} | acertou={d.get('acertou')} | sua={d.get('sua_resposta')} | gabarito={d.get('gabarito_correto')}")

        _print_header("Fluxo concluído com sucesso")


if __name__ == "__main__":
    run_e2e()

