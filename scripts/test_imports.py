"""
Script para testar se todas as importações estão funcionando
"""
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

print("=" * 70)
print("🧪 Testando Importações do BNCC-Gen")
print("=" * 70)

try:
    print("\n1. Testando core...")
    from app.core.config import settings
    print(f"   ✓ Config carregado: {settings.APP_NAME}")
    
    print("\n2. Testando database...")
    from app.db.database import get_db, init_db
    from app.db.models import SessaoEstudo
    from app.db.schemas import SessionStartResponse
    print("   ✓ Database modules OK")
    
    print("\n3. Testando prompts...")
    from app.prompts.prompt_loader import prompt_loader
    print("   ✓ Prompt loader OK")
    
    print("\n4. Testando services...")
    from app.services.rag_service import rag_service
    print("   ✓ RAG Service OK")
    
    from app.services.tools import ALL_TOOLS
    print(f"   ✓ Tools OK ({len(ALL_TOOLS)} tools)")
    
    from app.services.ocr_service import ocr_service
    print("   ✓ OCR Service OK")
    
    from app.services.agent_service import agent_service
    print("   ✓ Agent Service OK")
    
    print("\n5. Testando API...")
    from app.api.v1.api import api_router
    print("   ✓ API Router OK")
    
    print("\n6. Testando main...")
    from app.main import app
    print("   ✓ FastAPI App OK")
    
    print("\n" + "=" * 70)
    print("✅ Todos os módulos importados com sucesso!")
    print("=" * 70)
    print("\n📌 Próximos passos:")
    print("   1. Configure sua OPENAI_API_KEY no arquivo .env")
    print("   2. Execute: python scripts/ingest_bncc.py")
    print("   3. Execute: uvicorn app.main:app --reload")
    print("\n")
    
except Exception as e:
    print(f"\n❌ Erro ao importar: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

