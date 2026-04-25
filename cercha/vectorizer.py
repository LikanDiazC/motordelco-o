"""Vectorizador unificado. Ahora consume el catálogo normalizado (esquema canónico)
y construye el cerebro a partir de `contenido_vectorial.texto_a_vectorizar`.

Si el catálogo normalizado no existe, se normaliza al vuelo desde el catálogo profundo.
"""

import json
import pickle
from sentence_transformers import SentenceTransformer

from cercha.config import EMBEDDING_MODEL, STORES
from cercha.domain.normalizer import normalizar_catalogo
from cercha.domain.taxonomy import detectar_categoria


def _cargar_normalizado(nombre_tienda: str) -> list[dict]:
    """Devuelve el catálogo normalizado. Lo genera al vuelo si falta el archivo."""
    store_config = STORES[nombre_tienda]
    ruta_norm = store_config["catalog_normalized"]
    if ruta_norm.exists():
        with open(ruta_norm, 'r', encoding='utf-8') as f:
            return json.load(f)

    ruta_deep = store_config["catalog_deep"]
    if not ruta_deep.exists():
        raise FileNotFoundError(
            f"No existe ni {ruta_norm} ni {ruta_deep}. Ejecuta scrape/enrich antes."
        )
    with open(ruta_deep, 'r', encoding='utf-8') as f:
        productos_deep = json.load(f)
    normalizados = normalizar_catalogo(productos_deep, nombre_tienda)

    ruta_norm.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_norm, 'w', encoding='utf-8') as f:
        json.dump(normalizados, f, ensure_ascii=False, indent=4)
    return normalizados


def vectorizar_tienda(nombre_tienda: str):
    """Pipeline completo: normaliza → vectoriza → guarda cerebro."""
    store_config = STORES[nombre_tienda]
    ruta_vectores = store_config["catalog_vectors"]
    ruta_cerebro = store_config["brain"]

    print(f"Vectorizando {nombre_tienda}...")

    productos = _cargar_normalizado(nombre_tienda)
    if not productos:
        print(f"  Advertencia: catálogo normalizado vacío para {nombre_tienda}")
        return

    # Fase 1: preparar catálogo ligero para vectorización (+ debug)
    productos_listos = []
    for prod in productos:
        titulo = prod.get("metadata_basica", {}).get("titulo", "").strip()
        if not titulo:
            continue
        texto = prod.get("contenido_vectorial", {}).get("texto_a_vectorizar", "")
        if not texto:
            continue
        productos_listos.append({
            "id_producto": prod["id_producto"],
            "sku": prod["sku"],
            "titulo": titulo,
            "precio_clp": prod["metadata_basica"].get("precio_clp", 0),
            "url": prod.get("url_producto", ""),
            "url_imagen": prod.get("url_imagen", ""),
            "categorias": prod["metadata_basica"].get("categorias", []),
            "metadata_tecnica": prod.get("metadata_tecnica", {}),
            "texto_embedding": texto,
        })

    # Guardar catálogo estandarizado (útil para debug e inspección manual)
    ruta_vectores.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_vectores, 'w', encoding='utf-8') as f:
        json.dump(productos_listos, f, indent=4, ensure_ascii=False)

    print(f"  {len(productos_listos)} productos listos (de {len(productos)} normalizados)")

    # Fase 2: Vectorización
    print(f"  Cargando modelo {EMBEDDING_MODEL}...")
    modelo = SentenceTransformer(EMBEDDING_MODEL)

    textos = [p["texto_embedding"] for p in productos_listos]
    metadata = []
    for p in productos_listos:
        dims = p["metadata_tecnica"].get("dimensiones", {})
        # Mantener 'categoria' (id de taxonomía interna) para que search_engine
        # siga eligiendo umbrales adaptados; distinta de 'categorias' (breadcrumbs).
        categoria_id = detectar_categoria(p["titulo"]).id
        metadata.append({
            "id_producto": p["id_producto"],
            "sku": p["sku"],
            "titulo": p["titulo"],
            "precio": p["precio_clp"],
            "url": p["url"],
            "url_imagen": p["url_imagen"],
            "categorias": p["categorias"],
            "categoria": categoria_id,
            "medida_limpia": dims.get("medida_cruda", ""),
            "largo_mm": dims.get("largo_mm"),
            "diametro_mm": dims.get("diametro_mm"),
            "cantidad_empaque": p["metadata_tecnica"].get("cantidad_empaque", 1),
            "material": p["metadata_tecnica"].get("material", ""),
            "tipo_cabeza": p["metadata_tecnica"].get("tipo_cabeza", ""),
        })

    print(f"  Calculando {len(textos)} embeddings ({EMBEDDING_MODEL})...")
    vectores = modelo.encode(textos, show_progress_bar=True)

    ruta_cerebro.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_cerebro, 'wb') as f:
        pickle.dump({'vectores': vectores, 'metadata': metadata}, f)

    print(f"  Cerebro guardado: {ruta_cerebro}")
    print(f"  Ejemplo texto embedding: {textos[0][:120]}...")


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
