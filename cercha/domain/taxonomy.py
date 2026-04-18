"""Taxonomía de productos para ferretería chilena.

Inspirada en ETIM (Electro-Technical Information Model) pero adaptada al
mercado local. Reemplaza el filtro es_tornillo() con clasificación por categoría.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Categoria:
    id: str
    nombre: str
    keywords: tuple
    atributos_clave: tuple
    excluir: tuple = ()  # si alguna de estas palabras está en el título → no es esta categoría
    umbral_con_dimension: float = 0.55
    umbral_sin_dimension: float = 0.70


CATEGORIAS: dict[str, Categoria] = {
    "tornillos": Categoria(
        id="tornillos",
        nombre="Tornillos y Tirafondos",
        keywords=("tornillo", "tirafondo", "soberbio", "autoperforante", "roscalata"),
        atributos_clave=("medida", "punta", "uso", "cabeza", "material"),
        umbral_con_dimension=0.55,
        umbral_sin_dimension=0.70,
    ),
    "pernos": Categoria(
        id="pernos",
        nombre="Pernos y Tuercas",
        keywords=("perno", "tuerca", "arandela", "esparrago", "espárrago", "carrocero", "perno hex"),
        atributos_clave=("medida", "material"),
        umbral_con_dimension=0.55,
        umbral_sin_dimension=0.70,
    ),
    "maderas": Categoria(
        id="maderas",
        nombre="Maderas y Tableros",
        keywords=("mdf", "osb", "terciado", "plywood", "melamina", "aglomerado",
                  "fibran", "fibrán", "tablero mdf", "plancha mdf", "panel mdf"),
        excluir=("puerta", "ventana", "mueble", "closet", "ropero", "cocina", "baño"),
        atributos_clave=("medida", "espesor", "material"),
        umbral_con_dimension=0.60,
        umbral_sin_dimension=0.75,
    ),
    "pinturas": Categoria(
        id="pinturas",
        nombre="Pinturas y Recubrimientos",
        keywords=("pintura", "barniz", "sellador", "impermeabilizante", "esmalte",
                  "látex", "latex", "anticorrosivo", "diluyente", "aguarras"),
        atributos_clave=("volumen", "uso", "acabado"),
        umbral_con_dimension=0.65,
        umbral_sin_dimension=0.72,
    ),
    "cementos": Categoria(
        id="cementos",
        nombre="Cementos y Morteros",
        keywords=("cemento", "mortero", "adhesivo ceramica", "estuco", "pasta muro",
                  "masilla", "fragua", "porcelana"),
        atributos_clave=("peso", "uso"),
        umbral_con_dimension=0.65,
        umbral_sin_dimension=0.72,
    ),
    "general": Categoria(
        id="general",
        nombre="Ferretería General",
        keywords=(),
        atributos_clave=("medida",),
        umbral_con_dimension=0.60,
        umbral_sin_dimension=0.75,
    ),
}

# Orden de evaluación — del más específico al más general
_ORDEN_EVALUACION = [
    "tornillos", "pernos", "maderas", "pinturas", "cementos", "general"
]


def detectar_categoria(titulo: str) -> Categoria:
    """Clasifica un producto en su categoría por palabras clave en el título."""
    titulo_lower = titulo.lower()
    for cat_id in _ORDEN_EVALUACION:
        if cat_id == "general":
            break
        cat = CATEGORIAS[cat_id]
        if any(kw in titulo_lower for kw in cat.keywords):
            if not any(ex in titulo_lower for ex in cat.excluir):
                return cat
    return CATEGORIAS["general"]
