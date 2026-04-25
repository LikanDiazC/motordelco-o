"""Smoke test del normalizer con los campos nuevos (rating, ean, etc.)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cercha.domain.normalizer import normalizar_producto


def main():
    prod = {
        "sku": "TEST001",
        "marca": "Acme",
        "titulo": "Tornillo drywall 6x1 1/4 pulgadas",
        "precio_clp": 4390,
        "precio_normal_clp": 6651,
        "url": "https://example.com",
        "url_imagen": "https://cdn/img_001.jpg",
        "urls_imagen": [
            "https://cdn/img_001.jpg",
            "https://cdn/img_002.jpg",
            "https://cdn/img_003.jpg",
        ],
        "especificaciones": {"Diametro": "6 mm", "Largo": '1 1/4"'},
        "categorias": ["Ferreteria", "Fijaciones", "Tornillos"],
        "rating": 4.9,
        "review_count": 84,
        "disponibilidad": "InStock",
        "ean": "7808770102893",
        "descripcion": "Tornillo de alta calidad",
    }
    out = normalizar_producto(prod, "sodimac")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    # Asserts
    mb = out["metadata_basica"]
    assert mb["precio_clp"] == 4390
    assert mb["precio_normal_clp"] == 6651
    assert mb["descuento_pct"] == 34.0  # (6651-4390)/6651 = 34.0%
    assert mb["rating"] == 4.9
    assert mb["review_count"] == 84
    assert mb["disponibilidad"] == "InStock"
    assert mb["ean"] == "7808770102893"
    assert len(out["urls_imagen"]) == 3
    print("\nOK: todos los campos nuevos llegan al output normalizado.")


if __name__ == "__main__":
    main()
