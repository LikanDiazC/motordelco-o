"""Script de corrección única para catalogo_profundo.json de Sodimac.

El deep scraper anterior al fix de ordenación emitía los breadcrumbs en orden
hoja→raíz (JSON-LD sin sort por `position`).  Este script invierte esas listas
y reporta cuántos productos fueron corregidos.

Uso:
    python scripts/fix_profundo_sodimac.py
"""

import json
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / "data" / "sodimac" / "catalogo_profundo.json"

# Palabras clave que identifican la categoría RAÍZ de Sodimac ferretería
_RAIZ_KW = ("ferretería", "fijacion", "fijación")


def es_raiz(nombre: str) -> bool:
    n = nombre.lower()
    return any(k in n for k in _RAIZ_KW)


def corregir_orden(cats: list[str]) -> tuple[list[str], bool]:
    """Devuelve (lista_corregida, fue_modificada)."""
    if len(cats) < 2:
        return cats, False
    if es_raiz(cats[-1]) and not es_raiz(cats[0]):
        return cats[::-1], True
    return cats, False


def main():
    if not RUTA.exists():
        print(f"Archivo no encontrado: {RUTA}")
        return

    with open(RUTA, encoding="utf-8") as f:
        productos = json.load(f)

    total = len(productos)
    corregidos = 0

    for prod in productos:
        cats = prod.get("categorias") or []
        nuevas, cambio = corregir_orden(cats)
        if cambio:
            prod["categorias"] = nuevas
            corregidos += 1

    with open(RUTA, "w", encoding="utf-8") as f:
        json.dump(productos, f, ensure_ascii=False, indent=4)

    print(f"✓ {total} productos procesados.")
    print(f"✓ {corregidos} categorías corregidas (invertidas a orden raíz→hoja).")
    if corregidos == 0:
        print("  (Ya estaban en orden correcto o no se encontró el patrón.)")

    # Verificar muestra
    ejemplos = [p for p in productos if p.get("categorias")][:3]
    print("\nMuestra post-corrección:")
    for p in ejemplos:
        print(f"  {p['sku']}: {p['categorias']}")


if __name__ == "__main__":
    main()
