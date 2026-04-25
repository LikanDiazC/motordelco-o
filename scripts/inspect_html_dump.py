"""Herramienta de diagnóstico: extrae el __NEXT_DATA__ de un HTML guardado
y muestra los caminos JSON donde viven categorías, imagen y specs.

Útil cuando Sodimac/Easy cambian la forma de su respuesta y los scrapers
dejan de encontrar campos. Pasa uno de los archivos que descargaste
(easy1/2.txt, sodimac1/2.txt) y verifica qué rutas existen.

Uso:
    python scripts/inspect_html_dump.py <ruta_html> [--dump salida.json]
    python scripts/inspect_html_dump.py C:/Users/.../sodimac2.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def extraer_next_data(html: str) -> dict:
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.DOTALL
    )
    if not m:
        raise SystemExit("No se encontro __NEXT_DATA__ en el HTML.")
    return json.loads(m.group(1))


def extraer_jsonld_breadcrumbs(html: str) -> list[list[str]]:
    """Devuelve todas las BreadcrumbList halladas en scripts application/ld+json."""
    resultados: list[list[str]] = []
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE
    ):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except Exception:
            continue
        nodos = data if isinstance(data, list) else [data]
        for nodo in nodos:
            if not isinstance(nodo, dict):
                continue
            bloques = [nodo] + (nodo.get("@graph", []) if isinstance(nodo.get("@graph"), list) else [])
            for bloque in bloques:
                if isinstance(bloque, dict) and bloque.get("@type") == "BreadcrumbList":
                    nombres = []
                    for el in bloque.get("itemListElement", []) or []:
                        if isinstance(el, dict):
                            nombre = el.get("name") or (
                                el["item"]["name"] if isinstance(el.get("item"), dict) and el["item"].get("name") else None
                            )
                            if isinstance(nombre, str):
                                nombres.append(nombre.strip())
                    if nombres:
                        resultados.append(nombres)
    return resultados


def rastrear_claves(obj, claves_buscadas: set[str], prefijo: str = "") -> list[tuple[str, object]]:
    """Busca recursivamente claves por nombre y devuelve pares (path, valor)."""
    hallazgos: list[tuple[str, object]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            ruta = f"{prefijo}.{k}" if prefijo else k
            if k in claves_buscadas:
                hallazgos.append((ruta, v))
            hallazgos.extend(rastrear_claves(v, claves_buscadas, ruta))
    elif isinstance(obj, list) and obj:
        for i, v in enumerate(obj[:3]):  # limitar para no explotar en listas gigantes
            hallazgos.extend(rastrear_claves(v, claves_buscadas, f"{prefijo}[{i}]"))
    return hallazgos


def resumir(valor, max_len: int = 180) -> str:
    try:
        s = json.dumps(valor, ensure_ascii=False)
    except Exception:
        s = str(valor)
    return s if len(s) <= max_len else s[:max_len] + "..."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archivo", help="HTML guardado de Sodimac o Easy")
    ap.add_argument("--dump", help="Ruta para guardar el __NEXT_DATA__ extraído")
    ap.add_argument("--tienda", choices=["sodimac", "easy", "auto"], default="auto",
                    help="Para resaltar rutas específicas de cada tienda")
    args = ap.parse_args()

    ruta = Path(args.archivo)
    html = ruta.read_text(encoding="utf-8", errors="replace")

    print(f"\n=== JSON-LD BreadcrumbList ({ruta.name}) ===")
    bread_ld = extraer_jsonld_breadcrumbs(html)
    if bread_ld:
        for b in bread_ld:
            print("  ", " > ".join(b))
    else:
        print("  (ninguna encontrada)")

    print(f"\n=== __NEXT_DATA__ ({ruta.name}) ===")
    try:
        data = extraer_next_data(html)
    except SystemExit as e:
        print(f"  {e}")
        return

    if args.dump:
        Path(args.dump).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Volcado completo -> {args.dump}")

    claves = {
        "breadcrumb", "breadcrumbs", "categoryTree", "categories",
        "productCategories", "category",
        "mediaUrls", "media", "images", "image", "imageUrl", "primaryImage",
        "specifications", "attributes",
        "brand", "skuId", "productId", "displayName", "productName",
    }
    hallazgos = rastrear_claves(data, claves)

    print(f"\nClaves interesantes halladas (primeras {len(hallazgos)}):")
    for path, valor in hallazgos[:40]:
        print(f"  {path} = {resumir(valor)}")

    if len(hallazgos) > 40:
        print(f"  ... ({len(hallazgos) - 40} adicionales)")


if __name__ == "__main__":
    main()
