"""Vectorizador unificado. Una sola función para crear el "cerebro" de cualquier tienda.

Elimina la duplicación entre crear_vectores.py e ia_easy.py.
"""

import json
import re
import pickle
from pathlib import Path
from sentence_transformers import SentenceTransformer

from cercha.config import EMBEDDING_MODEL, STORES
from cercha.domain.feature_engineering import construir_super_oracion
from cercha.domain.taxonomy import detectar_categoria

# Specs que se preservan en la metadata del cerebro (para extraer cantidad y medidas)
_SPECS_KEYS_CANTIDAD = {'Contenido', 'Cantidad por paquete', 'Cantidad de Unidades (PPUM)'}
_SPECS_KEYS_MEDIDA = {'Diámetro', 'Diametro', 'Largo', 'Medidas'}


def _specs_relevantes(specs: dict) -> dict:
    """Filtra solo las specs útiles para búsqueda en runtime (ahorra memoria en pickle)."""
    if not specs:
        return {}
    relevantes = {}
    for k, v in specs.items():
        if k in _SPECS_KEYS_CANTIDAD or k in _SPECS_KEYS_MEDIDA:
            relevantes[k] = v
    return relevantes


def vectorizar_tienda(nombre_tienda: str):
    """Pipeline completo: lee catálogo profundo → estandariza → vectoriza → guarda cerebro.

    Funciona para cualquier tienda registrada en config.STORES.
    """
    store_config = STORES[nombre_tienda]
    ruta_entrada = store_config["catalog_deep"]
    ruta_vectores = store_config["catalog_vectors"]
    ruta_cerebro = store_config["brain"]

    print(f"Vectorizando {nombre_tienda}...")

    if not ruta_entrada.exists():
        print(f"  Error: No existe {ruta_entrada}")
        return

    with open(ruta_entrada, 'r', encoding='utf-8') as f:
        productos = json.load(f)

    # Fase 1: Feature Engineering (unificado)
    productos_listos = []
    for prod in productos:
        titulo = prod.get('titulo', '').strip()
        if not titulo:
            continue

        specs = prod.get('especificaciones', {})
        desc_extra = prod.get('descripcion_completa', prod.get('descripcion', ''))
        desc_extra = re.sub(r'<[^>]+>', ' ', desc_extra).replace('&quot;', '"')

        categoria = detectar_categoria(titulo)
        features = construir_super_oracion(titulo, specs, desc_extra, categoria)

        productos_listos.append({
            "sku": prod.get('sku', 'N/A'),
            "titulo": titulo,
            "precio_clp": prod.get('precio_clp', 0),
            "url": prod.get('url', ''),
            "categoria": features["categoria"],
            "medida_extraida": features["medida"],
            "texto_embedding": features["texto_embedding"],
            "specs": specs,
        })

    # Guardar catálogo estandarizado (útil para debug)
    ruta_vectores.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_vectores, 'w', encoding='utf-8') as f:
        json.dump(productos_listos, f, indent=4, ensure_ascii=False)

    print(f"  {len(productos_listos)} productos estandarizados (de {len(productos)} totales)")

    # Fase 2: Vectorización
    print(f"  Cargando modelo {EMBEDDING_MODEL}...")
    modelo = SentenceTransformer(EMBEDDING_MODEL)

    textos = [p['texto_embedding'] for p in productos_listos]
    metadata = [{
        "sku": p['sku'],
        "titulo": p['titulo'],
        "precio": p['precio_clp'],
        "url": p['url'],
        "categoria": p['categoria'],
        "medida_limpia": p['medida_extraida'],
        "specs": _specs_relevantes(p.get('specs', {})),
    } for p in productos_listos]

    print(f"  Calculando {len(textos)} embeddings ({EMBEDDING_MODEL})...")
    vectores = modelo.encode(textos, show_progress_bar=True)

    # Guardar cerebro
    ruta_cerebro.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_cerebro, 'wb') as f:
        pickle.dump({'vectores': vectores, 'metadata': metadata}, f)

    print(f"  Cerebro guardado: {ruta_cerebro}")
    print(f"  Ejemplo super oracion: {textos[0][:120]}...")


def vectorizar_todas():
    """Vectoriza todas las tiendas registradas."""
    for nombre in STORES:
        ruta_deep = STORES[nombre]["catalog_deep"]
        if ruta_deep.exists():
            vectorizar_tienda(nombre)
        else:
            print(f"  Saltando {nombre}: no existe {ruta_deep}")


if __name__ == "__main__":
    vectorizar_todas()
