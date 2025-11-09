"""
Carregador de prompts modularizados
"""
import os
from pathlib import Path
from typing import Dict


class PromptLoader:
    """Classe para carregar prompts de arquivos .txt"""
    
    def __init__(self, prompts_dir: str = None):
        """
        Inicializa o carregador de prompts
        
        Args:
            prompts_dir: Diretório onde estão os arquivos de prompts
        """
        if prompts_dir is None:
            # Usa o diretório atual (app/prompts)
            self.prompts_dir = Path(__file__).parent
        else:
            self.prompts_dir = Path(prompts_dir)
    
    def load_prompt(self, filename: str) -> str:
        """
        Carrega um prompt específico de um arquivo
        
        Args:
            filename: Nome do arquivo (ex: 'agente_interpretador_system.txt')
            
        Returns:
            Conteúdo do prompt como string
            
        Raises:
            FileNotFoundError: Se o arquivo não existir
        """
        filepath = self.prompts_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"Arquivo de prompt não encontrado: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    def load_all_prompts(self) -> Dict[str, str]:
        """
        Carrega todos os prompts .txt do diretório
        
        Returns:
            Dicionário com {nome_arquivo: conteúdo}
        """
        prompts = {}
        
        for filepath in self.prompts_dir.glob("*.txt"):
            filename = filepath.name
            prompts[filename] = self.load_prompt(filename)
        
        return prompts
    
    def get_agent_prompts(self, agent_name: str) -> Dict[str, str]:
        """
        Carrega os prompts system e human de um agente específico
        
        Args:
            agent_name: Nome do agente (ex: 'interpretador', 'criador')
            
        Returns:
            Dicionário com {'system': prompt_system, 'human': prompt_human}
        """
        system_file = f"agente_{agent_name}_system.txt"
        human_file = f"agente_{agent_name}_human.txt"
        
        return {
            'system': self.load_prompt(system_file),
            'human': self.load_prompt(human_file)
        }


# Instância global do carregador
prompt_loader = PromptLoader()

