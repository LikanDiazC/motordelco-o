"""Analiza los pares intra-cluster que no fueron ni positivos ni negativos duros.

Objetivo: identificar si hay positivos ocultos que valdría la pena capturar
relajando reglas, sin introducir ruido.
"""
from __future__ import annotations

import json
import pickle
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from cercha.config import STORES

BASE = Path(r"C:\Users\Administrator\Documents\Buscop\motordelco-o\data")

_TOKEN_RE = re.compile(r"[a-záéíóúñA-ZÁÉÍÓÚÑ0-9]+", re.IGNORECASE)

def _tokens(texto: str) -> set[str]:
    if not texto:
        return set()
    return {t.lower() for t in _TOKEN_RE.findall(texto) if len(t) > 1}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _normalizar(mat):
    n = np.linalg.norm(mat, axis=1, keepdims=True)
    n = np.where(n == 0, 1, n)
    return mat / n


def _cargar(nombre):
    with open(STORES[nombre]["catalog_normalized"], encoding="utf-8") as f:
        productos = json.load(f)
    with open(STORES[nombre]["brain"], "rb") as f:
        brain = pickle.load(f)
    idx = {m["id_producto"]: i for i, m in enumerate(brain["metadata"])}
    return productos, brain["vectores"].astype(np.float32), idx


