"""Genera un 'golden set' con labels más confiables que los weak labels.

IDEA CLAVE (ortogonalidad):
Los weak_labels fueron generados con reglas sobre: cosine_sim, brand_match,
jaccard_titulo, diff_largo_mm, diff_diametro_mm.

Si re-etiquetáramos usando exclusivamente esos mismos features, el RF siempre
alcanzaría F1=1.0 por memorización (como vimos en el trainer v1).

Solución: etiquetar usando features v2 (char n-grams, números parseados,
primera palabra significativa, Levenshtein de marcas, etc.) y features
físicos duros (dims). Como el modelo final usará MIX de features v1 + v2,
podrá aprender patrones nuevos sin colapsar a "memorizar reglas".

Reglas del golden set (MUY CONSERVADORAS — prefiero pocos labels pero limpios):

POSITIVO GOLDEN (pares "obviamente iguales"):
  - mismo_cluster = 1
  - primera palabra significativa coincide
  - char_jaccard_3gram >= 0.45
  - tokens_raros_jaccard >= 0.30
  - nums_overlap >= 2 (comparten 2+ números: dims, modelos, etc.)
  - Si ambos tienen dims: |Δlargo| <= 1.5mm AND |Δdiam| <= 0.8mm
  - NO exige brand_match (queremos generalizar a marcas distintas)

NEGATIVO GOLDEN (pares "obviamente distintos"):
  Dos variantes:
    a) Intra-cluster ruidoso:
       - mismo_cluster = 1
       - char_jaccard_3gram < 0.10
       - tokens_raros_jaccard < 0.05
       - primera_palabra_match = 0
       - nums_overlap = 0
    b) Inter-cluster claro:
       - mismo_cluster = 0
       - char_jaccard_3gram < 0.08
       - tokens_raros_jaccard = 0
       - cosine_sim < 0.25

Salida:
  data/golden_set.json → pares etiquetados con features v1 + v2 unificadas
"""
from __future__ import annotations

import json
import pickle
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from cercha.config import STORES
from cercha.domain.features_v2 import calcular_features_v2

BASE = Path(r"C:\Users\Administrator\Documents\Buscop\motordelco-o\data")
OUT_GOLDEN  = BASE / "golden_set.json"
OUT_REPORTE = BASE / "golden_set_reporte.json"

# ─── Reglas golden ─────────────────────────────────────────────────────────
# POSITIVO
POS_CHAR_JACC_MIN     = 0.30   # era 0.45 (muy estricto)
POS_TOKENS_RAROS_MIN  = 0.20   # era 0.30
POS_NUMS_OVERLAP_MIN  = 1      # era 2 (perdíamos casos con 1 único número clave)
POS_DIFF_LARGO_MAX    = 1.5
POS_DIFF_DIAM_MAX     = 0.8

# NEGATIVO intra-cluster ruidoso
NEG_CHAR_JACC_MAX     = 0.12   # era 0.10
NEG_TOKENS_RAROS_MAX  = 0.05

# NEGATIVO inter-cluster claro
NEG_INTER_COSINE_MAX  = 0.30   # era 0.25
NEG_INTER_CHAR_MAX    = 0.15   # era 0.08

NEG_INTER_RATIO       = 3   # 3× los positivos
NEG_INTRA_RATIO       = 2   # 2× los positivos (son los más valiosos)

RANDOM_SEED = 7


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


def _titulos_y_marca(p):
    mb = p["metadata_basica"]
    tit = mb.get("titulo_limpio") or mb.get("titulo") or ""
    marca = mb.get("marca_norm") or ""
    return tit, marca


def _diff(a, b):
    if a is None or b is None:
        return None
    return abs(float(a) - float(b))


