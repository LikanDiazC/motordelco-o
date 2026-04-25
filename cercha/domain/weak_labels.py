"""Generador de etiquetas débiles (weak labels) para entrenar el Random Forest.

Estrategia:
    POSITIVOS (alta confianza):
        - Mismo cluster
        - Misma marca_norm (no vacía)
        - Dimensiones coincidentes: |Δlargo| ≤ 1.0mm, |Δdiam| ≤ 0.5mm (si ambas tienen)
        - Cosine similarity ≥ 0.70
        - Material_norm compatible (igual o al menos uno vacío)

    NEGATIVOS FÁCILES (muestreo de clusters distintos):
        - Clusters diferentes
        - Cosine similarity < 0.35
        - Se muestrean ~3× la cantidad de positivos

    NEGATIVOS DUROS (mismo cluster pero distinto producto):
        - Mismo cluster
        - marca_norm distinta (ambas no vacías)
        - |Δlargo| > 15mm  O  |Δdiam| > 3mm  O  jaccard título < 0.15
        - Estos son los más valiosos para entrenar el RF

Features calculados para cada par (tanto positivos como negativos):
    cosine_sim, diff_largo_mm, diff_diametro_mm,
    brand_match, material_match, cantidad_match,
    mismo_cluster, jaccard_titulo, ratio_precio,
    tipo_rosca_match, tipo_cabeza_match

Salida:
    data/weak_labels.json   → lista de pares {sodimac_id, easy_id, label, features}
    data/weak_labels_reporte.json → estadísticas
"""

from __future__ import annotations

import json
import pickle
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from cercha.config import STORES

# ─── Parámetros ────────────────────────────────────────────────────────────
# Positivo tier 1 (estricto): marca + dims + cosine moderado
POS_COSINE_MIN        = 0.65   # cosine mínimo para positivo tier 1
POS_DIFF_LARGO_MAX    = 2.0    # mm de tolerancia en largo
POS_DIFF_DIAM_MAX     = 1.0    # mm de tolerancia en diámetro

# Positivo tier 2 (sin dimensiones disponibles): cosine alto + marca + jaccard
POS_T2_COSINE_MIN     = 0.82
POS_T2_JACCARD_MIN    = 0.30

# Positivo tier 3 (sin marca match, pero similitud dominante): cosine muy alto + jaccard alto
POS_T3_COSINE_MIN     = 0.85
POS_T3_JACCARD_MIN    = 0.35

# Positivo tier 4 (dims idénticas + cosine moderado + jaccard decente)
#   Captura pares donde las marcas son distintas pero las dimensiones coinciden
#   (caso frecuente: Easy dice marca X, Sodimac dice "generico")
POS_T4_COSINE_MIN     = 0.72
POS_T4_JACCARD_MIN    = 0.20
POS_T4_DIFF_LARGO_MAX = 1.0    # tolerancia estricta
POS_T4_DIFF_DIAM_MAX  = 0.5    # tolerancia estricta

# Marcas "comodín" (no descalifican: tratadas como si no hubiera marca declarada)
MARCAS_COMODIN = {"generico", "genérico", "sin marca", "", "home collection"}

# Negativos: balancear a ratios razonables
NEG_FACIL_COSINE_MAX  = 0.35
NEG_FACIL_RATIO       = 3      # 3× los positivos

NEG_DURO_DIFF_LARGO   = 20.0
NEG_DURO_DIFF_DIAM    = 4.0
NEG_DURO_JACCARD_MAX  = 0.10
NEG_DURO_COSINE_MAX   = 0.50   # además del resto, exigir cosine < 0.50
NEG_DURO_RATIO        = 3      # muestrear 3× los positivos

RANDOM_SEED = 42

BASE            = Path(r"C:\Users\Administrator\Documents\Buscop\motordelco-o\data")
OUT_LABELS      = BASE / "weak_labels.json"
OUT_REPORTE     = BASE / "weak_labels_reporte.json"

# ─── Utilidades ────────────────────────────────────────────────────────────
_TOKEN_RE = re.compile(r"[a-záéíóúñA-ZÁÉÍÓÚÑ0-9]+", re.IGNORECASE)

def _tokens(texto: str) -> set[str]:
    if not texto:
        return set()
    return {t.lower() for t in _TOKEN_RE.findall(texto) if len(t) > 1}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _ratio(x: float, y: float) -> float:
    if not x or not y:
        return 0.0
    return min(x, y) / max(x, y)


