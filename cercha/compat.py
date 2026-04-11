"""Capa de compatibilidad para ejecutar con los datos legacy (data/, data2/).

Permite usar el nuevo motor de búsqueda con los .pkl existentes sin
necesidad de re-vectorizar inmediatamente.

Uso: python -m cercha.compat
"""

import pickle
from pathlib import Path
from sentence_transformers import SentenceTransformer

from cercha.config import EMBEDDING_MODEL, MATCH_SIMILARITY_THRESHOLD
from cercha.domain.search_engine import limpiar_texto, buscar_en_tienda


# Rutas legacy
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGACY_SODIMAC = PROJECT_ROOT / "data" / "cerebro_sodimac.pkl"
LEGACY_EASY = PROJECT_ROOT / "data2" / "cerebro_easy.pkl"


def cargar_legacy():
    """Carga los cerebros del formato viejo."""
    tiendas = {}

    if LEGACY_SODIMAC.exists():
        with open(LEGACY_SODIMAC, 'rb') as f:
            tiendas["sodimac"] = pickle.load(f)
        print(f"  [sodimac] {len(tiendas['sodimac']['metadata'])} productos")

    if LEGACY_EASY.exists():
        with open(LEGACY_EASY, 'rb') as f:
            tiendas["easy"] = pickle.load(f)
        print(f"  [easy] {len(tiendas['easy']['metadata'])} productos")

    return tiendas


def iniciar_comparador_legacy():
    """Comparador usando datos legacy con el nuevo motor de búsqueda."""
    print("=" * 60)
    print(" COMPARADOR CERCHA v4.0 (modo compatibilidad)")
    print(" Motor de Busqueda Hibrido (Semantico + Dimensional)")
    print("=" * 60)

    print("\n  Cargando cerebros legacy...")
    tiendas = cargar_legacy()

    if not tiendas:
        print("\n  Error: No hay datos. Verifica que existan los .pkl")
        return

    print(f"\n  Cargando modelo semantico...")
    modelo = SentenceTransformer(EMBEDDING_MODEL)
    print(f"  Umbral: {MATCH_SIMILARITY_THRESHOLD*100:.0f}%")
    print(f"\n  Sistema listo.\n")

    while True:
        query = input("Buscar (o 'salir'): ").strip()
        if query.lower() in ('salir', 'exit', 'quit', ''):
            break

        query_limpia = limpiar_texto(query)
        vector_query = modelo.encode([query_limpia])

        print(f"\n{'='*65}")
        print(f"  RESULTADOS: '{query.upper()}'")
        print(f"{'='*65}")

        resultados = {}
        for nombre, datos in tiendas.items():
            res = buscar_en_tienda(
                query_limpia, vector_query,
                datos['metadata'], datos['vectores'],
                MATCH_SIMILARITY_THRESHOLD,
            )
            resultados[nombre] = res

            if res.es_match:
                print(f"  [{nombre.upper()}] Match: {res.similitud*100:.1f}%")
                print(f"    Producto: {res.producto['titulo']}")
                print(f"    Cantidad: {res.cantidad} un.")
                print(f"    Precio: ${res.producto['precio']:,.0f} -> Unitario: ${res.precio_unitario:,.1f} c/u")
            else:
                print(f"  [{nombre.upper()}] No se encontro producto exacto.")
            print(f"  {'-'*60}")

        # Recomendación
        matches = {n: r for n, r in resultados.items() if r.es_match}
        if len(matches) >= 2:
            precios_ord = sorted(matches.items(), key=lambda x: x[1].precio_unitario)
            mejor = precios_ord[0][0]
            ahorro = precios_ord[1][1].precio_unitario - precios_ord[0][1].precio_unitario
            if ahorro > 0:
                print(f"  RECOMENDACION: Compra en {mejor.upper()}. Ahorras ${ahorro:,.1f}/unidad.")
            else:
                print(f"  RECOMENDACION: Mismo precio unitario.")

        print(f"{'='*65}\n")


if __name__ == "__main__":
    iniciar_comparador_legacy()
