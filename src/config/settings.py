"""
Configuración central del pipeline de ingesta — Proyecto Expediente.

Usa pydantic-settings para:
  - Tipado estricto de todas las variables
  - Carga automática desde .env (sin hardcodear secrets)
  - Preparado para los API keys del Agente 2/3 (Claude, ElevenLabs, etc.)

Todo corre local: PDF -> texto -> depuración con modelo local -> almacenamiento local.
"""
from pathlib import Path

from pydantic_settings import BaseSettings

# --- Rutas derivadas de la estructura del proyecto (no sobreescribibles via .env) ---
# Usamos el directorio del archivo settings.py como referencia
SETTINGS_DIR = Path(__file__).parent  # src/config/
PROJECT_ROOT = SETTINGS_DIR.parent.parent  # raíz del proyecto

# Directorios de datos — NUNCA en git
DATA_DIR = PROJECT_ROOT / "data"
SRC_DIR = PROJECT_ROOT / "src"

# Subdirectorios de datos
DOCS_RAW_DIR = DATA_DIR / "docs_raw"
DOCS_PROCESADOS_DIR = DATA_DIR / "docs_procesados"
KB_DIR = DATA_DIR / "knowledge_base"
CHROMA_DIR = KB_DIR / "chroma_db"
SQLITE_PATH = KB_DIR / "expedientes.sqlite"
LOG_PATH = PROJECT_ROOT / "ingesta.log"
PROMPT_DEPURADOR_PATH = SRC_DIR / "prompts" / "depurador.md"


class Settings(BaseSettings):
    """
    Variables de configuración sobreescribibles via entorno o archivo .env.
    Los valores por defecto son los correctos para el entorno de desarrollo local.
    """

    # --- Modelo local ---
    local_llm_url: str = "http://localhost:8080/v1/chat/completions"
    local_llm_model: str = "default"  # Necesario para Ollama (ej: qwen2.5-coder:7b-instruct-q2_K)
    local_llm_temperature: float = 0.1  # determinista — extracción, no creatividad
    local_llm_timeout_sec: int = 120

    # --- Chunking para documentos largos ---
    # Un modelo 7B-4bit en MLX maneja bien ~6000-8000 chars de input por llamada.
    chunk_size_chars: int = 6000
    chunk_overlap_chars: int = 300

    # --- Embeddings locales (para ChromaDB) ---
    # Modelo multilingüe pequeño, corre bien en CPU/MPS en M3 Pro.
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # --- OCR fallback ---
    # Mínimo de chars por página para considerar que el PDF tiene texto real.
    min_chars_texto_real: int = 50

    # --- API keys para Agente 2/3 (vacíos en desarrollo local) ---
    # Se rellenan en .env cuando se conecten los agentes cloud.
    anthropic_api_key: str = ""
    elevenlabs_api_key: str = ""

    # --- API keys para research-agent (editorial service, Phase 4) ---
    jina_api_key: str = ""
    firecrawl_api_key: str = ""

    # --- Publisher (editorial service, Phase 5) ---
    postiz_api_key: str = ""
    postiz_base_url: str = "http://localhost:5000"

    # --- Video generation (video-generation-pipeline) ---
    # One fixed "Archivo Desclasificado" voice per language, per
    # specs/video-generation-from-script "Consistent voice per language".
    elevenlabs_spanish_voice_id: str = ""
    elevenlabs_english_voice_id: str = ""
    # Unsplash works unauthenticated at a lower rate limit; an access key
    # raises it. Empty means "no search" — the color+text fallback is used.
    unsplash_access_key: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # ignora variables de .env que no están declaradas aquí
        "root_dir": PROJECT_ROOT,  # ruta raíz del proyecto para rutas relativas
    }


settings = Settings()