# ─── Carga de datos ────────────────────────────────────────────────────────
def _cargar_tienda(nombre: str):
    """Devuelve (productos_norm, vectores, index_por_id)."""
    ruta_norm    = STORES[nombre]["catalog_normalized"]
    ruta_cerebro = STORES[nombre]["brain"]

    with open(ruta_norm, encoding="utf-8") as f:
        productos = json.load(f)

    with open(ruta_cerebro, "rb") as f:
        brain = pickle.load(f)

    # index: id_producto → posición en el array de vectores
    idx = {m["id_producto"]: i for i, m in enumerate(brain["metadata"])}
    return productos, brain["vectores"].astype(np.float32), idx


def _normalizar(mat: np.ndarray) -> np.ndarray:
    """Normaliza cada fila a norma 1 (para cosine similarity como producto punto)."""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return mat / norms


# ─── Extracción de features de un par ──────────────────────────────────────
def _features_par(e: dict, s: dict, cosine: float) -> dict:
    """Features numéricos/booleanos de un par Easy×Sodimac."""
    mb_e, mb_s = e["metadata_basica"], s["metadata_basica"]
    mt_e, mt_s = e["metadata_tecnica"], s["metadata_tecnica"]
    dim_e      = mt_e.get("dimensiones") or {}
    dim_s      = mt_s.get("dimensiones") or {}

    def _diff(a, b):
        if a is None or b is None:
            return None
        return round(abs(float(a) - float(b)), 2)

    diff_largo = _diff(dim_e.get("largo_mm"),    dim_s.get("largo_mm"))
    diff_diam  = _diff(dim_e.get("diametro_mm"), dim_s.get("diametro_mm"))

    me, ms = mb_e.get("marca_norm") or "", mb_s.get("marca_norm") or ""
    brand_match = 1 if me and ms and me == ms else 0

    mat_e = mt_e.get("material_norm") or mt_e.get("material") or ""
    mat_s = mt_s.get("material_norm") or mt_s.get("material") or ""
    material_match = 1 if mat_e and mat_s and mat_e.lower() == mat_s.lower() else 0

    c_e = mt_e.get("cantidad_empaque") or 1
    c_s = mt_s.get("cantidad_empaque") or 1
    cantidad_match = 1 if c_e == c_s else 0

    r_e = mt_e.get("tipo_rosca") or ""
    r_s = mt_s.get("tipo_rosca") or ""
    rosca_match = 1 if r_e and r_s and r_e.lower() == r_s.lower() else 0

    k_e = mt_e.get("tipo_cabeza") or ""
    k_s = mt_s.get("tipo_cabeza") or ""
    cabeza_match = 1 if k_e and k_s and k_e.lower() == k_s.lower() else 0

    tit_e = mb_e.get("titulo_limpio") or mb_e.get("titulo") or ""
    tit_s = mb_s.get("titulo_limpio") or mb_s.get("titulo") or ""
    jac   = round(_jaccard(_tokens(tit_e), _tokens(tit_s)), 4)

    ratio_p = round(_ratio(mb_e.get("precio_clp", 0), mb_s.get("precio_clp", 0)), 4)

    mismo_cluster = 1 if e.get("cluster_id") == s.get("cluster_id") and e.get("cluster_id") != -1 else 0

    return {
        "cosine_sim":       round(float(cosine), 4),
        "diff_largo_mm":    diff_largo,
        "diff_diametro_mm": diff_diam,
        "brand_match":      brand_match,
        "material_match":   material_match,
        "cantidad_match":   cantidad_match,
        "tipo_rosca_match": rosca_match,
        "tipo_cabeza_match": cabeza_match,
        "jaccard_titulo":   jac,
        "ratio_precio":     ratio_p,
        "mismo_cluster":    mismo_cluster,
    }


# ─── Reglas de etiquetado ──────────────────────────────────────────────────
def _marca_conflicto(feat: dict) -> bool:
    """True si ambas marcas están DECLARADAS (no comodín) y son distintas."""
    me = (feat.get("_marca_e") or "").lower().strip()
    ms = (feat.get("_marca_s") or "").lower().strip()
    if me in MARCAS_COMODIN or ms in MARCAS_COMODIN:
        return False
    return bool(me) and bool(ms) and me != ms


