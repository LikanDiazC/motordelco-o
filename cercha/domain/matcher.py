"""Aplica el modelo entrenado para encontrar matches reales Easy↔Sodimac.

Pipeline:
  1. Carga productos normalizados + embeddings + modelo entrenado
  2. Genera TODOS los pares intra-cluster (blocking por clustering)
  3. Calcula features para cada par
  4. Predice probabilidad de match con el modelo
  5. Filtra por umbral + resuelve conflictos (un Sodimac ↔ un Easy)
  6. Exporta candidatos ordenados por confianza a JSON y Excel

Salida:
  data/matches_candidatos.json   → todos los pares con proba > 0.2 (para auditar)
  data/matches_top.json          → solo los matches de alta confianza (pos 1-a-1)
  data/matches_revisar.xlsx      → vista para inspección humana

Selección 1-a-1: un producto de Sodimac solo se asocia a UN producto de Easy
(el de mayor probabilidad), salvo que la proba sea muy cercana (±0.02) en cuyo
caso se marcan ambos para revisión manual.
"""
from __future__ import annotations

import json
import pickle
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from cercha.config import STORES

BASE = Path(r"C:\Users\Administrator\Documents\Buscop\motordelco-o\data")
IN_MODEL       = BASE / "modelo_matcher.pkl"
OUT_CANDIDATOS = BASE / "matches_candidatos.json"
OUT_TOP        = BASE / "matches_top.json"
OUT_XLSX       = BASE / "matches_revisar.xlsx"

UMBRAL_CANDIDATO = 0.50    # mínimo para guardar como candidato
UMBRAL_ALTA_CONF = 0.85    # mínimo para top-matches auto-aprobados
TIE_EPSILON      = 0.02    # si dos pares de un mismo producto tienen proba±0.02 → ambos a revisar

_TOKEN_RE = re.compile(r"[a-záéíóúñA-ZÁÉÍÓÚÑ0-9]+", re.IGNORECASE)

def _tokens(texto: str) -> set[str]:
    if not texto: return set()
    return {t.lower() for t in _TOKEN_RE.findall(texto) if len(t) > 1}

def _jaccard(a, b):
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)

def _ratio(x, y):
    if not x or not y: return 0.0
    return min(x, y) / max(x, y)


def _normalizar_mat(mat):
    n = np.linalg.norm(mat, axis=1, keepdims=True)
    n = np.where(n == 0, 1, n)
    return mat / n


def _cargar_tienda(nombre):
    with open(STORES[nombre]["catalog_normalized"], encoding="utf-8") as f:
        productos = json.load(f)
    with open(STORES[nombre]["brain"], "rb") as f:
        brain = pickle.load(f)
    idx = {m["id_producto"]: i for i, m in enumerate(brain["metadata"])}
    return productos, brain["vectores"].astype(np.float32), idx


def _features_par(e, s, cos, impute):
    mb_e, mb_s = e["metadata_basica"], s["metadata_basica"]
    mt_e, mt_s = e["metadata_tecnica"], s["metadata_tecnica"]
    dim_e = mt_e.get("dimensiones") or {}
    dim_s = mt_s.get("dimensiones") or {}

    def _diff(a, b):
        if a is None or b is None: return None
        return abs(float(a) - float(b))

    dl = _diff(dim_e.get("largo_mm"),    dim_s.get("largo_mm"))
    dd = _diff(dim_e.get("diametro_mm"), dim_s.get("diametro_mm"))
    tiene_dims = 1 if (dl is not None and dd is not None) else 0
    if dl is None: dl = impute["diff_largo_mm"]
    if dd is None: dd = impute["diff_diametro_mm"]

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
    jac = _jaccard(_tokens(tit_e), _tokens(tit_s))
    ratio_p = _ratio(mb_e.get("precio_clp", 0), mb_s.get("precio_clp", 0))

    mismo_cluster = 1 if (e.get("cluster_id") == s.get("cluster_id") and e.get("cluster_id") != -1) else 0

    # orden EXACTO que espera el modelo
    return [
        round(float(cos), 4),
        round(dl, 2),
        round(dd, 2),
        tiene_dims,
        brand_match,
        material_match,
        cantidad_match,
        rosca_match,
        cabeza_match,
        round(jac, 4),
        round(ratio_p, 4),
        mismo_cluster,
    ]


