"""Clustering no supervisado de productos Easy + Sodimac.

Pipeline:
  1. Carga embeddings desde ambos cerebro.pkl
  2. Reduce dimensionalidad con UMAP (384 -> n_components)
  3. Clusteriza con HDBSCAN
  4. Persiste cluster_id en catalogo_normalizado.json de cada tienda
  5. Genera reporte de clusters (tamaño, mezcla Easy/Sodimac, ejemplos)

Uso:
    python -m cercha.domain.clustering
"""

from __future__ import annotations

import json
import pickle
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import umap
from sklearn.cluster import HDBSCAN

from cercha.config import STORES


# ---------------------------------------------------------------------------
# Parámetros por defecto (ajustables)
#
# Objetivo: clusters suficientemente amplios para que productos equivalentes
# entre Easy y Sodimac caigan juntos, sin colapsar tipos distintos.
#
# n_neighbors ALTO  -> estructura global (productos parecidos cruzan tiendas)
# n_components BAJO -> espacio más compacto (clusters más grandes)
# min_cluster_size ALTO -> no fragmentar en micro-clusters por-tienda
# ---------------------------------------------------------------------------
UMAP_N_NEIGHBORS = 50      # muy global: cruza fronteras de tienda
UMAP_N_COMPONENTS = 8
UMAP_MIN_DIST = 0.0
UMAP_METRIC = "cosine"
RANDOM_STATE = 42

HDB_MIN_CLUSTER_SIZE = 15  # equilibrio: ni micro ni mega-clusters
HDB_MIN_SAMPLES = 3
HDB_METRIC = "euclidean"

BASE = Path(r"C:\Users\Administrator\Documents\Buscop\motordelco-o\data")
REPORTE = BASE / "clusters_reporte.json"


def cargar_cerebros() -> tuple[np.ndarray, list[dict]]:
    """Concatena vectores y metadata de todas las tiendas en matrices únicas."""
    vectores_list, meta_list = [], []
    for tienda, cfg in STORES.items():
        ruta = cfg["brain"]
        if not ruta.exists():
            print(f"  [WARN] No existe cerebro de {tienda}: {ruta}")
            continue
        with open(ruta, "rb") as f:
            brain = pickle.load(f)
        vectores_list.append(brain["vectores"])
        for m in brain["metadata"]:
            m = dict(m)
            m["tienda"] = tienda
            meta_list.append(m)
        print(f"  {tienda:>8}: {len(brain['vectores'])} embeddings cargados")
    vectores = np.vstack(vectores_list).astype(np.float32)
    return vectores, meta_list


def reducir_umap(vectores: np.ndarray) -> np.ndarray:
    print(f"\n[UMAP] Reduciendo {vectores.shape[1]} -> {UMAP_N_COMPONENTS} dims...")
    reducer = umap.UMAP(
        n_neighbors=UMAP_N_NEIGHBORS,
        n_components=UMAP_N_COMPONENTS,
        min_dist=UMAP_MIN_DIST,
        metric=UMAP_METRIC,
        random_state=RANDOM_STATE,
        verbose=False,
    )
    reducido = reducer.fit_transform(vectores)
    print(f"  OK: shape resultante {reducido.shape}")
    return reducido


def clusterizar(embedding_2d: np.ndarray) -> np.ndarray:
    print(f"\n[HDBSCAN] min_cluster_size={HDB_MIN_CLUSTER_SIZE}, min_samples={HDB_MIN_SAMPLES}")
    clusterer = HDBSCAN(
        min_cluster_size=HDB_MIN_CLUSTER_SIZE,
        min_samples=HDB_MIN_SAMPLES,
        metric=HDB_METRIC,
        cluster_selection_method="eom",
    )
    labels = clusterer.fit_predict(embedding_2d)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_ruido = int((labels == -1).sum())
    print(f"  Clusters detectados: {n_clusters}")
    print(f"  Productos ruido (-1): {n_ruido} ({n_ruido*100//len(labels)}%)")
    return labels


