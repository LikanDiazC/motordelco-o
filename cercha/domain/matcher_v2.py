"""Aplica el modelo v2 (features v1+v2) al espacio intra-cluster.

Diferencias vs matcher.py (v1):
  - Usa features v1 + v2 combinadas (21 features)
  - Compara los matches resultantes con los del modelo v1 (diff con leaky baseline)
  - Umbrales más estrictos porque el modelo ya incluye señales más finas

Salidas:
  data/matches_v2_candidatos.json   → todos los candidatos con proba ≥ UMBRAL_CAND
  data/matches_v2_top.json          → matches 1-a-1 de alta confianza
  data/matches_v2_vs_v1.json        → comparación: qué cambió vs el modelo v1
"""
from __future__ import annotations

import json
import pickle
from collections import defaultdict
from pathlib import Path

import numpy as np

from cercha.config import STORES
from cercha.domain.features_v2 import calcular_features_v2, FEATURE_V2_COLS

BASE = Path(r"C:\Users\Administrator\Documents\Buscop\motordelco-o\data")
IN_MODEL_V2   = BASE / "modelo_matcher_v2.pkl"
IN_MATCHES_V1 = BASE / "matches_top.json"
OUT_CANDS     = BASE / "matches_v2_candidatos.json"
OUT_TOP       = BASE / "matches_v2_top.json"
OUT_COMPARE   = BASE / "matches_v2_vs_v1.json"

UMBRAL_CAND      = 0.50
UMBRAL_ALTA_CONF = 0.75
TIE_EPSILON      = 0.02


def _normalizar_mat(mat):
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


def _features_par_v12(e, s, cos, impute, feature_cols):
    mb_e, mb_s = e["metadata_basica"], s["metadata_basica"]
    mt_e, mt_s = e["metadata_tecnica"], s["metadata_tecnica"]
    dim_e = mt_e.get("dimensiones") or {}
    dim_s = mt_s.get("dimensiones") or {}

    def _diff(a, b):
        if a is None or b is None: return None
        return abs(float(a) - float(b))

    dl = _diff(dim_e.get("largo_mm"), dim_s.get("largo_mm"))
    dd = _diff(dim_e.get("diametro_mm"), dim_s.get("diametro_mm"))
    tiene_dims = 1 if (dl is not None and dd is not None) else 0
    if dl is None: dl = impute["diff_largo_mm"]
    if dd is None: dd = impute["diff_diametro_mm"]

    tit_e = mb_e.get("titulo_limpio") or mb_e.get("titulo") or ""
    tit_s = mb_s.get("titulo_limpio") or mb_s.get("titulo") or ""
    me = mb_e.get("marca_norm") or ""
    ms = mb_s.get("marca_norm") or ""

    brand_match = 1 if me and ms and me == ms else 0
    mat_e = mt_e.get("material_norm") or mt_e.get("material") or ""
    mat_s = mt_s.get("material_norm") or mt_s.get("material") or ""
    material_match = 1 if mat_e and mat_s and mat_e.lower() == mat_s.lower() else 0
    c_e = mt_e.get("cantidad_empaque") or 1
    c_s = mt_s.get("cantidad_empaque") or 1
    rosca_match = 1 if (mt_e.get("tipo_rosca") and mt_e.get("tipo_rosca") == mt_s.get("tipo_rosca")) else 0
    cabeza_match = 1 if (mt_e.get("tipo_cabeza") and mt_e.get("tipo_cabeza") == mt_s.get("tipo_cabeza")) else 0

    # jaccard titulo v1 (tokens)
    import re
    _TOK = re.compile(r"[a-záéíóúñA-ZÁÉÍÓÚÑ0-9]+", re.IGNORECASE)
    tok_e = {t.lower() for t in _TOK.findall(tit_e) if len(t) > 1}
    tok_s = {t.lower() for t in _TOK.findall(tit_s) if len(t) > 1}
    jac = len(tok_e & tok_s) / max(1, len(tok_e | tok_s))

    ratio_p = 0.0
    pe, ps = mb_e.get("precio_clp", 0), mb_s.get("precio_clp", 0)
    if pe and ps:
        ratio_p = min(pe, ps) / max(pe, ps)

    mismo_cluster = 1 if (e.get("cluster_id") == s.get("cluster_id") and e.get("cluster_id") != -1) else 0

    v1 = {
        "cosine_sim":       round(float(cos), 4),
        "diff_largo_mm":    round(dl, 2),
        "diff_diametro_mm": round(dd, 2),
        "tiene_dims":       tiene_dims,
        "brand_match":      brand_match,
        "material_match":   material_match,
        "cantidad_match":   1 if c_e == c_s else 0,
        "tipo_rosca_match": rosca_match,
        "tipo_cabeza_match": cabeza_match,
        "jaccard_titulo":   round(jac, 4),
        "ratio_precio":     round(ratio_p, 4),
        "mismo_cluster":    mismo_cluster,
    }
    v2 = calcular_features_v2(tit_e, tit_s, me, ms)
    all_f = {**v1, **v2}
    # devolver en el orden de feature_cols
    return [all_f[c] for c in feature_cols]


