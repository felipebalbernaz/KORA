"""
Serviço RAG (Retrieval-Augmented Generation) para busca de habilidades BNCC
"""
from typing import List, Dict, Optional, Any
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class RAGService:
    """
    Serviço para busca semântica de habilidades BNCC usando ChromaDB
    """

    def __init__(self):
        """Inicializa o serviço RAG"""
        # Seleciona o provedor de embeddings
        if settings.EMBEDDING_PROVIDER == "google":
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                google_api_key=settings.GOOGLE_API_KEY
            )
            logger.info(f"Usando Google Gemini Embeddings: {settings.EMBEDDING_MODEL}")
        else:
            self.embeddings = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                openai_api_key=settings.OPENAI_API_KEY
            )
            logger.info(f"Usando OpenAI Embeddings: {settings.EMBEDDING_MODEL}")

        self.vectorstore: Optional[Chroma] = None
        self._load_vectorstore()
    
    def _load_vectorstore(self):
        """Carrega o vectorstore do ChromaDB"""
        try:
            self.vectorstore = Chroma(
                persist_directory=settings.CHROMA_PERSIST_DIRECTORY,
                embedding_function=self.embeddings,
                collection_name="bncc_matematica"
            )
            logger.info("Vectorstore ChromaDB carregado com sucesso")
        except Exception as e:
            logger.warning(f"Vectorstore não encontrado: {e}")
            logger.warning("Execute 'python scripts/ingest_bncc.py' para criar o banco vetorial")
            self.vectorstore = None
    
    def buscar_habilidades(
        self,
        query: str,
        k: int = None,
        filtros: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Busca semântica por habilidades BNCC
        
        Args:
            query: Texto da busca
            k: Número de resultados a retornar (padrão: settings.TOP_K_RESULTS)
            filtros: Filtros de metadata (ex: {"ano": "8º"})
            
        Returns:
            Lista de documentos encontrados
        """
        if self.vectorstore is None:
            logger.error("Vectorstore não inicializado")
            return []
        
        if k is None:
            k = settings.TOP_K_RESULTS
        
        try:
            if filtros:
                results = self.vectorstore.similarity_search(
                    query,
                    k=k,
                    filter=filtros
                )
            else:
                results = self.vectorstore.similarity_search(query, k=k)
            
            logger.info(f"Busca retornou {len(results)} resultados para: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Erro na busca: {e}")
            return []
    
    def buscar_por_conceitos(
        self,
        conceitos: List[str],
        ano_escolar: Optional[str] = None,
        k: int = None
    ) -> List[Document]:
        """
        Busca habilidades por conceitos específicos
        
        Args:
            conceitos: Lista de conceitos matemáticos
            ano_escolar: Filtro por ano (ex: "8º", "1ª")
            k: Número de resultados
            
        Returns:
            Lista de documentos encontrados
        """
        # Cria query combinando os conceitos
        query = " ".join(conceitos)
        
        # Adiciona filtro de ano se fornecido
        filtros = {"ano": ano_escolar} if ano_escolar else None
        
        return self.buscar_habilidades(query, k=k, filtros=filtros)
    
    def buscar_por_codigo(self, codigo_bncc: str) -> Optional[Document]:
        """
        Busca uma habilidade específica pelo código BNCC
        
        Args:
            codigo_bncc: Código da habilidade (ex: "EF08MA01")
            
        Returns:
            Documento encontrado ou None
        """
        if self.vectorstore is None:
            return None
        
        try:
            results = self.vectorstore.similarity_search(
                codigo_bncc,
                k=1,
                filter={"codigo_bncc": codigo_bncc}
            )
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Erro ao buscar código {codigo_bncc}: {e}")
            return None
    
    def buscar_por_ano(self, ano: str, k: int = None) -> List[Document]:
        """
        Busca todas as habilidades de um ano específico
        
        Args:
            ano: Ano escolar (ex: "8º", "1ª")
            k: Número máximo de resultados
            
        Returns:
            Lista de documentos
        """
        if k is None:
            k = 50  # Retorna mais resultados para listagem por ano
        
        return self.buscar_habilidades(
            query=f"matemática {ano} ano",
            k=k,
            filtros={"ano": ano}
        )
    
    def formatar_habilidades(self, documentos: List[Document]) -> List[Dict[str, str]]:
        """
        Formata documentos em dicionários estruturados
        
        Args:
            documentos: Lista de documentos do ChromaDB
            
        Returns:
            Lista de dicionários com informações das habilidades
        """
        habilidades = []
        
        for doc in documentos:
            habilidade = {
                "codigo_bncc": doc.metadata.get("codigo_bncc", ""),
                "habilidade": doc.page_content,
                "ano": doc.metadata.get("ano", ""),
                "unidade_tematica": doc.metadata.get("unidade_tematica", ""),
                "objeto_conhecimento": doc.metadata.get("objeto_conhecimento", "")
            }
            habilidades.append(habilidade)
        
        return habilidades


# Instância global do serviço RAG
rag_service = RAGService()

