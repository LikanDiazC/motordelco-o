"""Script de migración: convierte los datos existentes (data/ y data2/) al nuevo formato.

Ejecutar una sola vez para migrar los .pkl y .json existentes a la nueva estructura.
Uso: python -m cercha.migrate
"""

import json
import pickle
import shutil
from pathlib import Path
from cercha.config import PROJECT_ROOT, STORES


def migrar():
    """Migra datos del formato viejo (data/, data2/) al nuevo (data/sodimac/, data/easy/)."""
    old_data = PROJECT_ROOT / "data"
    old_data2 = PROJECT_ROOT / "data2"

    print("=== Migracion de datos Cercha ===\n")

    # Crear directorios nuevos
    for store_config in STORES.values():
        store_config["brain"].parent.mkdir(parents=True, exist_ok=True)

    # Migrar Sodimac
    sodimac_pkl_old = old_data / "cerebro_sodimac.pkl"
    sodimac_deep_old = old_data / "tornillos_catalogo_profundo.json"
    sodimac_raw_old = old_data / "tornillos_catalogo_completo.json"

    if sodimac_pkl_old.exists():
        dest = STORES["sodimac"]["brain"]
        shutil.copy2(sodimac_pkl_old, dest)
        print(f"  Sodimac cerebro: {sodimac_pkl_old} -> {dest}")

    if sodimac_deep_old.exists():
        dest = STORES["sodimac"]["catalog_deep"]
        shutil.copy2(sodimac_deep_old, dest)
        print(f"  Sodimac profundo: {sodimac_deep_old} -> {dest}")

    if sodimac_raw_old.exists():
        dest = STORES["sodimac"]["catalog_raw"]
        shutil.copy2(sodimac_raw_old, dest)
        print(f"  Sodimac crudo: {sodimac_raw_old} -> {dest}")

    # Migrar Easy
    easy_pkl_old = old_data2 / "cerebro_easy.pkl"
    easy_deep_old = old_data2 / "tornillos_easy_profundo.json"
    easy_raw_old = old_data2 / "tornillos_easy_crudo.json"
    easy_vec_old = old_data2 / "tornillos_easy_vectores.json"

    if easy_pkl_old.exists():
        dest = STORES["easy"]["brain"]
        shutil.copy2(easy_pkl_old, dest)
        print(f"  Easy cerebro: {easy_pkl_old} -> {dest}")

    if easy_deep_old.exists():
        dest = STORES["easy"]["catalog_deep"]
        shutil.copy2(easy_deep_old, dest)
        print(f"  Easy profundo: {easy_deep_old} -> {dest}")

    if easy_raw_old.exists():
        dest = STORES["easy"]["catalog_raw"]
        shutil.copy2(easy_raw_old, dest)
        print(f"  Easy crudo: {easy_raw_old} -> {dest}")

    if easy_vec_old.exists():
        dest = STORES["easy"]["catalog_vectors"]
        shutil.copy2(easy_vec_old, dest)
        print(f"  Easy vectores: {easy_vec_old} -> {dest}")

    print("\n=== Migracion completada ===")
    print("Ahora puedes re-vectorizar con: python -m cercha.pipeline vectorize all")
    print("(Esto creara super oraciones SIMETRICAS para ambas tiendas)")


if __name__ == "__main__":
    migrar()
