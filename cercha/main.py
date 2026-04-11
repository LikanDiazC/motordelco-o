"""Interfaz CLI del Comparador Cercha.

Separación clara: este archivo solo maneja I/O con el usuario.
Toda la lógica vive en los módulos domain/.
"""

import pickle
from sentence_transformers import SentenceTransformer

from cercha.config import STORES, EMBEDDING_MODEL, MATCH_SIMILARITY_THRESHOLD
from cercha.domain.search_engine import limpiar_texto, buscar_en_tienda


def cargar_cerebro(nombre_tienda: str) -> dict:
    """Carga el cerebro vectorial de una tienda desde disco."""
    ruta = STORES[nombre_tienda]["brain"]
    if not ruta.exists():
        raise FileNotFoundError(f"No existe cerebro para {nombre_tienda}: {ruta}")
    with open(ruta, 'rb') as f:
        return pickle.load(f)


def mostrar_resultado_tienda(nombre: str, resultado, emoji: str):
    """Formatea y muestra el resultado de una tienda."""
    if resultado.es_match:
        print(f"{emoji} {nombre.upper()} (Match: {resultado.similitud*100:.1f}%)")
        print(f"   Producto: {resultado.producto['titulo']}")
        print(f"   Cantidad: {resultado.cantidad} unidades")
        precio_caja = resultado.producto['precio']
        print(f"   Precio Caja: ${precio_caja:,.0f}  ->  [ Unitario: ${resultado.precio_unitario:,.1f} c/u ]")
    else:
        print(f"{emoji} {nombre.upper()} -- No se encontro producto exacto.")


def iniciar_comparador():
    """Loop principal del comparador interactivo."""
    print("=" * 60)
    print(" COMPARADOR CERCHA v4.0")
    print(" Motor de Cotizacion Hibrido (Semantico + Dimensional)")
    print("=" * 60)

    # Cargar datos de todas las tiendas disponibles
    tiendas_data = {}
    for nombre in STORES:
        try:
            tiendas_data[nombre] = cargar_cerebro(nombre)
            print(f"  [{nombre}] Cerebro cargado ({len(tiendas_data[nombre]['metadata'])} productos)")
        except FileNotFoundError as e:
            print(f"  [{nombre}] No disponible: {e}")

    if not tiendas_data:
        print("\nError: No hay tiendas disponibles. Ejecuta el pipeline primero.")
        return

    print(f"\n  Cargando modelo semantico ({EMBEDDING_MODEL})...")
    modelo = SentenceTransformer(EMBEDDING_MODEL)

    print(f"  Umbral de match: {MATCH_SIMILARITY_THRESHOLD*100:.0f}%")
    print(f"\n  Sistema listo. {len(tiendas_data)} tienda(s) activa(s).\n")

    emojis = {"sodimac": "[SODIMAC]", "easy": "[EASY]"}

    while True:
        query = input("Buscar (o 'salir'): ").strip()
        if query.lower() in ('salir', 'exit', 'quit', ''):
            break

        query_limpia = limpiar_texto(query)
        vector_query = modelo.encode([query_limpia], convert_to_tensor=False)

        resultados = {}
        for nombre, datos in tiendas_data.items():
            resultados[nombre] = buscar_en_tienda(
                query_limpia, vector_query,
                datos['metadata'], datos['vectores'],
                MATCH_SIMILARITY_THRESHOLD,
            )

        # Mostrar resultados
        print(f"\n{'='*65}")
        print(f"  RESULTADOS: '{query.upper()}'")
        print(f"{'='*65}")

        for nombre, res in resultados.items():
            mostrar_resultado_tienda(nombre, res, emojis.get(nombre, f"[{nombre}]"))
            print("-" * 65)

        # Recomendación de precio
        matches = {n: r for n, r in resultados.items() if r.es_match}
        if len(matches) >= 2:
            mas_barato = min(matches, key=lambda n: matches[n].precio_unitario)
            precios = sorted(matches.values(), key=lambda r: r.precio_unitario)
            ahorro = precios[1].precio_unitario - precios[0].precio_unitario
            if ahorro > 0:
                print(f"  RECOMENDACION: Compra en {mas_barato.upper()}. "
                      f"Ahorras ${ahorro:,.1f} por unidad.")
            else:
                print("  RECOMENDACION: Mismo precio unitario en ambas tiendas.")
        elif len(matches) == 1:
            nombre_unico = list(matches.keys())[0]
            print(f"  Solo disponible en {nombre_unico.upper()}.")

        print(f"{'='*65}\n")


if __name__ == "__main__":
    iniciar_comparador()
