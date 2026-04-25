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
        "catalog_normalized": DATA_DIR / "sodimac" / "catalogo_normalizado.json",
        "catalog_vectors": DATA_DIR / "sodimac" / "catalogo_vectores.json",
        "brain": DATA_DIR / "sodimac" / "cerebro.pkl",
        "faiss_index": DATA_DIR / "sodimac" / "index.faiss",
    },
    "easy": {
        "catalog_raw": DATA_DIR / "easy" / "catalogo_crudo.json",
        "catalog_deep": DATA_DIR / "easy" / "catalogo_profundo.json",
        "catalog_normalized": DATA_DIR / "easy" / "catalogo_normalizado.json",
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

# Stop words: palabras funcionales que no aportan valor léxico en la búsqueda.
# El bono léxico SOLO debe premiar sustantivos/adjetivos de contenido.
STOP_WORDS = {
    # Artículos y determinantes
    "de", "la", "el", "los", "las", "un", "una", "unos", "unas", "del", "al",
    # Preposiciones comunes
    "para", "con", "en", "por", "a", "sin", "sobre", "bajo", "ante", "entre",
    "hasta", "desde", "hacia",
    # Conjunciones
    "y", "o", "u", "e", "ni", "pero", "que",
    # Separador dimensional ("6 x 2" → "x" no es contenido)
    "x",
    # Pronombres/partículas funcionales
    "se", "su", "sus", "lo",
}

# Scraping
SCRAPE_DELAY_SECONDS = 2
SCRAPE_CHECKPOINT_EVERY = 10
PAGE_LOAD_TIMEOUT_MS = 60000