def construir_reporte(labels: np.ndarray, meta: list[dict]) -> dict:
    """Devuelve estadísticas por cluster: tamaño, distribución Easy/Sodimac, ejemplos, medida típica."""
    buckets: dict[int, list[dict]] = defaultdict(list)
    for lab, m in zip(labels, meta):
        buckets[int(lab)].append(m)

    reporte = {
        "n_productos": len(labels),
        "n_clusters": sum(1 for k in buckets if k != -1),
        "n_ruido": len(buckets.get(-1, [])),
        "parametros": {
            "umap": {
                "n_neighbors": UMAP_N_NEIGHBORS,
                "n_components": UMAP_N_COMPONENTS,
                "min_dist": UMAP_MIN_DIST,
                "metric": UMAP_METRIC,
            },
            "hdbscan": {
                "min_cluster_size": HDB_MIN_CLUSTER_SIZE,
                "min_samples": HDB_MIN_SAMPLES,
                "metric": HDB_METRIC,
            },
        },
        "clusters": [],
    }

    # Orden: ruido al final, resto por tamaño descendente
    keys_ordenadas = sorted(
        [k for k in buckets if k != -1],
        key=lambda k: len(buckets[k]),
        reverse=True,
    )
    if -1 in buckets:
        keys_ordenadas.append(-1)

    for cid in keys_ordenadas:
        prods = buckets[cid]
        por_tienda = Counter(p["tienda"] for p in prods)
        categorias = Counter(p.get("categoria", "") for p in prods).most_common(3)
        largos = [p.get("largo_mm") for p in prods if p.get("largo_mm")]
        diams = [p.get("diametro_mm") for p in prods if p.get("diametro_mm")]
        materiales = Counter(
            (p.get("material", "") or "").lower() for p in prods if p.get("material")
        ).most_common(3)

        info = {
            "cluster_id": cid,
            "tamano": len(prods),
            "por_tienda": dict(por_tienda),
            "mix_tiendas": round(
                min(por_tienda.values()) / max(por_tienda.values()), 2
            ) if len(por_tienda) > 1 else 0.0,
            "categoria_top": categorias[0][0] if categorias else "",
            "categorias_top3": categorias,
            "materiales_top3": materiales,
            "largo_mm_medio": round(float(np.median(largos)), 2) if largos else None,
            "diam_mm_medio": round(float(np.median(diams)), 2) if diams else None,
            "ejemplos": [
                {
                    "tienda": p["tienda"],
                    "sku": p["sku"],
                    "titulo": p["titulo"][:90],
                    "largo_mm": p.get("largo_mm"),
                    "diametro_mm": p.get("diametro_mm"),
                }
                for p in prods[:4]
            ],
        }
        reporte["clusters"].append(info)
    return reporte


def guardar_cluster_ids_en_normalizados(labels: np.ndarray, meta: list[dict]) -> None:
    """Inserta `cluster_id` en cada producto del catalogo_normalizado.json por tienda."""
    mapping: dict[tuple[str, str], int] = {
        (m["tienda"], str(m["sku"])): int(lab)
        for lab, m in zip(labels, meta)
    }

    for tienda, cfg in STORES.items():
        ruta = cfg["catalog_normalized"]
        if not ruta.exists():
            continue
        with open(ruta, encoding="utf-8") as f:
            productos = json.load(f)
        n_actualizados = 0
        for p in productos:
            key = (tienda, str(p["sku"]))
            cid = mapping.get(key)
            if cid is not None:
                p["cluster_id"] = cid
                n_actualizados += 1
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(productos, f, ensure_ascii=False, indent=4)
        print(f"  {tienda:>8}: cluster_id asignado a {n_actualizados}/{len(productos)}")


def main():
    print("=" * 70)
    print("CLUSTERING NO SUPERVISADO  (UMAP + HDBSCAN)")
    print("=" * 70)

    vectores, meta = cargar_cerebros()
    print(f"  Total: {len(meta)} productos, embedding dim={vectores.shape[1]}")

    reducido = reducir_umap(vectores)
    labels = clusterizar(reducido)

    print("\n[PERSISTENCIA]")
    guardar_cluster_ids_en_normalizados(labels, meta)

    print("\n[REPORTE]")
    reporte = construir_reporte(labels, meta)
    REPORTE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORTE, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=4)
    print(f"  Reporte guardado: {REPORTE}")

    # resumen ejecutivo
    print("\n[RESUMEN]")
    print(f"  Productos     : {reporte['n_productos']}")
    print(f"  Clusters      : {reporte['n_clusters']}")
    print(f"  Ruido         : {reporte['n_ruido']}")
    bi_tienda = sum(1 for c in reporte["clusters"] if c["cluster_id"] != -1 and c["mix_tiendas"] > 0)
    print(f"  Clusters con ambas tiendas: {bi_tienda} / {reporte['n_clusters']}")

    print("\n  Top 10 clusters más grandes:")
    for c in reporte["clusters"][:10]:
        if c["cluster_id"] == -1:
            continue
        tag = c["categoria_top"] or "?"
        mix = c["por_tienda"]
        print(f"    #{c['cluster_id']:>3} n={c['tamano']:<4} [{tag:<14}] "
              f"easy={mix.get('easy', 0):>3} sodimac={mix.get('sodimac', 0):>3}  "
              f"ej: {c['ejemplos'][0]['titulo']}")


if __name__ == "__main__":
    main()
