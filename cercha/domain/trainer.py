"""Entrena un Random Forest clasificador sobre los weak labels.

Entrada:
    data/weak_labels.json   (generado por weak_labels.py)

Salida:
    data/modelo_matcher.pkl          → modelo entrenado (joblib)
    data/modelo_matcher_reporte.json → métricas, feature importance, hiperparámetros
    data/modelo_matcher_errores.json → pares mal clasificados para inspección

Features usadas:
    cosine_sim, diff_largo_mm, diff_diametro_mm,
    brand_match, material_match, cantidad_match,
    tipo_rosca_match, tipo_cabeza_match,
    jaccard_titulo, ratio_precio, mismo_cluster

Los `None` de diff_largo_mm / diff_diametro_mm se imputan con el valor MAX_DIFF
(25 mm largo, 5 mm diámetro) para no confundir al modelo con un "dato ausente
pero pequeño". Adicionalmente, se agrega una columna booleana "tiene_dims".

Modelos comparados:
    - RandomForestClassifier (baseline robusto)
    - GradientBoostingClassifier (alternativa)

Estrategia de evaluación:
    - train/test split estratificado 80/20
    - 5-fold cross-validation para métrica estable
    - classification_report + matriz de confusión + AUC
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import (
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    precision_recall_curve,
    f1_score,
)

BASE = Path(r"C:\Users\Administrator\Documents\Buscop\motordelco-o\data")
IN_LABELS = BASE / "weak_labels.json"
OUT_MODEL = BASE / "modelo_matcher.pkl"
OUT_REPORTE = BASE / "modelo_matcher_reporte.json"
OUT_ERRORES = BASE / "modelo_matcher_errores.json"

RANDOM_STATE = 42

# Imputación para valores None
IMPUTE_DIFF_LARGO = 25.0   # ≈ cluster "muy distinto"
IMPUTE_DIFF_DIAM  = 5.0

FEATURE_COLS = [
    "cosine_sim",
    "diff_largo_mm",
    "diff_diametro_mm",
    "tiene_dims",          # 1 si ambos diffs no son None, 0 si se imputó
    "brand_match",
    "material_match",
    "cantidad_match",
    "tipo_rosca_match",
    "tipo_cabeza_match",
    "jaccard_titulo",
    "ratio_precio",
    "mismo_cluster",
]


# ─── Construcción del dataset ─────────────────────────────────────────────
def _a_dataframe(records: list[dict]) -> pd.DataFrame:
    rows = []
    for rec in records:
        f = rec["features"]
        dl = f.get("diff_largo_mm")
        dd = f.get("diff_diametro_mm")
        tiene_dims = 1 if (dl is not None and dd is not None) else 0
        dl = IMPUTE_DIFF_LARGO if dl is None else dl
        dd = IMPUTE_DIFF_DIAM  if dd is None else dd

        rows.append({
            "easy_id":          rec["easy_id"],
            "sodimac_id":       rec["sodimac_id"],
            "label":            rec["label"],
            "fuente":           rec["ctx"].get("fuente"),
            "cosine_sim":       f["cosine_sim"],
            "diff_largo_mm":    dl,
            "diff_diametro_mm": dd,
            "tiene_dims":       tiene_dims,
            "brand_match":      f["brand_match"],
            "material_match":   f["material_match"],
            "cantidad_match":   f["cantidad_match"],
            "tipo_rosca_match": f["tipo_rosca_match"],
            "tipo_cabeza_match": f["tipo_cabeza_match"],
            "jaccard_titulo":   f["jaccard_titulo"],
            "ratio_precio":     f["ratio_precio"],
            "mismo_cluster":    f["mismo_cluster"],
            "easy_titulo":      rec["ctx"].get("easy_titulo"),
            "sodimac_titulo":   rec["ctx"].get("sodimac_titulo"),
            "easy_marca":       rec["ctx"].get("easy_marca"),
            "sodimac_marca":    rec["ctx"].get("sodimac_marca"),
        })
    return pd.DataFrame(rows)


# ─── Entrenamiento y evaluación ───────────────────────────────────────────
def _entrenar_y_evaluar(nombre: str, modelo, X_tr, X_te, y_tr, y_te, X_all, y_all):
    print(f"\n{'─'*70}\n  {nombre}\n{'─'*70}")

    # cross-validation en TODO el dataset (estratificado, 5-fold)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cv_f1 = cross_val_score(modelo, X_all, y_all, cv=skf, scoring="f1", n_jobs=-1)
    cv_auc = cross_val_score(modelo, X_all, y_all, cv=skf, scoring="roc_auc", n_jobs=-1)
    print(f"  CV F1   (5-fold): {cv_f1.mean():.4f} ± {cv_f1.std():.4f}")
    print(f"  CV ROC-AUC      : {cv_auc.mean():.4f} ± {cv_auc.std():.4f}")

    modelo.fit(X_tr, y_tr)
    y_pred = modelo.predict(X_te)
    y_proba = modelo.predict_proba(X_te)[:, 1]

    cm = confusion_matrix(y_te, y_pred)
    rep = classification_report(y_te, y_pred, digits=4, output_dict=True)
    auc = roc_auc_score(y_te, y_proba)

    print(f"\n  Matriz de confusión (test):")
    print(f"                pred=0   pred=1")
    print(f"    real=0    {cm[0][0]:>6}   {cm[0][1]:>6}")
    print(f"    real=1    {cm[1][0]:>6}   {cm[1][1]:>6}")
    print(f"\n  Precision (match=1): {rep['1']['precision']:.4f}")
    print(f"  Recall    (match=1): {rep['1']['recall']:.4f}")
    print(f"  F1        (match=1): {rep['1']['f1-score']:.4f}")
    print(f"  ROC-AUC            : {auc:.4f}")

    # umbral óptimo por F1
    prec, rec, thr = precision_recall_curve(y_te, y_proba)
    # omitir el último punto que no tiene threshold
    f1_vals = 2 * prec[:-1] * rec[:-1] / (prec[:-1] + rec[:-1] + 1e-9)
    best_idx = f1_vals.argmax()
    best_thr = float(thr[best_idx])
    best_f1  = float(f1_vals[best_idx])
    print(f"\n  Umbral óptimo (por F1): {best_thr:.3f}   F1={best_f1:.4f}")

    return {
        "nombre": nombre,
        "cv_f1_mean": float(cv_f1.mean()),
        "cv_f1_std":  float(cv_f1.std()),
        "cv_auc_mean": float(cv_auc.mean()),
        "cv_auc_std":  float(cv_auc.std()),
        "test_precision": rep["1"]["precision"],
        "test_recall":    rep["1"]["recall"],
        "test_f1":        rep["1"]["f1-score"],
        "test_auc":       auc,
        "confusion_matrix": cm.tolist(),
        "umbral_optimo": best_thr,
        "f1_umbral_optimo": best_f1,
        "classification_report": rep,
    }


def main():
    print("=" * 70)
    print("ENTRENAMIENTO DEL CLASIFICADOR DE MATCHING EASY×SODIMAC")
    print("=" * 70)

    # --- cargar labels ---
    print("\n[1/5] Cargando weak labels...")
    with open(IN_LABELS, encoding="utf-8") as f:
        records = json.load(f)
    print(f"  Registros: {len(records)}")

    df = _a_dataframe(records)
    print(f"  Positivos: {(df.label==1).sum()}")
    print(f"  Negativos: {(df.label==0).sum()}")
    print(f"     duros  : {((df.label==0) & (df.fuente=='neg_duro_cluster')).sum()}")
    print(f"     fáciles: {((df.label==0) & (df.fuente=='neg_facil_inter')).sum()}")

    # --- preparar features ---
    X = df[FEATURE_COLS].values
    y = df["label"].values
    print(f"\n  Shape features: {X.shape}, labels: {y.shape}")

    # --- split ---
    print("\n[2/5] Split 80/20 estratificado...")
    X_tr, X_te, y_tr, y_te, idx_tr, idx_te = train_test_split(
        X, y, df.index.values,
        test_size=0.2, random_state=RANDOM_STATE, stratify=y,
    )
    print(f"  Train: {len(X_tr)} (pos={y_tr.sum()})")
    print(f"  Test : {len(X_te)} (pos={y_te.sum()})")

    # --- modelos ---
    print("\n[3/5] Evaluando modelos...")

    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight="balanced",
        n_jobs=-1,
        random_state=RANDOM_STATE,
    )
    gb = GradientBoostingClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=4,
        random_state=RANDOM_STATE,
    )

    res_rf = _entrenar_y_evaluar("RandomForest",       rf, X_tr, X_te, y_tr, y_te, X, y)
    res_gb = _entrenar_y_evaluar("GradientBoosting",   gb, X_tr, X_te, y_tr, y_te, X, y)

    # --- elegir mejor modelo (por F1) ---
    if res_rf["test_f1"] >= res_gb["test_f1"]:
        modelo = rf
        winner = "RandomForest"
    else:
        modelo = gb
        winner = "GradientBoosting"
    print(f"\n[4/5] Modelo elegido: {winner}")

    # feature importance
    imp = dict(sorted(
        zip(FEATURE_COLS, modelo.feature_importances_),
        key=lambda kv: -kv[1],
    ))
    print(f"\n  Feature importance:")
    for k, v in imp.items():
        bar = "█" * int(v * 60)
        print(f"    {k:<20} {v:>6.3f} {bar}")

    # predecir en TODO el dataset para identificar errores
    y_all_pred = modelo.predict(X)
    y_all_proba = modelo.predict_proba(X)[:, 1]
    df["pred"] = y_all_pred
    df["proba"] = np.round(y_all_proba, 4)
    df["error"] = (df["label"] != df["pred"]).astype(int)

    # top 20 errores (FP y FN ordenados por |proba - 0.5| más certero = peor)
    errores = df[df["error"] == 1].copy()
    errores["certeza_err"] = (errores["proba"] - errores["label"]).abs()
    errores = errores.sort_values("certeza_err", ascending=False).head(40)
    print(f"\n  Errores totales en dataset completo: {df['error'].sum()}/{len(df)} ({df['error'].mean()*100:.2f}%)")

    # --- guardar ---
    print("\n[5/5] Persistiendo modelo y reporte...")
    with open(OUT_MODEL, "wb") as f:
        pickle.dump({
            "modelo": modelo,
            "feature_cols": FEATURE_COLS,
            "umbral_optimo": (res_rf if winner == "RandomForest" else res_gb)["umbral_optimo"],
            "impute": {"diff_largo_mm": IMPUTE_DIFF_LARGO, "diff_diametro_mm": IMPUTE_DIFF_DIAM},
            "modelo_tipo": winner,
        }, f)

    reporte = {
        "total_pares":     len(df),
        "positivos":       int((df.label==1).sum()),
        "negativos":       int((df.label==0).sum()),
        "modelo_elegido":  winner,
        "feature_cols":    FEATURE_COLS,
        "feature_importance": imp,
        "resultados": {
            "RandomForest":     res_rf,
            "GradientBoosting": res_gb,
        },
        "imputacion": {
            "diff_largo_mm":    IMPUTE_DIFF_LARGO,
            "diff_diametro_mm": IMPUTE_DIFF_DIAM,
        },
    }
    with open(OUT_REPORTE, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    # guardar errores de inspección
    err_records = errores[
        ["easy_id", "sodimac_id", "label", "pred", "proba", "fuente",
         "cosine_sim", "jaccard_titulo", "brand_match", "diff_largo_mm", "diff_diametro_mm",
         "easy_marca", "sodimac_marca", "easy_titulo", "sodimac_titulo"]
    ].to_dict(orient="records")
    with open(OUT_ERRORES, "w", encoding="utf-8") as f:
        json.dump(err_records, f, ensure_ascii=False, indent=2)

    print(f"  Modelo  : {OUT_MODEL}")
    print(f"  Reporte : {OUT_REPORTE}")
    print(f"  Errores : {OUT_ERRORES}")

    print("\n" + "=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    g = res_rf if winner == "RandomForest" else res_gb
    print(f"  Modelo elegido      : {winner}")
    print(f"  F1 (test hold-out)  : {g['test_f1']:.4f}")
    print(f"  F1 (CV 5-fold)      : {g['cv_f1_mean']:.4f} ± {g['cv_f1_std']:.4f}")
    print(f"  ROC-AUC (CV)        : {g['cv_auc_mean']:.4f} ± {g['cv_auc_std']:.4f}")
    print(f"  Umbral óptimo       : {g['umbral_optimo']:.3f}")
    print(f"  Top 3 features      : {list(imp.keys())[:3]}")


if __name__ == "__main__":
    main()
