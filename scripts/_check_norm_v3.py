"""Valida las mejoras del normalizador v3."""
import json, re
from pathlib import Path
from collections import Counter

BASE = Path(r"C:\Users\Administrator\Documents\Buscop\motordelco-o\data")

for tienda in ("easy", "sodimac"):
    with open(BASE/tienda/"catalogo_normalizado.json", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n{'='*70}\n{tienda.upper()}  ({len(data)} productos)\n{'='*70}")

    # 1. marca_norm
    marcas_raw = Counter(p["metadata_basica"]["marca"] for p in data)
    marcas_norm = Counter(p["metadata_basica"]["marca_norm"] for p in data)
    print(f"\n[1] MARCA")
    print(f"    unique marca_raw  : {len(marcas_raw)}")
    print(f"    unique marca_norm : {len(marcas_norm)}")
    print(f"    top 5 marca_norm  : {marcas_norm.most_common(5)}")

    # 2. titulo_limpio (Easy: verificar que se quitó el sufijo de marca)
    cambios_titulo = sum(
        1 for p in data
        if p["metadata_basica"]["titulo"] != p["metadata_basica"]["titulo_limpio"]
    )
    print(f"\n[2] TÍTULO LIMPIO")
    print(f"    Títulos modificados: {cambios_titulo}/{len(data)} ({cambios_titulo*100//len(data)}%)")
    # ejemplos
    ejemplos = [
        p for p in data
        if p["metadata_basica"]["titulo"] != p["metadata_basica"]["titulo_limpio"]
    ][:3]
    for p in ejemplos:
        print(f"      ANTES: {p['metadata_basica']['titulo']}")
        print(f"      DESPUES: {p['metadata_basica']['titulo_limpio']}")

    # 3. material_norm
    mat_raw = Counter(p["metadata_tecnica"]["material"] for p in data if p["metadata_tecnica"]["material"])
    mat_norm = Counter(p["metadata_tecnica"]["material_norm"] for p in data if p["metadata_tecnica"]["material_norm"])
    print(f"\n[3] MATERIAL")
    print(f"    unique material raw  : {len(mat_raw)}")
    print(f"    unique material_norm : {len(mat_norm)}")
    print(f"    top 5 material_norm  : {mat_norm.most_common(5)}")

    # 4. tipo_rosca
    rosca = Counter(p["metadata_tecnica"]["tipo_rosca"] for p in data if p["metadata_tecnica"]["tipo_rosca"])
    con_rosca = sum(1 for p in data if p["metadata_tecnica"]["tipo_rosca"])
    print(f"\n[4] TIPO_ROSCA")
    print(f"    productos con tipo_rosca: {con_rosca}/{len(data)} ({con_rosca*100//len(data)}%)")
    print(f"    distribución top 6      : {rosca.most_common(6)}")

    # 5. texto_a_vectorizar (verificar que incluye dimensiones)
    con_dims_en_texto = sum(
        1 for p in data
        if "Diámetro" in p["contenido_vectorial"]["texto_a_vectorizar"]
           or "Largo" in p["contenido_vectorial"]["texto_a_vectorizar"]
    )
    print(f"\n[5] TEXTO_A_VECTORIZAR")
    print(f"    incluye dimensiones: {con_dims_en_texto}/{len(data)} ({con_dims_en_texto*100//len(data)}%)")
    # ejemplo
    print(f"    ejemplo producto[0]:")
    print(f"      {data[0]['contenido_vectorial']['texto_a_vectorizar'][:280]}")

# Cross-check: marca_norm ahora matchea entre tiendas
print(f"\n{'='*70}\nCROSS-STORE: marcas comunes (marca_norm)\n{'='*70}")
with open(BASE/"easy"/"catalogo_normalizado.json", encoding="utf-8") as f:
    easy = {p["metadata_basica"]["marca_norm"] for p in json.load(f) if p["metadata_basica"]["marca_norm"]}
with open(BASE/"sodimac"/"catalogo_normalizado.json", encoding="utf-8") as f:
    sod = {p["metadata_basica"]["marca_norm"] for p in json.load(f) if p["metadata_basica"]["marca_norm"]}

comunes = easy & sod
print(f"  easy unique   : {len(easy)}")
print(f"  sodimac unique: {len(sod)}")
print(f"  comunes       : {len(comunes)}")
print(f"  ejemplos      : {sorted(list(comunes))[:15]}")
