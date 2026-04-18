"""Script de scraping multi-categoría. Ejecutar desde la raíz del proyecto:
    python scrape_all.py [sodimac|easy|all]
"""

import sys
import json
from pathlib import Path
from collections import Counter

def resumen_categorias(ruta_json: Path, label: str, mostrar_ejemplos: bool = True):
    """Muestra un resumen de categorías detectadas en el catálogo."""
    from cercha.domain.taxonomy import detectar_categoria

    with open(ruta_json, 'r', encoding='utf-8') as f:
        productos = json.load(f)

    conteo: Counter = Counter()
    por_cat: dict[str, list] = {}
    for p in productos:
        cat = detectar_categoria(p.get('titulo', ''))
        conteo[cat.nombre] += 1
        por_cat.setdefault(cat.nombre, []).append(p.get('titulo', ''))

    print(f"\n--- Resumen {label} ({len(productos)} productos) ---")
    for nombre, n in sorted(conteo.items(), key=lambda x: -x[1]):
        print(f"  {nombre:35s} {n:4d} productos")
        if mostrar_ejemplos:
            for t in por_cat[nombre][:2]:
                print(f"      · {t[:80]}")


def main():
    tienda = sys.argv[1] if len(sys.argv) > 1 else "all"

    if tienda in ("sodimac", "all"):
        print("\n=== SODIMAC: scraping catalogo ===")
        from cercha.scrapers.sodimac import SodimacCatalogScraper, SODIMAC_BUSQUEDAS
        from cercha.config import STORES
        SodimacCatalogScraper().ejecutar()
        resumen_categorias(STORES["sodimac"]["catalog_raw"], "Sodimac")

    if tienda in ("easy", "all"):
        print("\n=== EASY: scraping catalogo ===")
        from cercha.scrapers.easy import EasyCatalogScraper
        from cercha.config import STORES
        EasyCatalogScraper().ejecutar()
        resumen_categorias(STORES["easy"]["catalog_raw"], "Easy")

    print("\nListo. Para enriquecer y vectorizar:")
    print("  python -m cercha.pipeline enrich sodimac")
    print("  python -m cercha.pipeline enrich easy")
    print("  python -m cercha.pipeline vectorize all")


if __name__ == "__main__":
    main()
