"""
Interface Streamlit para testar o BNCC-Gen

Frontend temporário para validação dos agentes e fluxo completo.
"""
import streamlit as st
import requests
from io import BytesIO

# Configurações
API_BASE_URL = "http://127.0.0.1:8000"

# Configuração da página
st.set_page_config(
    page_title="BNCC-Gen - Teste",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
    }
    .questao-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<h1 class="main-header">🎓 BNCC-Gen - Sistema de Testes</h1>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Status")

    # Status da API
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            st.success("✅ API Online")
        else:
            st.error("❌ API com problemas")
    except:
        st.error("❌ API Offline")
        st.warning("Execute: `uvicorn app.main:app --reload`")

    st.markdown("---")

    # Informações
    st.subheader("📊 Fluxo")
    st.info("""
    **1.** Digite uma questão de matemática

    **2.** Sistema identifica habilidades BNCC

    **3.** Gera 3 questões validadas (Criador → Solver → Validação)

    **4.** Submeta respostas para correção
    """)

    st.markdown("---")

    # Reset
    if st.button("🔄 Nova Sessão", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Inicializa session state
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'questoes' not in st.session_state:
    st.session_state.questoes = None
if 'relatorio' not in st.session_state:
    st.session_state.relatorio = None

# ============================================================
# PASSO 1: CRIAR SESSÃO COM QUESTÃO
# ============================================================

if st.session_state.session_id is None:
    st.header("📝 Passo 1: Digite a Questão Original")

    st.markdown("""
    Digite uma questão de matemática que será usada como base para:
    - **Agente Interpretador**: Identificar habilidades BNCC via RAG
    - **Pipeline**: Criador → Solver → Validação para gerar 3 questões aprovadas
    - **Agente Resolução**: Criar gabarito mestre
    """)

    # Input de texto para a questão
    questao_texto = st.text_area(
        "Questão de Matemática:",
        height=200,
        placeholder="Digite aqui a questão do aluno (texto)",
        help="Digite a questão que será analisada pelos agentes"
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        if st.button("🚀 Iniciar Sessão e Gerar Questões", type="primary", use_container_width=True):
            if not questao_texto or len(questao_texto.strip()) < 10:
                st.error("❌ Por favor, digite uma questão válida (mínimo 10 caracteres)")
            else:
                with st.spinner("🔄 Processando... Agentes trabalhando (pode levar até 2 minutos)"):
                    try:
                        # Cria um arquivo fake com o texto da questão
                        files = {'file': ('questao.txt', BytesIO(questao_texto.encode('utf-8')), 'text/plain')}

                        # Chama a API
                        response = requests.post(
                            f"{API_BASE_URL}/api/v1/session/start",
                            files=files,
                            timeout=180  # 3 minutos para os agentes processarem
                        )

                        if response.status_code == 200:
                            data = response.json()
                            st.session_state.session_id = data['session_id']
                            st.session_state.questoes = data['lista_de_questoes']

                            st.success("✅ Sessão criada com sucesso!")
                            st.balloons()
                            st.rerun()
                        else:
                            error_detail = response.json().get('detail', response.text) if response.headers.get('content-type') == 'application/json' else response.text
                            st.error(f"❌ Erro: {response.status_code}")
                            st.code(error_detail, language="text")

                    except requests.exceptions.Timeout:
                        st.error("⏱️ Timeout: Os agentes demoraram muito. Verifique os logs da API.")
                    except Exception as e:
                        st.error(f"❌ Erro ao conectar com a API: {str(e)}")

    st.markdown("---")
    st.info("💡 **Dica:** Após criar a sessão, você verá as 3 questões validadas e poderá submeter respostas para correção.")

# ============================================================
# PASSO 2: VISUALIZAR QUESTÕES GERADAS
# ============================================================

elif st.session_state.relatorio is None:
    st.header("📋 Passo 2: Questões Geradas")

    st.success(f"✅ **Session ID:** `{st.session_state.session_id}`")

    st.markdown("""
    O sistema analisou a questão original e gerou 3 questões validadas (consistentes).
    Agora você pode submeter as respostas do aluno para correção automática.
    """)

    st.markdown("---")

    # Mostra as questões geradas com alternativas
    st.subheader("📝 Questões Geradas pelo Sistema (Múltipla Escolha)")

    # Busca dados completos da sessão (questões + gabarito com alternativas)
    try:
        resp = requests.get(f"{API_BASE_URL}/api/v1/session/{st.session_state.session_id}", timeout=30)
        sess = resp.json() if resp.status_code == 200 else {}
        questoes_obj = sess.get('lista_questoes', []) or []
        gabarito = (sess.get('gabarito_mestre') or {}).get('gabarito', [])
    except Exception as e:
        st.error(f"❌ Erro ao buscar dados da sessão: {str(e)}")
        questoes_obj, gabarito = [], []

    if 'user_answers' not in st.session_state:
        st.session_state.user_answers = {}

    letras = ["A","B","C","D","E"]

    # Fallback: se não vierem objetos de questões do GET, usa a lista textual da criação
    if not questoes_obj and st.session_state.get('questoes'):
        import re as _re
        questoes_obj = []
        for i, s in enumerate(st.session_state.questoes, 1):
            txt = str(s)
            m = _re.match(r"^\s*\d+[\.)\-]\s*(.*)$", txt)
            enun = m.group(1).strip() if m else txt.strip()
            questoes_obj.append({"numero": i, "enunciado": enun, "habilidades_combinadas": []})

    for i, q in enumerate(questoes_obj, 1):
        enun = q.get('enunciado') if isinstance(q, dict) else str(q)
        alt_map = {}
        if i-1 < len(gabarito):
            gb_item = gabarito[i-1] or {}
            alt_map = gb_item.get('alternativas') or {}
        # Garante rótulos
        opcoes = []
        for L in letras:
            label = alt_map.get(L) or f"Alternativa {L}"
            opcoes.append(f"{L}) {label}")
        with st.expander(f"📌 Questão {i}", expanded=True):
            st.markdown(f"<div class='questao-box'>{enun}</div>", unsafe_allow_html=True)
            sel = st.radio(
                f"Sua resposta para a questão {i}:",
                options=letras,
                format_func=lambda x: f"{x}) {alt_map.get(x) or ''}",
                key=f"q_{i}"
            )
            st.session_state.user_answers[str(i)] = sel

    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        if st.button("📤 Submeter para Correção", type="primary", use_container_width=True):
            if not st.session_state.user_answers or len(st.session_state.user_answers) == 0:
                st.error("❌ Por favor, selecione as alternativas para as 3 questões")
            else:
                with st.spinner("🔄 Corrigindo... Agente de Correção trabalhando"):
                    try:
                        payload = {"respostas": st.session_state.user_answers}
                        response = requests.post(
                            f"{API_BASE_URL}/api/v1/session/{st.session_state.session_id}/submit",
                            json=payload,
                            timeout=180
                        )

                        if response.status_code == 200:
                            data = response.json()
                            st.session_state.relatorio = data['relatorio_diagnostico']

                            st.success("✅ Respostas corrigidas com sucesso!")
                            st.balloons()
                            st.rerun()
                        else:
                            error_detail = response.json().get('detail', response.text) if response.headers.get('content-type') == 'application/json' else response.text
                            st.error(f"❌ Erro: {response.status_code}")
                            st.code(error_detail, language="text")

                    except requests.exceptions.Timeout:
                        st.error("⏱️ Timeout: O agente de correção demorou muito.")
                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")

# ============================================================
# PASSO 3: VISUALIZAR RELATÓRIO DIAGNÓSTICO
# ============================================================

else:
    st.header("📊 Relatório Diagnóstico")

    st.success(f"✅ **Session ID:** `{st.session_state.session_id}`")

    relatorio = st.session_state.relatorio

    # Busca dados completos da sessão (questões + gabarito com alternativas)
    try:
        resp = requests.get(f"{API_BASE_URL}/api/v1/session/{st.session_state.session_id}", timeout=30)
        sess = resp.json() if resp.status_code == 200 else {}
        questoes_obj = sess.get('lista_questoes', []) or []
        gabarito = (sess.get('gabarito_mestre') or {}).get('gabarito', [])
    except Exception as e:
        st.warning(f"Não foi possível carregar detalhes da sessão: {e}")
        questoes_obj, gabarito = [], []

    # Métricas principais
    st.markdown("### 📈 Desempenho Geral")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("� Total de Questões", relatorio.get('total_questoes', 0))
    with col2:
        st.metric("✅ Acertos", relatorio.get('total_acertos', 0))
    with col3:
        st.metric("❌ Erros", relatorio.get('total_questoes', 0) - relatorio.get('total_acertos', 0))
    with col4:
        percentual = relatorio.get('percentual_acerto', 0)
        st.metric("📊 Percentual", f"{percentual}%")

    st.markdown("---")

    # Resumo
    st.markdown("### 📝 Resumo do Diagnóstico")
    st.info(relatorio.get('resumo', 'Sem resumo disponível'))

    st.markdown("---")

    # Gabarito mestre (opcional)
    with st.expander("📘 Ver Gabarito Mestre (com alternativas)", expanded=False):
        if gabarito:
            letras = ["A", "B", "C", "D", "E"]
            for i, gb in enumerate(gabarito, start=1):
                alt_map = gb.get('alternativas') or {}
                letra = (gb.get('alternativa_correta_letra') or '').upper()
                texto = alt_map.get(letra) or gb.get('resposta_final', '')
                st.markdown(f"**Questão {i}:** Letra {letra} — {texto}")
        else:
            st.write("Gabarito não disponível.")

    # Correção detalhada
    if relatorio.get('correcao_detalhada'):
        st.markdown("### ✅ Correção Detalhada por Questão")
        letras = ["A", "B", "C", "D", "E"]
        user_answers = st.session_state.get('user_answers', {})
        n = max(len(gabarito), len(relatorio['correcao_detalhada']))
        for idx in range(n):
            num = idx + 1
            q_obj = questoes_obj[idx] if idx < len(questoes_obj) else {}
            enun = q_obj.get('enunciado', f"Questão {num}")
            habilidades = q_obj.get('habilidades_combinadas', [])
            gb = gabarito[idx] if idx < len(gabarito) else {}
            corr = relatorio['correcao_detalhada'][idx] if idx < len(relatorio['correcao_detalhada']) else {}

            alt_map = gb.get('alternativas') or {}
            letra_certa = (gb.get('alternativa_correta_letra') or '').upper()
            texto_certo = alt_map.get(letra_certa) or gb.get('resposta_final', '')

            sua_letra = (user_answers.get(str(num)) or str(corr.get('sua_resposta', '')).strip()).upper()
            sua_texto = alt_map.get(sua_letra) or corr.get('sua_resposta', '')

            acertou = corr.get('acertou')
            if acertou is None and letra_certa in letras and sua_letra in letras:
                acertou = (sua_letra == letra_certa)
            status = "Acertou" if acertou else "Errou"

            icon = "✅" if acertou else "❌"
            with st.expander(f"{icon} Questão {num} - {status}", expanded=True):
                st.markdown(f"**Enunciado:** {enun}")
                st.markdown(f"**Sua resposta:** {sua_letra or 'N/D'} — {sua_texto}")
                st.markdown(f"**Gabarito:** {letra_certa or 'N/D'} — {texto_certo}")
                if habilidades:
                    st.markdown("**Habilidades BNCC:** " + ", ".join(habilidades))
                st.markdown(f"**Feedback:** {corr.get('feedback', 'N/A')}")
                passos = gb.get('passos_resolucao') or []
                if passos:
                    with st.expander("🧠 Ver solução detalhada", expanded=False):
                        for p in passos:
                            st.markdown(f"- {p}")

    st.markdown("---")

    # Habilidades a revisar
    if 'habilidades_a_revisar' in relatorio and relatorio['habilidades_a_revisar']:
        st.markdown("### 📚 Habilidades BNCC a Revisar")

        for hab in relatorio['habilidades_a_revisar']:
            st.warning(f"📌 {hab}")
    else:
        st.success("🎉 Parabéns! Todas as habilidades foram dominadas!")

    st.markdown("---")

    # Botão para nova sessão
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Iniciar Nova Sessão", type="primary", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🎓 BNCC-Gen v1.0.0 | Interface de Testes</p>
    <p>Desenvolvido com Streamlit + FastAPI + LangChain + Google Gemini + ChromaDB</p>
</div>
""", unsafe_allow_html=True)