def main():
    print("=" * 70)
    print("MATCHING V2: RF(v1+v2) SOBRE ESPACIO INTRA-CLUSTER")
    print("=" * 70)

    # cargar modelo v2
    print("\n[1/5] Cargando modelo v2...")
    with open(IN_MODEL_V2, "rb") as f:
        paquete = pickle.load(f)
    modelo = paquete["modelo"]
    cols = paquete["feature_cols"]
    impute = paquete["impute"]
    print(f"  Features: {len(cols)}  |  Imputación: {impute}")

    # cargar productos
    print("\n[2/5] Cargando productos y embeddings...")
    easy, e_vec, e_idx = _cargar("easy")
    sodi, s_vec, s_idx = _cargar("sodimac")
    e_al = np.stack([_normalizar_mat(e_vec)[e_idx[p['id_producto']]] for p in easy])
    s_al = np.stack([_normalizar_mat(s_vec)[s_idx[p['id_producto']]] for p in sodi])
    cos_matrix = e_al @ s_al.T

    # pares intra-cluster
    print("\n[3/5] Generando pares intra-cluster...")
    c_e, c_s = defaultdict(list), defaultdict(list)
    for i, p in enumerate(easy):
        if p.get("cluster_id", -1) != -1:
            c_e[p["cluster_id"]].append(i)
    for i, p in enumerate(sodi):
        if p.get("cluster_id", -1) != -1:
            c_s[p["cluster_id"]].append(i)

    pares = [(ei, si, cid) for cid, eis in c_e.items() for ei in eis for si in c_s.get(cid, [])]
    print(f"  Pares: {len(pares)}")

    # features
    print("\n[4/5] Calculando features y prediciendo...")
    X = np.zeros((len(pares), len(cols)), dtype=np.float32)
    for i, (ei, si, _) in enumerate(pares):
        X[i] = _features_par_v12(easy[ei], sodi[si], cos_matrix[ei, si], impute, cols)

    probas = modelo.predict_proba(X)[:, 1]
    print(f"  Distribución:")
    for thr in [0.95, 0.85, 0.75, 0.60, 0.50]:
        print(f"    proba >= {thr}: {int((probas >= thr).sum()):>5}")

    # construir candidatos
    print("\n[5/5] Construyendo candidatos y resolviendo 1-a-1...")
    candidatos = []
    for (ei, si, cid), p in zip(pares, probas):
        if p < UMBRAL_CAND:
            continue
        e, s = easy[ei], sodi[si]
        candidatos.append({
            "easy_id": e["id_producto"], "sodimac_id": s["id_producto"],
            "proba": round(float(p), 4),
            "cosine": round(float(cos_matrix[ei, si]), 4),
            "cluster_id": int(cid),
            "easy_sku": e.get("sku"), "sodimac_sku": s.get("sku"),
            "easy_titulo": e["metadata_basica"].get("titulo_limpio") or e["metadata_basica"].get("titulo"),
            "sodimac_titulo": s["metadata_basica"].get("titulo_limpio") or s["metadata_basica"].get("titulo"),
            "easy_marca": e["metadata_basica"].get("marca_norm"),
            "sodimac_marca": s["metadata_basica"].get("marca_norm"),
            "easy_precio": e["metadata_basica"].get("precio_clp"),
            "sodimac_precio": s["metadata_basica"].get("precio_clp"),
        })
    candidatos.sort(key=lambda r: -r["proba"])

    # resolución 1-a-1
    asig_e, asig_s = set(), set()
    por_e, por_s = defaultdict(list), defaultdict(list)
    for c in candidatos:
        por_e[c["easy_id"]].append(c)
        por_s[c["sodimac_id"]].append(c)

    matches_top, ambiguos = [], []
    for c in candidatos:
        if c["easy_id"] in asig_e or c["sodimac_id"] in asig_s:
            continue
        if c["proba"] < UMBRAL_ALTA_CONF:
            continue
        rivales_e = [x for x in por_e[c["easy_id"]] if x["sodimac_id"] != c["sodimac_id"] and x["sodimac_id"] not in asig_s]
        rivales_s = [x for x in por_s[c["sodimac_id"]] if x["easy_id"] != c["easy_id"] and x["easy_id"] not in asig_e]
        tie = any(abs(x["proba"] - c["proba"]) <= TIE_EPSILON for x in rivales_e + rivales_s)
        if tie:
            ambiguos.append(c)
            continue
        c["status"] = "match_1a1"
        matches_top.append(c)
        asig_e.add(c["easy_id"])
        asig_s.add(c["sodimac_id"])

    # guardar
    with open(OUT_CANDS, "w", encoding="utf-8") as f:
        json.dump(candidatos, f, ensure_ascii=False, indent=2)
    with open(OUT_TOP, "w", encoding="utf-8") as f:
        json.dump({
            "matches_1a1": matches_top,
            "ambiguos":    ambiguos,
            "meta": {
                "umbral_alta_conf": UMBRAL_ALTA_CONF,
                "umbral_candidato": UMBRAL_CAND,
                "total_candidatos": len(candidatos),
                "matches_1a1":      len(matches_top),
                "ambiguos":         len(ambiguos),
                "easy_matcheados":  len(asig_e),
                "sodi_matcheados":  len(asig_s),
            },
        }, f, ensure_ascii=False, indent=2)

    # comparación v2 vs v1
    v1_data = None
    if IN_MATCHES_V1.exists():
        with open(IN_MATCHES_V1, encoding="utf-8") as f:
            v1_data = json.load(f)

    comparacion = {
        "v2": {
            "matches_1a1":  len(matches_top),
            "ambiguos":     len(ambiguos),
            "candidatos":   len(candidatos),
        },
    }
    if v1_data:
        v1_matches = v1_data.get("matches_1a1", [])
        v1_amb = v1_data.get("ambiguos", [])
        comparacion["v1"] = {
            "matches_1a1": len(v1_matches),
            "ambiguos":    len(v1_amb),
            "candidatos":  v1_data.get("meta", {}).get("total_candidatos", 0),
        }
        # intersección de pares
        v1_pairs = {(m["easy_id"], m["sodimac_id"]) for m in v1_matches}
        v2_pairs = {(m["easy_id"], m["sodimac_id"]) for m in matches_top}
        comparacion["overlap"] = {
            "en_ambos":   len(v1_pairs & v2_pairs),
            "solo_v1":    len(v1_pairs - v2_pairs),
            "solo_v2":    len(v2_pairs - v1_pairs),
        }

    with open(OUT_COMPARE, "w", encoding="utf-8") as f:
        json.dump(comparacion, f, ensure_ascii=False, indent=2)

    # resumen
    print("\n" + "=" * 70)
    print("RESUMEN MATCHING V2")
    print("=" * 70)
    print(f"  Matches 1-a-1 (proba >= {UMBRAL_ALTA_CONF}): {len(matches_top)}")
    print(f"  Ambiguos (ties)                         : {len(ambiguos)}")
    print(f"  Cobertura Easy    : {len(asig_e)*100/len(easy):.1f}% ({len(asig_e)}/{len(easy)})")
    print(f"  Cobertura Sodimac : {len(asig_s)*100/len(sodi):.1f}% ({len(asig_s)}/{len(sodi)})")

    if v1_data:
        print(f"\n  COMPARACIÓN V2 vs V1:")
        print(f"    V1 matches 1-a-1 : {len(v1_data.get('matches_1a1', []))}")
        print(f"    V2 matches 1-a-1 : {len(matches_top)}")
        print(f"    En ambos         : {comparacion['overlap']['en_ambos']}")
        print(f"    Solo V1          : {comparacion['overlap']['solo_v1']}")
        print(f"    Solo V2          : {comparacion['overlap']['solo_v2']}")

    print(f"\n  Top 15 matches V2:")
    for m in matches_top[:15]:
        print(f"    [{m['proba']:.3f}] {m['easy_marca']:<12} | {m['sodimac_marca']:<12}")
        print(f"       E: {m['easy_titulo'][:75]}")
        print(f"       S: {m['sodimac_titulo'][:75]}")


if __name__ == "__main__":
    main()