def main():
    print("=" * 70)
    print("MATCHING EASY↔SODIMAC CON RANDOM FOREST")
    print("=" * 70)

    # --- cargar modelo ---
    print("\n[1/6] Cargando modelo entrenado...")
    with open(IN_MODEL, "rb") as f:
        paquete = pickle.load(f)
    modelo   = paquete["modelo"]
    impute   = paquete["impute"]
    tipo     = paquete["modelo_tipo"]
    umbral_opt = paquete["umbral_optimo"]
    print(f"  Tipo: {tipo}")
    print(f"  Umbral óptimo (del entrenamiento): {umbral_opt:.3f}")
    print(f"  Imputación: {impute}")

    # --- cargar productos y embeddings ---
    print("\n[2/6] Cargando productos y embeddings...")
    easy, e_vec, e_idx = _cargar_tienda("easy")
    sodi, s_vec, s_idx = _cargar_tienda("sodimac")
    print(f"  Easy   : {len(easy)}")
    print(f"  Sodimac: {len(sodi)}")

    # matriz coseno alineada
    e_aligned = np.stack([_normalizar_mat(e_vec)[e_idx[p['id_producto']]] for p in easy])
    s_aligned = np.stack([_normalizar_mat(s_vec)[s_idx[p['id_producto']]] for p in sodi])
    cos_matrix = e_aligned @ s_aligned.T

    # --- generar pares intra-cluster ---
    print("\n[3/6] Generando pares intra-cluster (blocking)...")
    c_easy = defaultdict(list)
    c_sodi = defaultdict(list)
    for i, p in enumerate(easy):
        if p.get("cluster_id", -1) != -1:
            c_easy[p["cluster_id"]].append(i)
    for i, p in enumerate(sodi):
        if p.get("cluster_id", -1) != -1:
            c_sodi[p["cluster_id"]].append(i)

    pares = []  # (ei, si, cid)
    for cid, eis in c_easy.items():
        for ei in eis:
            for si in c_sodi.get(cid, []):
                pares.append((ei, si, cid))
    print(f"  Total pares: {len(pares)}")

    # --- calcular features + predecir ---
    print("\n[4/6] Calculando features y prediciendo...")
    X = np.zeros((len(pares), 12), dtype=np.float32)
    for idx, (ei, si, _) in enumerate(pares):
        cos = cos_matrix[ei, si]
        X[idx] = _features_par(easy[ei], sodi[si], cos, impute)

    probas = modelo.predict_proba(X)[:, 1]
    print(f"  Distribución de probabilidad:")
    for thr in [0.9, 0.8, 0.7, 0.5, 0.3]:
        print(f"    proba >= {thr}: {int((probas >= thr).sum()):>5}")

    # --- construir candidatos ---
    print("\n[5/6] Filtrando candidatos y resolviendo 1-a-1...")
    candidatos = []
    for (ei, si, cid), p in zip(pares, probas):
        if p < UMBRAL_CANDIDATO:
            continue
        e, s = easy[ei], sodi[si]
        candidatos.append({
            "easy_id":    e["id_producto"],
            "sodimac_id": s["id_producto"],
            "proba":      round(float(p), 4),
            "cosine":     round(float(cos_matrix[ei, si]), 4),
            "cluster_id": int(cid),
            "easy_sku":   e.get("sku"),
            "sodimac_sku": s.get("sku"),
            "easy_titulo":    e["metadata_basica"].get("titulo_limpio") or e["metadata_basica"].get("titulo"),
            "sodimac_titulo": s["metadata_basica"].get("titulo_limpio") or s["metadata_basica"].get("titulo"),
            "easy_marca":     e["metadata_basica"].get("marca_norm"),
            "sodimac_marca":  s["metadata_basica"].get("marca_norm"),
            "easy_precio":    e["metadata_basica"].get("precio_clp"),
            "sodimac_precio": s["metadata_basica"].get("precio_clp"),
        })

    candidatos.sort(key=lambda r: -r["proba"])
    print(f"  Candidatos (proba >= {UMBRAL_CANDIDATO}): {len(candidatos)}")

    # resolución 1-a-1 (Hungarian-lite): recorrer ordenado y asignar
    asignado_easy = set()
    asignado_sodi = set()
    matches_top = []
    ambiguos    = []
    # agrupar candidatos por (easy_id) y por (sodi_id) para detectar ties
    por_easy = defaultdict(list)
    por_sodi = defaultdict(list)
    for c in candidatos:
        por_easy[c["easy_id"]].append(c)
        por_sodi[c["sodimac_id"]].append(c)

    for c in candidatos:
        if c["easy_id"] in asignado_easy or c["sodimac_id"] in asignado_sodi:
            continue
        if c["proba"] < UMBRAL_ALTA_CONF:
            continue
        # detectar tie en las listas del easy/sodi
        rivales_easy = [x for x in por_easy[c["easy_id"]] if x["sodimac_id"] != c["sodimac_id"]]
        rivales_sodi = [x for x in por_sodi[c["sodimac_id"]] if x["easy_id"] != c["easy_id"]]
        tie_e = any(abs(x["proba"] - c["proba"]) <= TIE_EPSILON for x in rivales_easy if x["sodimac_id"] not in asignado_sodi)
        tie_s = any(abs(x["proba"] - c["proba"]) <= TIE_EPSILON for x in rivales_sodi if x["easy_id"] not in asignado_easy)
        if tie_e or tie_s:
            ambiguos.append(c)
            continue
        c["status"] = "match_1a1"
        matches_top.append(c)
        asignado_easy.add(c["easy_id"])
        asignado_sodi.add(c["sodimac_id"])

    print(f"  Matches 1-a-1 (alta confianza): {len(matches_top)}")
    print(f"  Ambiguos (ties):                {len(ambiguos)}")
    print(f"  Productos Easy matcheados      : {len(asignado_easy)} / {len(easy)}")
    print(f"  Productos Sodimac matcheados   : {len(asignado_sodi)} / {len(sodi)}")

    # --- persistencia ---
    print("\n[6/6] Guardando resultados...")
    with open(OUT_CANDIDATOS, "w", encoding="utf-8") as f:
        json.dump(candidatos, f, ensure_ascii=False, indent=2)
    with open(OUT_TOP, "w", encoding="utf-8") as f:
        json.dump({
            "matches_1a1": matches_top,
            "ambiguos":    ambiguos,
            "meta": {
                "umbral_alta_conf": UMBRAL_ALTA_CONF,
                "umbral_candidato": UMBRAL_CANDIDATO,
                "total_candidatos": len(candidatos),
                "matches_1a1":      len(matches_top),
                "ambiguos":         len(ambiguos),
                "easy_matcheados":  len(asignado_easy),
                "sodi_matcheados":  len(asignado_sodi),
            },
        }, f, ensure_ascii=False, indent=2)

    print(f"  Candidatos: {OUT_CANDIDATOS}")
    print(f"  Top     : {OUT_TOP}")

    # resumen ejecutivo
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"  Matches de alta confianza (>= {UMBRAL_ALTA_CONF}) 1-a-1: {len(matches_top)}")
    print(f"  Cobertura Easy    : {len(asignado_easy)*100/len(easy):.1f}% ({len(asignado_easy)}/{len(easy)})")
    print(f"  Cobertura Sodimac : {len(asignado_sodi)*100/len(sodi):.1f}% ({len(asignado_sodi)}/{len(sodi)})")
    print(f"\n  Top 10 matches:")
    for m in matches_top[:10]:
        print(f"    [{m['proba']:.3f}] {m['easy_marca']} / {m['sodimac_marca']}")
        print(f"       E: {m['easy_titulo'][:75]}")
        print(f"       S: {m['sodimac_titulo'][:75]}")


if __name__ == "__main__":
    main()