def main():
    print("=" * 70)
    print("ANÁLISIS DE PARES INTRA-CLUSTER 'DUDOSOS'")
    print("=" * 70)

    easy, e_vec, e_idx = _cargar("easy")
    sodi, s_vec, s_idx = _cargar("sodimac")
    e_aligned = np.stack([_normalizar(e_vec)[e_idx[p["id_producto"]]] for p in easy])
    s_aligned = np.stack([_normalizar(s_vec)[s_idx[p["id_producto"]]] for p in sodi])
    cos_matrix = e_aligned @ s_aligned.T

    # agrupar por cluster
    c_easy = defaultdict(list)
    c_sodi = defaultdict(list)
    for i, p in enumerate(easy):
        if p.get("cluster_id", -1) != -1:
            c_easy[p["cluster_id"]].append(i)
    for i, p in enumerate(sodi):
        if p.get("cluster_id", -1) != -1:
            c_sodi[p["cluster_id"]].append(i)

    # recolectar pares intra-cluster con sus features
    pares = []
    for cid, eis in c_easy.items():
        sis = c_sodi.get(cid, [])
        for ei in eis:
            e = easy[ei]
            mb_e = e["metadata_basica"]
            mt_e = e["metadata_tecnica"]
            dim_e = mt_e.get("dimensiones") or {}
            for si in sis:
                s = sodi[si]
                mb_s = s["metadata_basica"]
                mt_s = s["metadata_tecnica"]
                dim_s = mt_s.get("dimensiones") or {}

                cos = float(cos_matrix[ei, si])
                me = mb_e.get("marca_norm") or ""
                ms = mb_s.get("marca_norm") or ""
                brand_match = 1 if me and ms and me == ms else 0

                tit_e = mb_e.get("titulo_limpio") or mb_e.get("titulo") or ""
                tit_s = mb_s.get("titulo_limpio") or mb_s.get("titulo") or ""
                jac = _jaccard(_tokens(tit_e), _tokens(tit_s))

                dl = dim_e.get("largo_mm"); dls = dim_s.get("largo_mm")
                dd = dim_e.get("diametro_mm"); dds = dim_s.get("diametro_mm")
                diff_l = abs(float(dl)-float(dls)) if dl is not None and dls is not None else None
                diff_d = abs(float(dd)-float(dds)) if dd is not None and dds is not None else None

                pares.append({
                    "cid": cid, "ei": ei, "si": si,
                    "cos": cos, "brand": brand_match, "jac": jac,
                    "diff_l": diff_l, "diff_d": diff_d,
                    "me": me, "ms": ms,
                    "tit_e": tit_e, "tit_s": tit_s,
                })

    print(f"\nTotal pares intra-cluster : {len(pares)}")

    # histograma de cosine
    def histo(vals, bins):
        h = Counter()
        for v in vals:
            for b_min, b_max in bins:
                if b_min <= v < b_max:
                    h[(b_min, b_max)] += 1
                    break
        return h

    cos_bins = [(-1, 0.3), (0.3, 0.5), (0.5, 0.65), (0.65, 0.75), (0.75, 0.85), (0.85, 1.01)]
    jac_bins = [(0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.45), (0.45, 0.6), (0.6, 1.01)]

    print(f"\n[A] Distribución de cosine_sim (TODOS los pares intra-cluster)")
    h = histo([p["cos"] for p in pares], cos_bins)
    for b in cos_bins:
        print(f"    [{b[0]:>5.2f}, {b[1]:>5.2f}): {h[b]:>5}")

    print(f"\n[B] Distribución cosine (solo brand_match=1)")
    h = histo([p["cos"] for p in pares if p["brand"]], cos_bins)
    for b in cos_bins:
        print(f"    [{b[0]:>5.2f}, {b[1]:>5.2f}): {h[b]:>5}")

    print(f"\n[C] Distribución jaccard (cosine >= 0.70, sin marca match)")
    h = histo([p["jac"] for p in pares if p["cos"] >= 0.70 and not p["brand"]], jac_bins)
    for b in jac_bins:
        print(f"    [{b[0]:>5.2f}, {b[1]:>5.2f}): {h[b]:>5}")

    # ¿cuántos pares marca_match + cosine < 0.65?
    marca_cos_bajo = [p for p in pares if p["brand"] and p["cos"] < 0.65]
    print(f"\n[D] brand_match=1 y cosine < 0.65: {len(marca_cos_bajo)} pares")
    print(f"    (con jaccard >= 0.30: {sum(1 for p in marca_cos_bajo if p['jac'] >= 0.30)})")
    print(f"    ejemplos:")
    for p in marca_cos_bajo[:5]:
        print(f"      cos={p['cos']:.2f} jac={p['jac']:.2f} marca={p['me']}")
        print(f"        E: {p['tit_e'][:80]}")
        print(f"        S: {p['tit_s'][:80]}")

    # ¿Pares cos alto + jac alto pero sin brand? (candidatos tier 3)
    cand_t3 = [p for p in pares if p["cos"] >= 0.75 and p["jac"] >= 0.30 and not p["brand"]]
    print(f"\n[E] Candidatos tier 3 flexible (cos>=0.75, jac>=0.30, sin brand match): {len(cand_t3)}")
    print(f"    (de los cuales sin marca en ninguno: {sum(1 for p in cand_t3 if not p['me'] and not p['ms'])})")
    print(f"    ejemplos:")
    for p in cand_t3[:10]:
        dims_str = f"Δl={p['diff_l']}mm Δd={p['diff_d']}mm" if p['diff_l'] is not None or p['diff_d'] is not None else "(sin dims)"
        print(f"      cos={p['cos']:.2f} jac={p['jac']:.2f} me={p['me'] or '∅'} ms={p['ms'] or '∅'} {dims_str}")
        print(f"        E: {p['tit_e'][:80]}")
        print(f"        S: {p['tit_s'][:80]}")

    # clusters con poca representación en positivos actuales
    clusters_con_bi = [cid for cid in c_easy if cid in c_sodi and len(c_easy[cid]) >= 2 and len(c_sodi[cid]) >= 2]
    print(f"\n[F] Clusters bi-tienda útiles: {len(clusters_con_bi)}")
    cluster_cos_max = {}
    for p in pares:
        cid = p["cid"]
        cluster_cos_max[cid] = max(cluster_cos_max.get(cid, 0), p["cos"])
    print(f"    Clusters donde el MEJOR cos intra es >= 0.70 : {sum(1 for v in cluster_cos_max.values() if v >= 0.70)}")
    print(f"    Clusters donde el MEJOR cos intra es >= 0.80 : {sum(1 for v in cluster_cos_max.values() if v >= 0.80)}")
    print(f"    Clusters donde el MEJOR cos intra es >= 0.90 : {sum(1 for v in cluster_cos_max.values() if v >= 0.90)}")


if __name__ == "__main__":
    main()