def _features_completos(e, s, cos):
    """Unifica features v1 (weak) + v2 (ortogonales) en un solo dict."""
    mb_e, mb_s = e["metadata_basica"], s["metadata_basica"]
    mt_e, mt_s = e["metadata_tecnica"], s["metadata_tecnica"]
    dim_e = mt_e.get("dimensiones") or {}
    dim_s = mt_s.get("dimensiones") or {}

    dl = _diff(dim_e.get("largo_mm"), dim_s.get("largo_mm"))
    dd = _diff(dim_e.get("diametro_mm"), dim_s.get("diametro_mm"))

    tit_e, me = _titulos_y_marca(e)
    tit_s, ms = _titulos_y_marca(s)

    brand_match = 1 if me and ms and me == ms else 0
    mat_e = mt_e.get("material_norm") or mt_e.get("material") or ""
    mat_s = mt_s.get("material_norm") or mt_s.get("material") or ""
    material_match = 1 if mat_e and mat_s and mat_e.lower() == mat_s.lower() else 0

    c_e = mt_e.get("cantidad_empaque") or 1
    c_s = mt_s.get("cantidad_empaque") or 1

    # feat v2
    v2 = calcular_features_v2(tit_e, tit_s, me, ms)

    # jaccard de tokens completo (v1)
    from cercha.domain.features_v2 import _tokens as _tok
    tok_e = set(_tok(tit_e))
    tok_s = set(_tok(tit_s))
    jac_v1 = len(tok_e & tok_s) / max(1, len(tok_e | tok_s))

    feats = {
        # v1
        "cosine_sim":       round(float(cos), 4),
        "diff_largo_mm":    dl,
        "diff_diametro_mm": dd,
        "brand_match":      brand_match,
        "material_match":   material_match,
        "cantidad_match":   1 if c_e == c_s else 0,
        "tipo_rosca_match": 1 if (mt_e.get("tipo_rosca") and mt_e.get("tipo_rosca") == mt_s.get("tipo_rosca")) else 0,
        "tipo_cabeza_match": 1 if (mt_e.get("tipo_cabeza") and mt_e.get("tipo_cabeza") == mt_s.get("tipo_cabeza")) else 0,
        "jaccard_titulo":   round(jac_v1, 4),
        "ratio_precio":     _ratio_precio(mb_e.get("precio_clp", 0), mb_s.get("precio_clp", 0)),
        "mismo_cluster":    1 if (e.get("cluster_id") == s.get("cluster_id") and e.get("cluster_id") != -1) else 0,
        # v2
        **v2,
    }
    return feats


def _ratio_precio(x, y):
    if not x or not y:
        return 0.0
    return round(min(x, y) / max(x, y), 4)


# ─── Reglas de clasificación ──────────────────────────────────────────────
def _es_positivo_golden(f: dict) -> bool:
    if not f["mismo_cluster"]:
        return False
    if f["v2_primera_palabra_match"] != 1:
        return False
    if f["v2_char_jaccard_3gram"] < POS_CHAR_JACC_MIN:
        return False
    if f["v2_tokens_raros_jaccard"] < POS_TOKENS_RAROS_MIN:
        return False
    if f["v2_nums_overlap"] < POS_NUMS_OVERLAP_MIN:
        return False
    # si ambos tienen dims, verificar compatibilidad
    if f["diff_largo_mm"] is not None and f["diff_largo_mm"] > POS_DIFF_LARGO_MAX:
        return False
    if f["diff_diametro_mm"] is not None and f["diff_diametro_mm"] > POS_DIFF_DIAM_MAX:
        return False
    # si ambos tienen material, que coincida
    mat_e = f.get("material_match")
    # (no podemos saber si AMBOS tienen material desde el feat solo; lo dejamos)
    return True


def _es_negativo_intra(f: dict) -> bool:
    if not f["mismo_cluster"]:
        return False
    if f["v2_char_jaccard_3gram"] >= NEG_CHAR_JACC_MAX:
        return False
    if f["v2_tokens_raros_jaccard"] >= NEG_TOKENS_RAROS_MAX:
        return False
    if f["v2_primera_palabra_match"] != 0:
        return False
    if f["v2_nums_overlap"] != 0:
        return False
    return True


def _es_negativo_inter(f: dict) -> bool:
    if f["mismo_cluster"]:
        return False
    if f["cosine_sim"] >= NEG_INTER_COSINE_MAX:
        return False
    if f["v2_char_jaccard_3gram"] >= NEG_INTER_CHAR_MAX:
        return False
    # sin exigir tokens_raros=0 (era demasiado)
    return True