def _es_positivo(feat: dict) -> tuple[bool, str]:
    """POS conservador por tiers. Devuelve (es_pos, tier)."""
    if not feat["mismo_cluster"]:
        return False, ""

    mat_e_tiene = feat.get("_mat_e_tiene", False)
    mat_s_tiene = feat.get("_mat_s_tiene", False)
    # si ambos tienen material, que coincida
    if mat_e_tiene and mat_s_tiene and not feat["material_match"]:
        return False, ""

    dl = feat["diff_largo_mm"]
    dd = feat["diff_diametro_mm"]

    # TIER 1: marca match + dims compatibles + cosine >= 0.65
    if (feat["brand_match"] and feat["cosine_sim"] >= POS_COSINE_MIN):
        dims_ok = True
        if dl is not None and dl > POS_DIFF_LARGO_MAX: dims_ok = False
        if dd is not None and dd > POS_DIFF_DIAM_MAX:  dims_ok = False
        if dims_ok:
            return True, "tier1_marca_dims"

    # TIER 2: marca match + cosine alto + jaccard alto (sin exigir dims)
    if (feat["brand_match"]
        and feat["cosine_sim"] >= POS_T2_COSINE_MIN
        and feat["jaccard_titulo"] >= POS_T2_JACCARD_MIN):
        if dl is not None and dl > POS_DIFF_LARGO_MAX: return False, ""
        if dd is not None and dd > POS_DIFF_DIAM_MAX:  return False, ""
        return True, "tier2_marca_cosine_jaccard"

    # TIER 3: cosine muy alto + jaccard alto, SIN conflicto de marca
    #   (acepta pares donde al menos una marca es comodín o una está vacía)
    if (feat["cosine_sim"] >= POS_T3_COSINE_MIN
        and feat["jaccard_titulo"] >= POS_T3_JACCARD_MIN
        and not _marca_conflicto(feat)):
        if dl is not None and dl > POS_DIFF_LARGO_MAX: return False, ""
        if dd is not None and dd > POS_DIFF_DIAM_MAX:  return False, ""
        return True, "tier3_cosine_jaccard"

    # TIER 4: DIMS IDÉNTICAS (ambas presentes) + cosine moderado + jaccard decente
    #   Capta tornillos/productos con dimensiones que son idénticos aunque la
    #   marca de Sodimac sea "generico" y la de Easy sea específica.
    if (dl is not None and dd is not None
        and dl <= POS_T4_DIFF_LARGO_MAX
        and dd <= POS_T4_DIFF_DIAM_MAX
        and feat["cosine_sim"] >= POS_T4_COSINE_MIN
        and feat["jaccard_titulo"] >= POS_T4_JACCARD_MIN
        and not _marca_conflicto(feat)):
        return True, "tier4_dims_identicas"

    return False, ""


def _es_negativo_duro(feat: dict) -> bool:
    """NEG intra-cluster: mismo cluster pero producto claramente distinto."""
    if not feat["mismo_cluster"]:
        return False
    if feat["cosine_sim"] >= NEG_DURO_COSINE_MAX:
        return False  # cosine alto → no es negativo duro confiable

    mar_e_tiene = feat.get("_mar_e_tiene", False)
    mar_s_tiene = feat.get("_mar_s_tiene", False)

    # marca distinta + alguno de estos: dims muy distintas, jaccard pobre
    if mar_e_tiene and mar_s_tiene and not feat["brand_match"]:
        if ((feat["diff_largo_mm"] is not None and feat["diff_largo_mm"] > NEG_DURO_DIFF_LARGO)
            or (feat["diff_diametro_mm"] is not None and feat["diff_diametro_mm"] > NEG_DURO_DIFF_DIAM)
            or feat["jaccard_titulo"] < NEG_DURO_JACCARD_MAX):
            return True
    # mismo cluster, marca igual, pero dims muy distintas → también negativo
    if feat["brand_match"]:
        if feat["diff_largo_mm"] is not None and feat["diff_largo_mm"] > NEG_DURO_DIFF_LARGO:
            return True
        if feat["diff_diametro_mm"] is not None and feat["diff_diametro_mm"] > NEG_DURO_DIFF_DIAM:
            return True
    return False


