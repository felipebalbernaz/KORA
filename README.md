# 🎓 BNCC-Gen - Sistema Multiagente de Questões Educacionais

Sistema multiagente de IA projetado para gerar listas de exercícios personalizadas baseadas na **Base Nacional Comum Curricular (BNCC)**. A partir de uma única questão-exemplo, o sistema identifica as habilidades da BNCC associadas e gera uma nova lista de estudo focada nesses objetivos pedagógicos.

Este documento descreve a arquitetura do **MVP (Minimum Viable Product)**, focado na lógica central dos agentes com **tool calling**, **RAG (Retrieval-Augmented Generation)** e **prompts modularizados**.

---

## 📑 Índice

1. [Visão Geral e Arquitetura](#-1-visão-geral-e-arquitetura)
2. [Estrutura do Projeto](#-2-estrutura-do-projeto)
3. [Configuração e Instalação](#️-3-configuração-e-instalação)
4. [Executando a Aplicação](#️-4-executando-a-aplicação)
5. [Endpoints da API](#-5-endpoints-da-api)
6. [Sistema de Agentes com Tool Calling](#-6-sistema-de-agentes-com-tool-calling)
7. [Sistema de Prompts Modularizado](#-7-sistema-de-prompts-modularizado)
8. [Sistema RAG - Base de Conhecimento BNCC](#-8-sistema-rag---base-de-conhecimento-bncc)
9. [Como Funciona na Prática](#-9-como-funciona-na-prática)
10. [Benefícios da Arquitetura](#-10-benefícios-da-arquitetura)

---

## 🚀 1. Visão Geral e Arquitetura

O sistema é construído como uma API **FastAPI** e orquestrado com **LangChain**. A principal característica da arquitetura é ser **baseada em sessões** para gerenciar o fluxo assíncrono do usuário (pedir questões e, horas depois, enviar respostas).

### 1.1. Stack Tecnológica

| Componente | Ferramenta | Propósito |
| :--- | :--- | :--- |
| **Servidor API** | **FastAPI** | Para criar endpoints de API rápidos, modernos e assíncronos. |
| **Orquestração de IA**| **LangChain (LCEL)** | Para definir e executar o fluxo de agentes (Interpretador -\> Criador -\> Resolução). |
| **RAG (BNCC)** | **LangChain + ChromaDB** | Para criar uma base de conhecimento vetorial das habilidades da BNCC e permitir a consulta semântica. |
| **Banco (Sessão)** | **SQLite + SQLAlchemy** | Para persistir o estado da sessão (ex: salvar o `gabarito_mestre` gerado). |
| **Validação** | **Pydantic** | Usado nativamente pelo FastAPI para validar dados de entrada e saída. |

### 1.2. Fluxo do Processo

O MVP opera em dois estágios principais:

1.  **Estágio 1: Criação da Sessão (`POST /api/v1/session/start`)**

    1.  O usuário envia uma imagem da `Questão Original`.
    2.  O `ocr_service` (mockado) "lê" a imagem e retorna um texto.
    3.  O `Agente Interpretador` (com RAG-BNCC) analisa o texto e extrai as habilidades.
    4.  O `Agente Criador` gera a `Lista de Questões` com base nessas habilidades.
    5.  O `Agente Resolução` gera o `Gabarito Mestre` para essa lista.
    6.  O `Gabarito Mestre` é **salvo no SQLite** associado a um novo `session_id`.
    7.  A API retorna a `Lista de Questões` e o `session_id` para o usuário.

2.  **Estágio 2: Submissão e Correção (`POST /api/v1/session/{session_id}/submit`)**

    1.  O usuário envia a imagem das suas `Respostas` e o `session_id`.
    2.  O `ocr_service` (mockado) "lê" as respostas.
    3.  O sistema **busca no SQLite** o `Gabarito Mestre` usando o `session_id`.
    4.  O `Agente de Correção` compara as `Respostas` do aluno com o `Gabarito Mestre`.
    5.  A API retorna o `Relatório Diagnóstico` final.

## 📁 2. Estrutura do Projeto

A arquitetura de pastas é organizada para separar responsabilidades (API, Lógica de Negócio, Banco de Dados, Prompts).

```
bncc_gen_backend/
│
├── app/
│   ├── api/v1/endpoints/
│   │   └── session.py           # Rotas da API (/start e /submit)
│   │
│   ├── core/
│   │   └── config.py            # Configurações (.env)
│   │
│   ├── db/
│   │   ├── database.py          # SQLAlchemy setup
│   │   ├── models.py            # Modelos do banco (SessaoEstudo)
│   │   └── schemas.py           # Schemas Pydantic
│   │
│   ├── services/
│   │   ├── agent_service.py     # Agentes com tool calling
│   │   ├── tools.py             # Ferramentas dos agentes
│   │   ├── rag_service.py       # ChromaDB + retriever
│   │   └── ocr_service.py       # Mock OCR
│   │
│   ├── prompts/                 # 📝 Sistema de prompts modularizado
│   │   ├── prompt_loader.py     # Carregador de prompts
│   │   ├── agente_interpretador_system.txt
│   │   ├── agente_interpretador_human.txt
│   │   ├── agente_criador_system.txt
│   │   ├── agente_criador_human.txt
│   │   ├── agente_resolucao_system.txt
│   │   ├── agente_resolucao_human.txt
│   │   ├── agente_correcao_system.txt
│   │   └── agente_correcao_human.txt
│   │
│   └── main.py                  # FastAPI app
│
├── data/Matemática/             # 📚 JSONs da BNCC
│   ├── BNCC 1° Ano - Matemática.json
│   ├── BNCC 2° Ano - Matemática.json
│   ├── ...
│   ├── BNCC 9° Ano - Matemática.json
│   ├── BNCC 1ª Série - Matemática.json
│   ├── BNCC 2ª Série - Matemática.json
│   └── BNCC 3ª Série - Matemática.json
│
├── scripts/
│   └── ingest_bncc.py           # Ingestão do RAG (executar 1x)
│
├── chroma_db/                   # 🗄️ Banco vetorial (criado automaticamente)
│   ├── chroma.sqlite3
│   └── ...
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 🛠️ 3. Configuração e Instalação

### Pré-requisitos

- Python 3.10+
- Chaves de API (OpenAI, Google, etc.) para os LLMs que o LangChain usará

### Passos de Instalação

1. **Clonar o repositório:**
   ```bash
   git clone [URL_DO_SEU_REPOSITORIO]
   cd bncc_gen_backend
   ```

2. **Criar e ativar um ambiente virtual:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # No Windows: .\venv\Scripts\activate
   ```

3. **Instalar as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variáveis de ambiente:**
   - Copie o `.env.example` para um novo arquivo chamado `.env`
   - Preencha as chaves de API necessárias (ex: `OPENAI_API_KEY=...`)

5. **Ingerir dados da BNCC (OBRIGATÓRIO):**
   ```bash
   python scripts/ingest_bncc.py
   ```
   *Isso criará o banco vetorial `./chroma_db/` com todas as habilidades de Matemática.*

6. **Verificar estrutura de prompts:**
   ```bash
   ls app/prompts/
   # Deve mostrar todos os arquivos .txt dos prompts
   ```

7. **Inicializar banco SQLite:**
   *Criado automaticamente na primeira execução*

## ▶️ 4. Executando a Aplicação

Com tudo configurado, inicie o servidor **Uvicorn**:

```bash
uvicorn app.main:app --reload
```

- `app.main`: Refere-se ao arquivo `app/main.py`
- `app`: Refere-se à instância `app = FastAPI()` dentro do arquivo
- `--reload`: Reinicia o servidor automaticamente após salvar alterações no código

**Servidor rodando em**: `http://127.0.0.1:8000`
**Documentação interativa**: `http://127.0.0.1:8000/docs`

---

## 📖 5. Endpoints da API

Documentação interativa (Swagger UI): **`http://127.0.0.1:8000/docs`**

### 5.1. Iniciar Sessão de Estudo

**Rota:** `POST /api/v1/session/start`
**Body:** `form-data` com uma chave `file` (a imagem da questão)
**Resposta (Sucesso 200):**

```json
{
  "session_id": "a1b2-c3d4-e5f6-g7h8",
  "lista_de_questoes": [
    "1. Nova questão gerada pelo Agente Criador...",
    "2. Segunda questão similar...",
    "3. Terceira questão com contexto variado...",
    "4. Quarta questão aplicada..."
  ]
}
```

### 5.2. Submeter Respostas e Obter Relatório

**Rota:** `POST /api/v1/session/{session_id}/submit`
**Parâmetro de URL:** `session_id` (o ID recebido no passo 1)
**Body:** `form-data` com uma chave `file` (a imagem das respostas do aluno)
**Resposta (Sucesso 200):**

```json
{
  "session_id": "a1b2-c3d4-e5f6-g7h8",
  "relatorio_diagnostico": {
    "resumo": "Você acertou 2 de 4 questões. O principal ponto de atenção é a aplicação da habilidade EM13MAT503 em contextos de função quadrática.",
    "correcao_detalhada": [
      {
        "questao": "1. Nova questão...",
        "sua_resposta": "Resposta mockada do aluno...",
        "gabarito_correto": "Gabarito mestre do Agente Resolução...",
        "feedback": "Correto."
      },
      {
        "questao": "2. Segunda questão...",
        "sua_resposta": "Resposta mockada do aluno...",
        "gabarito_correto": "Gabarito mestre...",
        "feedback": "Incorreto. Você confundiu a fórmula do vértice..."
      }
    ]
  }
}
```

---

## 🤖 6. Sistema de Agentes com Tool Calling

O BNCC-Gen utiliza uma arquitetura de **agentes inteligentes** baseada em **tool calling** do LangChain, onde cada agente tem acesso a ferramentas específicas para executar suas tarefas.

### 6.1. Arquitetura de Agentes

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Agente          │    │ Tools            │    │ Prompts         │
│ Interpretador   │◄──►│ • buscar_bncc    │    │ • system.txt    │
│                 │    │ • buscar_conceito│    │ • human.txt     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Agente          │    │ Tools            │    │ • system.txt    │
│ Criador         │◄──►│ • buscar_bncc    │    │ • human.txt     │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Agente          │    │ Tools            │    │ • system.txt    │
│ Resolução       │◄──►│ • salvar_gabarito│    │ • human.txt     │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Agente          │    │ Tools            │    │ • system.txt    │
│ Correção        │◄──►│ • recuperar_gab  │    │ • human.txt     │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### 6.2. Ferramentas (Tools) Disponíveis

| Tool | Função | Agentes que Usam |
|------|--------|------------------|
| `buscar_habilidades_bncc` | Busca semântica por habilidades BNCC | Interpretador, Criador |
| `buscar_por_conceitos` | Busca por conceitos matemáticos específicos | Interpretador |
| `salvar_gabarito_sessao` | Salva gabarito mestre no SQLite | Resolução |
| `recuperar_gabarito_sessao` | Recupera gabarito de uma sessão | Correção |

### 6.3. Fluxo de Tool Calling

1. **Agente Interpretador**:
   - Recebe questão original
   - Chama `buscar_habilidades_bncc(questao_texto)`
   - Pode chamar `buscar_por_conceitos([conceitos])` para refinamento
   - Retorna habilidades BNCC identificadas

2. **Agente Criador**:
   - Recebe habilidades identificadas
   - Pode chamar `buscar_habilidades_bncc()` para contexto adicional
   - Gera 4 questões similares

3. **Agente Resolução**:
   - Resolve todas as questões passo a passo
   - Chama `salvar_gabarito_sessao(session_id, gabarito)`
   - Confirma salvamento no banco

4. **Agente Correção**:
   - Chama `recuperar_gabarito_sessao(session_id)`
   - Compara com respostas do aluno
   - Gera relatório diagnóstico

---

## 📝 7. Sistema de Prompts Modularizado

Os prompts dos agentes são mantidos em arquivos `.txt` separados para facilitar edição e versionamento.

### 7.1. Estrutura de Prompts

```
app/prompts/
├── __init__.py
├── prompt_loader.py                    # Carregador de prompts
├── agente_interpretador_system.txt     # Prompt sistema do interpretador
├── agente_interpretador_human.txt      # Prompt usuário do interpretador
├── agente_criador_system.txt           # Prompt sistema do criador
├── agente_criador_human.txt            # Prompt usuário do criador
├── agente_resolucao_system.txt         # Prompt sistema da resolução
├── agente_resolucao_human.txt          # Prompt usuário da resolução
├── agente_correcao_system.txt          # Prompt sistema da correção
└── agente_correcao_human.txt           # Prompt usuário da correção
```

### 7.2. Carregamento de Prompts

```python
from app.prompts.prompt_loader import prompt_loader

# Carrega um prompt específico
system_prompt = prompt_loader.load_prompt("agente_interpretador_system.txt")

# Carrega todos os prompts
all_prompts = prompt_loader.load_all_prompts()
```

### 7.3. Vantagens da Separação

- ✅ **Edição Fácil**: Modifique prompts sem tocar no código Python
- ✅ **Versionamento**: Controle de versão independente para prompts
- ✅ **Colaboração**: Diferentes pessoas podem trabalhar em prompts e código
- ✅ **Testes A/B**: Fácil comparação entre versões de prompts
- ✅ **Manutenção**: Prompts organizados e documentados

---

## 🔍 8. Sistema RAG - Base de Conhecimento BNCC

O sistema utiliza **Retrieval-Augmented Generation (RAG)** para consultar as habilidades da BNCC de Matemática de forma inteligente.

### 8.1. Estratégia de Chunking

Cada **habilidade BNCC individual** = 1 chunk no banco vetorial:

```json
{
  "page_content": "Ano: 8º\nUnidade Temática: Números\nObjeto: Notação científica\nCódigo: EF08MA01\nHabilidade: Efetuar cálculos com potências...",
  "metadata": {
    "ano": "8º",
    "unidade_tematica": "Números",
    "codigo_bncc": "EF08MA01",
    "componente": "Matemática"
  }
}
```

### 8.2. Banco Vetorial - ChromaDB

**Por que ChromaDB?**
- ✅ **Simplicidade**: Sem configuração de servidor
- ✅ **Persistência**: Salva automaticamente em disco
- ✅ **Integração**: Nativa com LangChain
- ✅ **Performance**: Adequada para ~300 habilidades de matemática
- ✅ **Filtros**: Busca por ano, unidade temática, etc.

### 8.3. Tipos de Busca Implementados

```python
# Busca semântica básica
rag.buscar_habilidades("função quadrática vértice")

# Busca com filtro por ano
rag.buscar_habilidades("geometria", ano_escolar="8º")

# Busca por conceitos específicos
rag.buscar_por_conceito(["função quadrática", "vértice"], "9º")

# Busca avançada com re-ranking
rag.buscar_habilidades_avancada("probabilidade", {"unidade_tematica": "Estatística"})
```

### 8.4. Setup do RAG

1. **Executar ingestão uma única vez**:
   ```bash
   python scripts/ingest_bncc.py
   ```

2. **Estrutura dos dados**:
   ```
   data/Matemática/
   ├── BNCC 1° Ano - Matemática.json
   ├── BNCC 2° Ano - Matemática.json
   ├── ...
   ├── BNCC 9° Ano - Matemática.json
   ├── BNCC 1ª Série - Matemática.json
   ├── BNCC 2ª Série - Matemática.json
   └── BNCC 3ª Série - Matemática.json
   ```

3. **Banco vetorial criado**:
   ```
   ./chroma_db/          # Pasta criada automaticamente
   ├── chroma.sqlite3    # Banco SQLite do ChromaDB
   └── ...              # Arquivos de índice vetorial
   ```



---

## 🧠 9. Como Funciona na Prática

### Exemplo de Fluxo Completo

1. **Usuário envia**: Imagem de questão sobre função quadrática
2. **OCR Mock**: Extrai texto da questão
3. **Agente Interpretador**:
   - Chama `buscar_habilidades_bncc("função quadrática vértice")`
   - Identifica: `EM13MAT503` (pontos de máximo/mínimo)
4. **Agente Criador**: Gera 4 questões similares sobre função quadrática
5. **Agente Resolução**:
   - Resolve as 4 questões passo a passo
   - Chama `salvar_gabarito_sessao(session_id, gabarito)`
6. **Retorna**: Lista de questões + session_id

**Depois, quando o aluno submete respostas**:

7. **Agente Correção**:
   - Chama `recuperar_gabarito_sessao(session_id)`
   - Compara respostas com gabarito
   - Gera relatório diagnóstico personalizado

---

## 🎯 10. Benefícios da Arquitetura

Esta arquitetura garante:

- ✅ **Modularidade**: Cada agente tem responsabilidade única e bem definida
- ✅ **Escalabilidade**: Fácil adicionar novos agentes ou ferramentas
- ✅ **Manutenibilidade**: Prompts separados do código facilitam ajustes
- ✅ **Rastreabilidade**: Tool calling permite debug detalhado das decisões dos agentes
- ✅ **Flexibilidade**: RAG permite consultas inteligentes à BNCC sem hardcoding
- ✅ **Persistência**: Sistema de sessões permite uso assíncrono
- ✅ **Testabilidade**: Componentes isolados facilitam testes unitários

---

## 📚 Referências e Recursos

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangChain Documentation](https://python.langchain.com/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [BNCC - Base Nacional Comum Curricular](http://basenacionalcomum.mec.gov.br/)

---

## 📄 Licença

[Especificar licença do projeto]

---

## 👥 Contribuindo

[Instruções para contribuição]

---

**Desenvolvido com ❤️ para educação brasileira**