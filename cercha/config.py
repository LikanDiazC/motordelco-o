"""Configuración centralizada de Cercha. Única fuente de verdad para rutas y constantes."""

from pathlib import Path

# Raíz del proyecto (relativa al repositorio, no a la máquina del desarrollador)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Configuración de tiendas - agregar una nueva tienda es agregar una entrada aquí
STORES = {
    "sodimac": {
        "catalog_raw": DATA_DIR / "sodimac" / "catalogo_crudo.json",
        "catalog_deep": DATA_DIR / "sodimac" / "catalogo_profundo.json",
        "catalog_vectors": DATA_DIR / "sodimac" / "catalogo_vectores.json",
        "brain": DATA_DIR / "sodimac" / "cerebro.pkl",
        "faiss_index": DATA_DIR / "sodimac" / "index.faiss",
    },
    "easy": {
        "catalog_raw": DATA_DIR / "easy" / "catalogo_crudo.json",
        "catalog_deep": DATA_DIR / "easy" / "catalogo_profundo.json",
        "catalog_vectors": DATA_DIR / "easy" / "catalogo_vectores.json",
        "brain": DATA_DIR / "easy" / "cerebro.pkl",
        "faiss_index": DATA_DIR / "easy" / "index.faiss",
    },
}

# Modelo de embeddings
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSION = 384

# Umbrales del motor de búsqueda
MATCH_SIMILARITY_THRESHOLD = 0.70
LEXICAL_BONUS_PER_WORD = 0.05
TOP_K_CANDIDATES = 15

# Scraping
SCRAPE_DELAY_SECONDS = 2
SCRAPE_CHECKPOINT_EVERY = 10
PAGE_LOAD_TIMEOUT_MS = 60000
