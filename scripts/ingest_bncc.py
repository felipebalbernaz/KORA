"""
Script para ingestão dos dados da BNCC no ChromaDB

Executa UMA ÚNICA VEZ para popular o banco vetorial com as habilidades de Matemática.
"""
import json
import os
from pathlib import Path
from typing import List, Dict
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configurações
DATA_DIR = Path("data/Matemática")
CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "bncc_matematica"
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "google")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/embedding-001")


def carregar_arquivos_bncc() -> List[Dict]:
    """
    Carrega todos os arquivos JSON da BNCC de Matemática
    
    Returns:
        Lista de dicionários com as habilidades
    """
    print("📚 Carregando arquivos da BNCC...")
    
    todas_habilidades = []
    arquivos = sorted(DATA_DIR.glob("*.json"))
    
    for arquivo in arquivos:
        print(f"  Lendo: {arquivo.name}")
        
        with open(arquivo, 'r', encoding='utf-8') as f:
            habilidades = json.load(f)
            todas_habilidades.extend(habilidades)
    
    print(f"✓ Total de habilidades carregadas: {len(todas_habilidades)}")
    return todas_habilidades


def criar_documentos(habilidades: List[Dict]) -> List[Document]:
    """
    Converte habilidades BNCC em documentos LangChain
    
    Estratégia: Cada habilidade = 1 documento (chunk)
    
    Args:
        habilidades: Lista de habilidades BNCC
        
    Returns:
        Lista de documentos LangChain
    """
    print("\n📝 Criando documentos...")
    
    documentos = []
    
    for hab in habilidades:
        # Cria o conteúdo do documento
        page_content = f"""
Ano: {hab.get('ano', 'N/A')}
Unidade Temática: {hab.get('unidades_tematicas', 'N/A')}
Objeto de Conhecimento: {hab.get('objetos_de_conhecimento', 'N/A')}
Código BNCC: {hab.get('codigo_bncc', 'N/A')}
Habilidade: {hab.get('habilidade_bncc', 'N/A')}
        """.strip()
        
        # Metadata para filtros
        metadata = {
            "componente": hab.get('componente', 'Matemática'),
            "ano": hab.get('ano', 'N/A'),
            "unidade_tematica": hab.get('unidades_tematicas', 'N/A'),
            "objeto_conhecimento": hab.get('objetos_de_conhecimento', 'N/A'),
            "codigo_bncc": hab.get('codigo_bncc', 'N/A')
        }
        
        # Adiciona competências se existirem
        if 'competencias_especificas' in hab and hab['competencias_especificas']:
            metadata['competencias_especificas'] = hab['competencias_especificas']
        
        if 'competencias_gerais' in hab and hab['competencias_gerais']:
            metadata['competencias_gerais'] = hab['competencias_gerais']
        
        # Cria o documento
        doc = Document(
            page_content=page_content,
            metadata=metadata
        )
        
        documentos.append(doc)
    
    print(f"✓ {len(documentos)} documentos criados")
    return documentos


def criar_vectorstore(documentos: List[Document]):
    """
    Cria o vectorstore ChromaDB com os documentos

    Args:
        documentos: Lista de documentos LangChain
    """
    print("\n🗄️  Criando banco vetorial ChromaDB...")

    # Verifica se já existe
    if os.path.exists(CHROMA_DIR):
        print(f"⚠️  Diretório {CHROMA_DIR} já existe!")
        resposta = input("Deseja sobrescrever? (s/n): ")
        if resposta.lower() != 's':
            print("❌ Operação cancelada")
            return

        # Remove diretório existente
        import shutil
        shutil.rmtree(CHROMA_DIR)
        print("✓ Diretório anterior removido")

    # Cria embeddings baseado no provedor configurado
    print(f"🔄 Criando embeddings com {EMBEDDING_PROVIDER.upper()} (isso pode demorar alguns minutos)...")

    if EMBEDDING_PROVIDER == "google":
        embeddings = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        print(f"   Modelo: {EMBEDDING_MODEL}")
    else:
        embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        print(f"   Modelo: {EMBEDDING_MODEL}")

    # Cria o vectorstore
    vectorstore = Chroma.from_documents(
        documents=documentos,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_DIR
    )

    print(f"✓ Vectorstore criado em: {CHROMA_DIR}")
    print(f"✓ Collection: {COLLECTION_NAME}")
    print(f"✓ Provedor de embeddings: {EMBEDDING_PROVIDER}")

    # Testa uma busca
    print("\n🔍 Testando busca...")
    results = vectorstore.similarity_search("função quadrática", k=3)

    print(f"✓ Teste de busca retornou {len(results)} resultados")
    if results:
        print("\nPrimeiro resultado:")
        print(f"  Código: {results[0].metadata.get('codigo_bncc')}")
        print(f"  Ano: {results[0].metadata.get('ano')}")
        print(f"  Conteúdo: {results[0].page_content[:150]}...")


def main():
    """Função principal"""
    print("=" * 70)
    print("🎓 BNCC-Gen - Ingestão de Dados da BNCC")
    print("=" * 70)
    
    # Verifica se o diretório de dados existe
    if not DATA_DIR.exists():
        print(f"❌ Erro: Diretório {DATA_DIR} não encontrado!")
        print("   Certifique-se de que os arquivos JSON da BNCC estão no local correto.")
        return
    
    # Verifica se a API key está configurada
    if EMBEDDING_PROVIDER == "google":
        if not os.getenv("GOOGLE_API_KEY"):
            print("❌ Erro: GOOGLE_API_KEY não encontrada!")
            print("   Configure a variável de ambiente no arquivo .env")
            return
    else:
        if not os.getenv("OPENAI_API_KEY"):
            print("❌ Erro: OPENAI_API_KEY não encontrada!")
            print("   Configure a variável de ambiente no arquivo .env")
            return
    
    try:
        # 1. Carrega arquivos
        habilidades = carregar_arquivos_bncc()
        
        # 2. Cria documentos
        documentos = criar_documentos(habilidades)
        
        # 3. Cria vectorstore
        criar_vectorstore(documentos)
        
        print("\n" + "=" * 70)
        print("✅ Ingestão concluída com sucesso!")
        print("=" * 70)
        print("\n📌 Próximos passos:")
        print("   1. Execute: uvicorn app.main:app --reload")
        print("   2. Acesse: http://127.0.0.1:8000/docs")
        print("   3. Teste os endpoints da API")
        print("\n")
        
    except Exception as e:
        print(f"\n❌ Erro durante a ingestão: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