# ─── Pipeline principal ────────────────────────────────────────────────────
def generar_weak_labels():
    random.seed(RANDOM_SEED)

    print("=" * 70)
    print("GENERACIÓN DE WEAK LABELS")
    print("=" * 70)

    # --- cargar ---
    print("\n[1/5] Cargando productos y embeddings...")
    easy, e_vec, e_idx = _cargar_tienda("easy")
    sodi, s_vec, s_idx = _cargar_tienda("sodimac")
    print(f"    Easy   : {len(easy):>4} productos, embeddings {e_vec.shape}")
    print(f"    Sodimac: {len(sodi):>4} productos, embeddings {s_vec.shape}")

    # lookup id → producto normalizado
    easy_by_id = {p["id_producto"]: p for p in easy}
    sodi_by_id = {p["id_producto"]: p for p in sodi}

    # --- matriz de similitud coseno ---
    print("\n[2/5] Calculando matriz de similitud Easy×Sodimac...")
    e_norm = _normalizar(e_vec)
    s_norm = _normalizar(s_vec)
    # Reordenar para que coincida con el orden de `easy`/`sodi` (listas de normalizado)
    # Los arrays del brain están en orden de generación — armamos arrays alineados a las listas.
    e_aligned = np.stack([e_norm[e_idx[p["id_producto"]]] for p in easy])
    s_aligned = np.stack([s_norm[s_idx[p["id_producto"]]] for p in sodi])
    cos_matrix = e_aligned @ s_aligned.T  # shape (n_easy, n_sodi)
    print(f"    shape: {cos_matrix.shape}  |  rango [{cos_matrix.min():.3f}, {cos_matrix.max():.3f}]")

    # --- pares candidatos (mismo cluster) ---
    print("\n[3/5] Procesando pares intra-cluster...")
    clusters_easy: dict[int, list[int]] = defaultdict(list)  # cluster_id → [índices en lista easy]
    clusters_sodi: dict[int, list[int]] = defaultdict(list)
    for i, p in enumerate(easy):
        cid = p.get("cluster_id", -1)
        if cid != -1:
            clusters_easy[cid].append(i)
    for i, p in enumerate(sodi):
        cid = p.get("cluster_id", -1)
        if cid != -1:
            clusters_sodi[cid].append(i)

    pares_positivos = []
    pares_neg_duros = []
    pares_dudosos   = []
    total_intra = 0

    for cid, e_idxs in clusters_easy.items():
        s_idxs = clusters_sodi.get(cid, [])
        if not s_idxs:
            continue
        for ei in e_idxs:
            e = easy[ei]
            # marcadores auxiliares para reglas (tiene material / marca no vacía)
            marca_e = e["metadata_basica"].get("marca_norm") or ""
            _mar_e = bool(marca_e)
            _mat_e = bool(e["metadata_tecnica"].get("material_norm") or e["metadata_tecnica"].get("material"))
            for si in s_idxs:
                s = sodi[si]
                total_intra += 1
                cos = cos_matrix[ei, si]
                feat = _features_par(e, s, cos)
                marca_s = s["metadata_basica"].get("marca_norm") or ""
                feat["_mar_e_tiene"] = _mar_e
                feat["_mar_s_tiene"] = bool(marca_s)
                feat["_mat_e_tiene"] = _mat_e
                feat["_mat_s_tiene"] = bool(s["metadata_tecnica"].get("material_norm") or s["metadata_tecnica"].get("material"))
                feat["_marca_e"] = marca_e
                feat["_marca_s"] = marca_s

                es_pos, tier = _es_positivo(feat)
                if es_pos:
                    feat["_tier"] = tier
                    pares_positivos.append((e, s, feat))
                elif _es_negativo_duro(feat):
                    pares_neg_duros.append((e, s, feat))
                else:
                    pares_dudosos.append((e, s, feat))

    # muestrear negativos duros al ratio target
    random.shuffle(pares_neg_duros)
    target_neg_duros = len(pares_positivos) * NEG_DURO_RATIO
    pares_neg_duros_muestra = pares_neg_duros[:target_neg_duros]

    print(f"    pares intra-cluster totales   : {total_intra}")
    print(f"    positivos confiables          : {len(pares_positivos)}")
    print(f"    negativos duros (candidatos)  : {len(pares_neg_duros)}")
    print(f"    negativos duros (muestreados) : {len(pares_neg_duros_muestra)}")
    print(f"    dudosos (se descartan)        : {len(pares_dudosos)}")

    # desglose por tier de positivos
    tier_counts = Counter(f.get("_tier") for _, _, f in pares_positivos)
    print(f"\n    Positivos por tier:")
    for tier, n in tier_counts.most_common():
        print(f"      {tier}: {n}")

    pares_neg_duros = pares_neg_duros_muestra

    # --- negativos fáciles (clusters distintos) ---
    print("\n[4/5] Muestreando negativos fáciles inter-cluster...")
    n_neg_facil = len(pares_positivos) * NEG_FACIL_RATIO
    # tomamos pares aleatorios que estén en clusters distintos y con cosine < NEG_FACIL_COSINE_MAX
    pares_neg_faciles = []
    intentos = 0
    max_intentos = n_neg_facil * 20
    while len(pares_neg_faciles) < n_neg_facil and intentos < max_intentos:
        ei = random.randrange(len(easy))
        si = random.randrange(len(sodi))
        intentos += 1
        e, s = easy[ei], sodi[si]
        ce = e.get("cluster_id", -1)
        cs = s.get("cluster_id", -1)
        if ce == cs and ce != -1:
            continue
        cos = cos_matrix[ei, si]
        if cos >= NEG_FACIL_COSINE_MAX:
            continue
        feat = _features_par(e, s, cos)
        pares_neg_faciles.append((e, s, feat))
    print(f"    negativos fáciles generados: {len(pares_neg_faciles)} (intentos: {intentos})")

    # --- persistencia ---
    print("\n[5/5] Persistiendo...")

    def _registro(e, s, feat, label):
        # quitar marcadores auxiliares del output final
        feat_out = {k: v for k, v in feat.items() if not k.startswith("_")}
        return {
            "easy_id":    e["id_producto"],
            "sodimac_id": s["id_producto"],
            "label":      label,
            "features":   feat_out,
            # contexto para inspección manual:
            "ctx": {
                "easy_titulo":    e["metadata_basica"].get("titulo_limpio") or e["metadata_basica"].get("titulo"),
                "sodimac_titulo": s["metadata_basica"].get("titulo_limpio") or s["metadata_basica"].get("titulo"),
                "easy_marca":     e["metadata_basica"].get("marca_norm"),
                "sodimac_marca":  s["metadata_basica"].get("marca_norm"),
                "cluster_id":     e.get("cluster_id") if e.get("cluster_id") == s.get("cluster_id") else -1,
                "easy_sku":       e.get("sku"),
                "sodimac_sku":    s.get("sku"),
                "fuente":         None,  # se llena abajo
            },
        }

    records = []
    for e, s, f in pares_positivos:
        r = _registro(e, s, f, 1); r["ctx"]["fuente"] = "pos_cluster"; records.append(r)
    for e, s, f in pares_neg_duros:
        r = _registro(e, s, f, 0); r["ctx"]["fuente"] = "neg_duro_cluster"; records.append(r)
    for e, s, f in pares_neg_faciles:
        r = _registro(e, s, f, 0); r["ctx"]["fuente"] = "neg_facil_inter"; records.append(r)

    with open(OUT_LABELS, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # --- reporte ---
    reporte = {
        "total_pares":       len(records),
        "positivos":         len(pares_positivos),
        "negativos_duros":   len(pares_neg_duros),
        "negativos_faciles": len(pares_neg_faciles),
        "ratio_pos_neg":     round(len(pares_positivos) / max(1, len(pares_neg_duros)+len(pares_neg_faciles)), 3),
        "pares_intra_cluster_total": total_intra,
        "pares_descartados":         len(pares_dudosos),
        "parametros": {
            "pos_cosine_min":       POS_COSINE_MIN,
            "pos_diff_largo_max":   POS_DIFF_LARGO_MAX,
            "pos_diff_diam_max":    POS_DIFF_DIAM_MAX,
            "neg_facil_cosine_max": NEG_FACIL_COSINE_MAX,
            "neg_facil_ratio":      NEG_FACIL_RATIO,
            "neg_duro_diff_largo":  NEG_DURO_DIFF_LARGO,
            "neg_duro_diff_diam":   NEG_DURO_DIFF_DIAM,
            "neg_duro_jaccard_max": NEG_DURO_JACCARD_MAX,
        },
        "distribucion_positivos_por_cluster": dict(
            Counter(r["ctx"]["cluster_id"] for r in records if r["label"] == 1).most_common()
        ),
        "marcas_top_en_positivos": dict(
            Counter(r["ctx"]["easy_marca"] for r in records if r["label"] == 1).most_common(10)
        ),
    }

    with open(OUT_REPORTE, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    print(f"\n  Labels guardados: {OUT_LABELS}")
    print(f"  Reporte         : {OUT_REPORTE}")

    # --- resumen ---
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"  Total pares etiquetados: {len(records)}")
    print(f"    Positivos            : {len(pares_positivos)}")
    print(f"    Negativos duros      : {len(pares_neg_duros)}")
    print(f"    Negativos fáciles    : {len(pares_neg_faciles)}")
    print(f"  Ratio pos:neg          : 1:{round((len(pares_neg_duros)+len(pares_neg_faciles))/max(1,len(pares_positivos)),2)}")
    print(f"\n  Top marcas en positivos:")
    for marca, n in reporte["marcas_top_en_positivos"].items():
        print(f"    {marca:<20} {n}")

    return records, reporte


if __name__ == "__main__":
    generar_weak_labels()
