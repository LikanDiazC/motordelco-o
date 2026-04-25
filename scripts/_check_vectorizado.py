"""Verifica contenido real de los archivos vectorizados."""
import json, pickle
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\Documents\Buscop\motordelco-o\data")

for tienda in ("easy", "sodimac"):
    print(f"\n{'='*60}\n{tienda.upper()}\n{'='*60}")

    # 1. Normalizado
    with open(BASE/tienda/"catalogo_normalizado.json", encoding="utf-8") as f:
        norm = json.load(f)
    print(f"Normalizado: {len(norm)} productos")
    p0 = norm[0]
    cv = p0.get("contenido_vectorial", {})
    print(f"  keys cv           : {list(cv.keys())}")
    print(f"  texto_a_vectorizar: {cv.get('texto_a_vectorizar', '')[:140]}...")
    print(f"  descripcion_limpia: {(cv.get('descripcion_limpia') or '')[:80]}...")

    # cobertura real
    with_tav = sum(1 for p in norm if p.get("contenido_vectorial", {}).get("texto_a_vectorizar"))
    with_desc = sum(1 for p in norm if p.get("contenido_vectorial", {}).get("descripcion_limpia"))
    print(f"  Cobertura texto_a_vectorizar: {with_tav}/{len(norm)} ({with_tav*100//len(norm)}%)")
    print(f"  Cobertura descripcion_limpia: {with_desc}/{len(norm)} ({with_desc*100//len(norm)}%)")

    # 2. catalogo_vectores
    with open(BASE/tienda/"catalogo_vectores.json", encoding="utf-8") as f:
        vec = json.load(f)
    print(f"\nVectores JSON: {len(vec)} entradas")
    print(f"  keys: {list(vec[0].keys())}")
    print(f"  texto_embedding[0][:120]: {vec[0]['texto_embedding'][:120]}")

    # 3. cerebro.pkl
    with open(BASE/tienda/"cerebro.pkl", "rb") as f:
        brain = pickle.load(f)
    print(f"\nCerebro.pkl:")
    print(f"  vectores.shape : {brain['vectores'].shape}")
    print(f"  metadata[0]    : {brain['metadata'][0]}")
