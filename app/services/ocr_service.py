"""
Serviço de OCR (Optical Character Recognition) - MOCK para MVP
"""
from typing import BinaryIO
import logging

logger = logging.getLogger(__name__)


class OCRService:
    """
    Serviço mock de OCR para extração de texto de imagens.
    
    No MVP, retorna textos de exemplo. Em produção, seria integrado
    com serviços como Google Vision API, AWS Textract, ou Tesseract.
    """
    
    def __init__(self):
        """Inicializa o serviço de OCR"""
        self.mock_questoes = [
            # Questão 1: Função Quadrática
            """
            Questão: Dada a função f(x) = x² - 4x + 3, determine:
            a) As coordenadas do vértice da parábola
            b) O valor mínimo da função
            c) As raízes da função
            """,
            
            # Questão 2: Geometria
            """
            Questão: Um triângulo retângulo possui catetos medindo 6 cm e 8 cm.
            Calcule:
            a) A medida da hipotenusa
            b) A área do triângulo
            c) O perímetro do triângulo
            """,
            
            # Questão 3: Probabilidade
            """
            Questão: Em uma urna há 5 bolas vermelhas, 3 bolas azuis e 2 bolas verdes.
            Retirando uma bola ao acaso, qual a probabilidade de:
            a) Sair uma bola vermelha?
            b) Sair uma bola que não seja verde?
            c) Sair uma bola azul ou verde?
            """,
            
            # Questão 4: Equações
            """
            Questão: Resolva o sistema de equações:
            2x + 3y = 13
            x - y = 1
            
            Determine os valores de x e y.
            """
        ]
        
        self.mock_respostas = [
            # Respostas para Questão 1
            """
            Respostas:
            a) V(2, -1)
            b) Valor mínimo = -1
            c) x₁ = 1 e x₂ = 3
            """,
            
            # Respostas para Questão 2
            """
            Respostas:
            a) Hipotenusa = 10 cm
            b) Área = 24 cm²
            c) Perímetro = 24 cm
            """,
            
            # Respostas para Questão 3
            """
            Respostas:
            a) P(vermelha) = 5/10 = 1/2 = 50%
            b) P(não verde) = 8/10 = 4/5 = 80%
            c) P(azul ou verde) = 5/10 = 1/2 = 50%
            """,
            
            # Respostas para Questão 4
            """
            Respostas:
            x = 4
            y = 3
            """
        ]
        
        self.current_questao_index = 0
        self.current_resposta_index = 0
    
    async def extrair_texto_questao(self, file: BinaryIO) -> str:
        """
        Extrai texto de uma imagem de questão (MOCK).
        
        Args:
            file: Arquivo de imagem
            
        Returns:
            Texto extraído da imagem
        """
        logger.info("OCR Mock: Extraindo texto de questão")
        
        # No mock, retorna uma questão de exemplo
        texto = self.mock_questoes[self.current_questao_index % len(self.mock_questoes)]
        self.current_questao_index += 1
        
        logger.info(f"OCR Mock: Texto extraído (questão {self.current_questao_index})")
        return texto.strip()
    
    async def extrair_texto_respostas(self, file: BinaryIO) -> str:
        """
        Extrai texto de uma imagem de respostas (MOCK).
        
        Args:
            file: Arquivo de imagem
            
        Returns:
            Texto extraído da imagem
        """
        logger.info("OCR Mock: Extraindo texto de respostas")
        
        # No mock, retorna respostas de exemplo
        texto = self.mock_respostas[self.current_resposta_index % len(self.mock_respostas)]
        self.current_resposta_index += 1
        
        logger.info(f"OCR Mock: Texto extraído (resposta {self.current_resposta_index})")
        return texto.strip()
    
    def reset_indices(self):
        """Reseta os índices dos mocks (útil para testes)"""
        self.current_questao_index = 0
        self.current_resposta_index = 0


# Instância global do serviço OCR
ocr_service = OCRService()

