"""Verifica integridad de todos los archivos de datos."""
import json
from pathlib import Path

DATA = Path(r"C:\Users\Administrator\Documents\Buscop\motordelco-o\data")

archivos = [
    ("Easy crudo",      DATA / "easy"    / "catalogo_crudo.json"),
    ("Easy profundo",   DATA / "easy"    / "catalogo_profundo.json"),
    ("Sodimac crudo",   DATA / "sodimac" / "catalogo_crudo.json"),
    ("Sodimac profundo",DATA / "sodimac" / "catalogo_profundo.json"),
]

for nombre, ruta in archivos:
    with open(ruta, "rb") as f:
        raw = f.read()

    nulos = raw.count(b"\x00")
    pct   = nulos / len(raw) * 100

    if pct == 100:
        print(f"[CORRUPTO] {nombre} — {len(raw):,} bytes, 100% null")
        continue

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        print(f"[ERROR JSON] {nombre} — {e}")
        continue

    p0          = data[0]
    n_specs     = len(p0.get("especificaciones") or {})
    tiene_cats  = bool(p0.get("categorias"))
    tiene_desc  = bool(p0.get("descripcion") or p0.get("descripcion_completa"))

    print(f"[OK] {nombre}")
    print(f"     Productos : {len(data)}")
    print(f"     SKU       : {p0['sku']}")
    print(f"     Titulo    : {p0['titulo'][:55]}")
    print(f"     Specs     : {n_specs} campos  |  Categorias: {tiene_cats}  |  Descripcion: {tiene_desc}")
    print()
