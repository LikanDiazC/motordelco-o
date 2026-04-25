"""Entrena modelo v2: features v1 + v2 + validación cruzada ortogonal.

Datasets:
  - weak_labels.json  (etiquetado por reglas v1: cosine, brand, jaccard, dims)
  - golden_set.json   (etiquetado por reglas v2: char ngrams, nums, primera palabra)

Validación cruzada ortogonal (el test real de generalización):
  - Entrenar en weak, validar en golden  → ¿el modelo aprendido con reglas v1 generaliza a reglas v2?
  - Entrenar en golden, validar en weak  → ¿el modelo aprendido con reglas v2 generaliza a reglas v1?
  - Entrenar en ambos combinados, validar con CV  → el mejor estimado real de performance

Features finales (21): las 12 de v1 + las 9 de v2
  v1: cosine_sim, diff_largo_mm, diff_diametro_mm, tiene_dims,
      brand_match, material_match, cantidad_match, tipo_rosca_match,
      tipo_cabeza_match, jaccard_titulo, ratio_precio, mismo_cluster
  v2: v2_char_jaccard_3gram, v2_char_jaccard_4gram, v2_tokens_raros_jaccard,
      v2_nums_jaccard, v2_nums_overlap, v2_codigos_jaccard,
      v2_primera_palabra_match, v2_longitud_ratio, v2_lev_marca

Salida:
  data/modelo_matcher_v2.pkl
  data/modelo_matcher_v2_reporte.json
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

from cercha.domain.features_v2 import calcular_features_v2, FEATURE_V2_COLS

BASE = Path(r"C:\Users\Administrator\Documents\Buscop\motordelco-o\data")
IN_WEAK   = BASE / "weak_labels.json"
IN_GOLDEN = BASE / "golden_set.json"
OUT_MODEL    = BASE / "modelo_matcher_v2.pkl"
OUT_REPORTE  = BASE / "modelo_matcher_v2_reporte.json"

RANDOM_STATE = 42
IMPUTE_DIFF_LARGO = 25.0
IMPUTE_DIFF_DIAM  = 5.0

FEATURE_V1_COLS = [
    "cosine_sim",
    "diff_largo_mm",
    "diff_diametro_mm",
    "tiene_dims",
    "brand_match",
    "material_match",
    "cantidad_match",
    "tipo_rosca_match",
    "tipo_cabeza_match",
    "jaccard_titulo",
    "ratio_precio",
    "mismo_cluster",
]

ALL_COLS = FEATURE_V1_COLS + FEATURE_V2_COLS  # 12 + 9 = 21


def _completar_features_v2(rec: dict) -> dict:
    """Calcula v2 si no están ya presentes en el registro."""
    f = rec["features"]
    if "v2_char_jaccard_3gram" in f:
        return f  # ya vienen completas (golden_set ya las calcula)

    ctx = rec.get("ctx", {})
    tit_e = ctx.get("easy_titulo", "")
    tit_s = ctx.get("sodimac_titulo", "")
    me    = ctx.get("easy_marca", "")
    ms    = ctx.get("sodimac_marca", "")
    v2 = calcular_features_v2(tit_e, tit_s, me, ms)
    return {**f, **v2}


def _a_dataframe(records: list[dict], fuente_dataset: str) -> pd.DataFrame:
    rows = []
    for rec in records:
        f = _completar_features_v2(rec)
        dl = f.get("diff_largo_mm")
        dd = f.get("diff_diametro_mm")
        tiene_dims = 1 if (dl is not None and dd is not None) else 0
        if dl is None: dl = IMPUTE_DIFF_LARGO
        if dd is None: dd = IMPUTE_DIFF_DIAM

        row = {
            "easy_id":    rec["easy_id"],
            "sodimac_id": rec["sodimac_id"],
            "label":      rec["label"],
            "fuente_ds":  fuente_dataset,
            "tiene_dims": tiene_dims,
            "diff_largo_mm":    dl,
            "diff_diametro_mm": dd,
        }
        for col in FEATURE_V1_COLS:
            if col in ("diff_largo_mm", "diff_diametro_mm", "tiene_dims"):
                continue
            row[col] = f.get(col, 0)
        for col in FEATURE_V2_COLS:
            row[col] = f.get(col, 0)
        rows.append(row)
    return pd.DataFrame(rows)


def _eval(nombre, X_tr, y_tr, X_te, y_te):
    rf = RandomForestClassifier(
        n_estimators=300, min_samples_split=5, min_samples_leaf=2,
        class_weight="balanced", n_jobs=-1, random_state=RANDOM_STATE,
    )
    rf.fit(X_tr, y_tr)
    y_pred = rf.predict(X_te)
    y_proba = rf.predict_proba(X_te)[:, 1]

    rep = classification_report(y_te, y_pred, digits=4, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_te, y_pred)
    try:
        auc = roc_auc_score(y_te, y_proba)
    except ValueError:
        auc = float("nan")

    print(f"\n  ╔══ {nombre}")
    print(f"  ║ Precision/Recall/F1: {rep['1']['precision']:.4f} / {rep['1']['recall']:.4f} / {rep['1']['f1-score']:.4f}")
    print(f"  ║ ROC-AUC            : {auc:.4f}")
    print(f"  ║ CM (real x pred):   [{cm[0][0]:>5}  {cm[0][1]:>5}] [{cm[1][0]:>5}  {cm[1][1]:>5}]")

    return {
        "precision":   rep["1"]["precision"],
        "recall":      rep["1"]["recall"],
        "f1":          rep["1"]["f1-score"],
        "auc":         auc,
        "cm":          cm.tolist(),
        "support_pos": int(rep["1"]["support"]),
        "support_neg": int(rep["0"]["support"]),
    }


def main():
    print("=" * 70)
    print("ENTRENAMIENTO V2: FEATURES V1 + V2 + VALIDACIÓN ORTOGONAL")
    print("=" * 70)

    # --- cargar ambos datasets ---
    print("\n[1/5] Cargando datasets...")
    with open(IN_WEAK, encoding="utf-8") as f:
        weak_records = json.load(f)
    with open(IN_GOLDEN, encoding="utf-8") as f:
        golden_records = json.load(f)
    print(f"  Weak labels : {len(weak_records)}  (pos={sum(1 for r in weak_records if r['label']==1)})")
    print(f"  Golden set  : {len(golden_records)}  (pos={sum(1 for r in golden_records if r['label']==1)})")

    df_weak   = _a_dataframe(weak_records,   "weak")
    df_golden = _a_dataframe(golden_records, "golden")

    # alinear columnas
    cols = ALL_COLS
    X_weak, y_weak = df_weak[cols].values, df_weak["label"].values
    X_gold, y_gold = df_golden[cols].values, df_golden["label"].values

    # --- 1) weak con CV ---
    print("\n[2/5] Baseline: RF(v1+v2) en WEAK con CV 5-fold")
    rf_w = RandomForestClassifier(n_estimators=300, min_samples_split=5, min_samples_leaf=2,
                                  class_weight="balanced", n_jobs=-1, random_state=RANDOM_STATE)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cv_f1_weak = cross_val_score(rf_w, X_weak, y_weak, cv=skf, scoring="f1", n_jobs=-1)
    cv_auc_weak = cross_val_score(rf_w, X_weak, y_weak, cv=skf, scoring="roc_auc", n_jobs=-1)
    print(f"  CV F1   (5-fold weak) : {cv_f1_weak.mean():.4f} ± {cv_f1_weak.std():.4f}")
    print(f"  CV AUC  (5-fold weak) : {cv_auc_weak.mean():.4f} ± {cv_auc_weak.std():.4f}")

    # --- 2) golden con CV ---
    print("\n[3/5] Baseline: RF(v1+v2) en GOLDEN con CV 5-fold")
    rf_g = RandomForestClassifier(n_estimators=300, min_samples_split=5, min_samples_leaf=2,
                                  class_weight="balanced", n_jobs=-1, random_state=RANDOM_STATE)
    cv_f1_gold = cross_val_score(rf_g, X_gold, y_gold, cv=skf, scoring="f1", n_jobs=-1)
    cv_auc_gold = cross_val_score(rf_g, X_gold, y_gold, cv=skf, scoring="roc_auc", n_jobs=-1)
    print(f"  CV F1   (5-fold gold) : {cv_f1_gold.mean():.4f} ± {cv_f1_gold.std():.4f}")
    print(f"  CV AUC  (5-fold gold) : {cv_auc_gold.mean():.4f} ± {cv_auc_gold.std():.4f}")

    # --- 3) Validación ortogonal cruzada ---
    print("\n[4/5] TEST ORTOGONAL DE GENERALIZACIÓN")
    print("─" * 70)
    res_w2g = _eval("Train=WEAK  → Test=GOLDEN (generalización real)", X_weak, y_weak, X_gold, y_gold)
    res_g2w = _eval("Train=GOLDEN → Test=WEAK   (generalización real)", X_gold, y_gold, X_weak, y_weak)

    # --- 4) modelo final (ambos combinados) ---
    print("\n[5/5] Modelo final: entrenado en WEAK + GOLDEN combinados")
    X_all = np.vstack([X_weak, X_gold])
    y_all = np.concatenate([y_weak, y_gold])
    print(f"  Shape combinado: {X_all.shape}  (pos={int(y_all.sum())})")

    # split 80/20 para tener hold-out
    X_tr, X_te, y_tr, y_te = train_test_split(
        X_all, y_all, test_size=0.2, random_state=RANDOM_STATE, stratify=y_all
    )
    rf_final = RandomForestClassifier(
        n_estimators=400, min_samples_split=5, min_samples_leaf=2,
        class_weight="balanced", n_jobs=-1, random_state=RANDOM_STATE,
    )
    rf_final.fit(X_tr, y_tr)
    y_pred = rf_final.predict(X_te)
    y_proba = rf_final.predict_proba(X_te)[:, 1]

    rep_final = classification_report(y_te, y_pred, digits=4, output_dict=True)
    cm_final = confusion_matrix(y_te, y_pred)
    auc_final = roc_auc_score(y_te, y_proba)
    print(f"\n  ╔══ MODELO FINAL (weak + golden, 80/20 split)")
    print(f"  ║ Precision: {rep_final['1']['precision']:.4f}")
    print(f"  ║ Recall   : {rep_final['1']['recall']:.4f}")
    print(f"  ║ F1       : {rep_final['1']['f1-score']:.4f}")
    print(f"  ║ ROC-AUC  : {auc_final:.4f}")
    print(f"  ║ CM: {cm_final.tolist()}")

    # feature importance
    imp = dict(sorted(zip(cols, rf_final.feature_importances_), key=lambda kv: -kv[1]))
    print(f"\n  Top 10 features más importantes:")
    for i, (k, v) in enumerate(list(imp.items())[:10]):
        marker = "[v2]" if k.startswith("v2_") else "[v1]"
        bar = "█" * int(v * 40)
        print(f"    {marker} {k:<28} {v:>6.3f} {bar}")

    # --- persistir ---
    print("\n  Guardando modelo v2...")
    with open(OUT_MODEL, "wb") as f:
        pickle.dump({
            "modelo":         rf_final,
            "feature_cols":   cols,
            "impute":         {"diff_largo_mm": IMPUTE_DIFF_LARGO, "diff_diametro_mm": IMPUTE_DIFF_DIAM},
            "modelo_tipo":    "RandomForest_v2",
            "umbral_sugerido": 0.70,
        }, f)

    reporte = {
        "n_features":          len(cols),
        "features_v1":         FEATURE_V1_COLS,
        "features_v2":         FEATURE_V2_COLS,
        "datasets": {
            "weak":   {"total": len(weak_records),   "pos": int(y_weak.sum())},
            "golden": {"total": len(golden_records), "pos": int(y_gold.sum())},
        },
        "cv_intra_dataset": {
            "weak_f1_cv":   {"mean": float(cv_f1_weak.mean()), "std": float(cv_f1_weak.std())},
            "weak_auc_cv":  {"mean": float(cv_auc_weak.mean()), "std": float(cv_auc_weak.std())},
            "gold_f1_cv":   {"mean": float(cv_f1_gold.mean()), "std": float(cv_f1_gold.std())},
            "gold_auc_cv":  {"mean": float(cv_auc_gold.mean()), "std": float(cv_auc_gold.std())},
        },
        "generalizacion_ortogonal": {
            "train_weak_test_golden":  res_w2g,
            "train_golden_test_weak":  res_g2w,
        },
        "modelo_final": {
            "precision": rep_final["1"]["precision"],
            "recall":    rep_final["1"]["recall"],
            "f1":        rep_final["1"]["f1-score"],
            "auc":       auc_final,
            "confusion_matrix": cm_final.tolist(),
        },
        "feature_importance": imp,
    }
    with open(OUT_REPORTE, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)
    print(f"  Modelo : {OUT_MODEL}")
    print(f"  Reporte: {OUT_REPORTE}")

    # --- RESUMEN ---
    print("\n" + "=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    print(f"\n  Validación ortogonal (el test de generalización):")
    print(f"    Train=WEAK  → Test=GOLDEN : F1={res_w2g['f1']:.3f}  AUC={res_w2g['auc']:.3f}")
    print(f"    Train=GOLDEN → Test=WEAK  : F1={res_g2w['f1']:.3f}  AUC={res_g2w['auc']:.3f}")
    print(f"\n  Si F1 ortogonal >= 0.70 → el modelo GENERALIZA (no memoriza reglas)")
    print(f"  Si F1 ortogonal <= 0.50 → el modelo memoriza (no aprendió el concepto)")
    print(f"\n  Importancia features v2 (suma): {sum(v for k, v in imp.items() if k.startswith('v2_')):.3f}")
    print(f"  Importancia features v1 (suma): {sum(v for k, v in imp.items() if not k.startswith('v2_')):.3f}")


if __name__ == "__main__":
    main()
