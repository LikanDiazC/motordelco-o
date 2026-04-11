"""Orquestador de pipeline. Ejecuta las etapas de scraping → enriquecimiento → vectorización.

Uso:
    python -m cercha.pipeline scrape sodimac
    python -m cercha.pipeline scrape easy
    python -m cercha.pipeline enrich sodimac
    python -m cercha.pipeline enrich easy
    python -m cercha.pipeline vectorize sodimac
    python -m cercha.pipeline vectorize easy
    python -m cercha.pipeline vectorize all
    python -m cercha.pipeline full sodimac     # ejecuta todo
"""

import sys
import pickle
from sentence_transformers import SentenceTransformer
from cercha.config import STORES, EMBEDDING_MODEL, MATCH_SIMILARITY_THRESHOLD

class CerchaPipeline:
    """
    Motor centralizado en memoria.
    Carga el modelo semántico y los cerebros vectoriales para su uso en la API y el Dashboard.
    """
    def __init__(self):
        print(f"Cargando modelo semántico ({EMBEDDING_MODEL})...")
        self.modelo = SentenceTransformer(EMBEDDING_MODEL)
        self.umbral = MATCH_SIMILARITY_THRESHOLD
        self.tiendas = {}

        for nombre_tienda, config_tienda in STORES.items():
            ruta_cerebro = config_tienda["brain"]
            if ruta_cerebro.exists():
                print(f"  Cargando cerebro de {nombre_tienda}...")
                with open(ruta_cerebro, 'rb') as f:
                    self.tiendas[nombre_tienda] = pickle.load(f)
            else:
                print(f"  Advertencia: No se encontró el cerebro para {nombre_tienda} en {ruta_cerebro}")


def cmd_scrape(tienda: str):
    if tienda == "sodimac":
        from cercha.scrapers.sodimac import SodimacCatalogScraper
        SodimacCatalogScraper().ejecutar()
    elif tienda == "easy":
        from cercha.scrapers.easy import EasyCatalogScraper
        EasyCatalogScraper().ejecutar()
    else:
        print(f"Tienda desconocida: {tienda}. Opciones: {list(STORES.keys())}")


def cmd_enrich(tienda: str):
    if tienda == "sodimac":
        from cercha.scrapers.sodimac import SodimacDeepScraper
        SodimacDeepScraper().ejecutar()
    elif tienda == "easy":
        from cercha.scrapers.easy import EasyDeepScraper
        EasyDeepScraper().ejecutar()
    else:
        print(f"Tienda desconocida: {tienda}. Opciones: {list(STORES.keys())}")


def cmd_vectorize(tienda: str):
    from cercha.vectorizer import vectorizar_tienda, vectorizar_todas
    if tienda == "all":
        vectorizar_todas()
    elif tienda in STORES:
        vectorizar_tienda(tienda)
    else:
        print(f"Tienda desconocida: {tienda}. Opciones: {list(STORES.keys()) + ['all']}")


def cmd_full(tienda: str):
    """Ejecuta pipeline completo: scrape → enrich → vectorize."""
    print(f"=== Pipeline completo para {tienda} ===")
    print("\n[1/3] Scraping catalogo...")
    cmd_scrape(tienda)
    print("\n[2/3] Enriquecimiento profundo...")
    cmd_enrich(tienda)
    print("\n[3/3] Vectorizacion...")
    cmd_vectorize(tienda)
    print(f"\n=== Pipeline {tienda} completado ===")


def main():
    if len(sys.argv) < 3:
        print("Uso: python -m cercha.pipeline <comando> <tienda>")
        print("Comandos: scrape, enrich, vectorize, full")
        print(f"Tiendas: {list(STORES.keys())}")
        sys.exit(1)

    comando = sys.argv[1]
    tienda = sys.argv[2]

    comandos = {
        "scrape": cmd_scrape,
        "enrich": cmd_enrich,
        "vectorize": cmd_vectorize,
        "full": cmd_full,
    }

    if comando not in comandos:
        print(f"Comando desconocido: {comando}. Opciones: {list(comandos.keys())}")
        sys.exit(1)

    comandos[comando](tienda)


if __name__ == "__main__":
    main()