# ─── Pipeline principal ───────────────────────────────────────────────────
def generar_golden_set():
    random.seed(RANDOM_SEED)

    print("=" * 70)
    print("GENERACIÓN DE GOLDEN SET (reglas ortogonales a weak labels)")
    print("=" * 70)

    # cargar
    easy, e_vec, e_idx = _cargar("easy")
    sodi, s_vec, s_idx = _cargar("sodimac")
    print(f"  Easy: {len(easy)}  |  Sodimac: {len(sodi)}")

    e_aligned = np.stack([_normalizar(e_vec)[e_idx[p['id_producto']]] for p in easy])
    s_aligned = np.stack([_normalizar(s_vec)[s_idx[p['id_producto']]] for p in sodi])
    cos_matrix = e_aligned @ s_aligned.T

    # clusters
    c_easy = defaultdict(list)
    c_sodi = defaultdict(list)
    for i, p in enumerate(easy):
        if p.get("cluster_id", -1) != -1:
            c_easy[p["cluster_id"]].append(i)
    for i, p in enumerate(sodi):
        if p.get("cluster_id", -1) != -1:
            c_sodi[p["cluster_id"]].append(i)

    # --- procesar pares intra-cluster ---
    print("\n[1/3] Clasificando pares intra-cluster...")
    positivos = []
    neg_intra = []
    for cid, eis in c_easy.items():
        sis = c_sodi.get(cid, [])
        for ei in eis:
            for si in sis:
                cos = float(cos_matrix[ei, si])
                feats = _features_completos(easy[ei], sodi[si], cos)
                if _es_positivo_golden(feats):
                    positivos.append((easy[ei], sodi[si], feats, cid))
                elif _es_negativo_intra(feats):
                    neg_intra.append((easy[ei], sodi[si], feats, cid))

    print(f"  Positivos golden       : {len(positivos)}")
    print(f"  Neg intra-cluster (cand): {len(neg_intra)}")

    # muestra de neg_intra al ratio target
    random.shuffle(neg_intra)
    neg_intra = neg_intra[:len(positivos) * NEG_INTRA_RATIO]

    # --- negativos inter-cluster ---
    print("\n[2/3] Muestreando negativos inter-cluster...")
    target_inter = len(positivos) * NEG_INTER_RATIO
    neg_inter = []
    intentos = 0
    max_intentos = target_inter * 50
    while len(neg_inter) < target_inter and intentos < max_intentos:
        ei = random.randrange(len(easy))
        si = random.randrange(len(sodi))
        intentos += 1
        ce = easy[ei].get("cluster_id", -1)
        cs = sodi[si].get("cluster_id", -1)
        if ce == cs and ce != -1:
            continue
        cos = float(cos_matrix[ei, si])
        if cos >= NEG_INTER_COSINE_MAX:
            continue
        feats = _features_completos(easy[ei], sodi[si], cos)
        if _es_negativo_inter(feats):
            neg_inter.append((easy[ei], sodi[si], feats, -1))
    print(f"  Negativos inter-cluster : {len(neg_inter)}  (intentos: {intentos})")

    # --- persistir ---
    print("\n[3/3] Guardando...")
    registros = []
    for e, s, f, cid in positivos:
        registros.append(_registro(e, s, f, 1, cid, "pos_golden_v2"))
    for e, s, f, cid in neg_intra:
        registros.append(_registro(e, s, f, 0, cid, "neg_intra_golden_v2"))
    for e, s, f, cid in neg_inter:
        registros.append(_registro(e, s, f, 0, cid, "neg_inter_golden_v2"))

    with open(OUT_GOLDEN, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)

    reporte = {
        "total":      len(registros),
        "positivos":  len(positivos),
        "neg_intra":  len(neg_intra),
        "neg_inter":  len(neg_inter),
        "ratio_pos_neg": round(len(positivos) / max(1, len(neg_intra) + len(neg_inter)), 3),
        "parametros": {
            "POS_CHAR_JACC_MIN":    POS_CHAR_JACC_MIN,
            "POS_TOKENS_RAROS_MIN": POS_TOKENS_RAROS_MIN,
            "POS_NUMS_OVERLAP_MIN": POS_NUMS_OVERLAP_MIN,
            "NEG_CHAR_JACC_MAX":    NEG_CHAR_JACC_MAX,
            "NEG_INTER_COSINE_MAX": NEG_INTER_COSINE_MAX,
            "NEG_INTRA_RATIO":      NEG_INTRA_RATIO,
            "NEG_INTER_RATIO":      NEG_INTER_RATIO,
        },
        "positivos_por_cluster": dict(Counter(r["cluster_id"] for r in registros if r["label"] == 1).most_common()),
        "marcas_positivos":      dict(Counter(r["ctx"]["easy_marca"] for r in registros if r["label"] == 1).most_common(15)),
    }
    with open(OUT_REPORTE, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    print(f"  Golden set : {OUT_GOLDEN}")
    print(f"  Reporte    : {OUT_REPORTE}")

    # resumen
    print("\n" + "=" * 70)
    print("RESUMEN GOLDEN SET")
    print("=" * 70)
    print(f"  Total registros      : {len(registros)}")
    print(f"  Positivos (golden)   : {len(positivos)}")
    print(f"  Negativos intra      : {len(neg_intra)}")
    print(f"  Negativos inter      : {len(neg_inter)}")
    if registros:
        ratio = (len(neg_intra) + len(neg_inter)) / max(1, len(positivos))
        print(f"  Ratio pos:neg        : 1:{ratio:.1f}")
    print(f"\n  Top marcas en positivos:")
    for marca, n in reporte["marcas_positivos"].items():
        print(f"    {marca or '(vacía)':<20} {n}")


def _registro(e, s, feats, label, cid, fuente):
    return {
        "easy_id":    e["id_producto"],
        "sodimac_id": s["id_producto"],
        "label":      label,
        "cluster_id": cid,
        "features":   feats,
        "ctx": {
            "easy_titulo":    e["metadata_basica"].get("titulo_limpio") or e["metadata_basica"].get("titulo"),
            "sodimac_titulo": s["metadata_basica"].get("titulo_limpio") or s["metadata_basica"].get("titulo"),
            "easy_marca":     e["metadata_basica"].get("marca_norm"),
            "sodimac_marca":  s["metadata_basica"].get("marca_norm"),
            "easy_sku":       e.get("sku"),
            "sodimac_sku":    s.get("sku"),
            "fuente":         fuente,
        },
    }


if __name__ == "__main__":
    generar_golden_set()
