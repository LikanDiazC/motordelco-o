"""Diccionarios de estandarización unificados. Única fuente de verdad para todas las tiendas."""

USO_MAP = {
    ("yeso-carton", "yeso carton", "volcanita", "vulcanita", "drywall",
     "yesocarton", "volc"): "Yeso-carton (Volcanita / Drywall)",
    ("metalcon", "perfil", "tabiqueria", "hojalateria",
     "metal"): "Metal (Metalcon / Perfiles)",
    ("aglomerado", "mdf", "melamina", "pino", "madera", "cholguan",
     "terciado"): "Madera (Aglomerado / MDF / Melamina)",
    ("techo", "techumbre", "calamina", "v2", "v8", "tejado",
     "cubierta"): "Techumbre (Techo / Zinc / Calamina)",
    ("concreto", "hormigon", "ladrillo", "albañileria",
     "cemento"): "Concreto (Hormigon / Ladrillo)",
    ("fibrocemento", "internit", "pizarreño"): "Fibrocemento (Internit / Pizarreño)",
}

PUNTA_MAP = {
    ("autoperforante", "auto perforante", "punta broca",
     "autotaladrante"): "Autoperforante (Punta Broca)",
    ("punta espada", "punta fina", "punta clavo",
     "aguja"): "Punta Fina (Punta Espada / Clavo)",
    ("tirafondo", "tira fondo", "perno madera"): "Tirafondo (Madera Estructural)",
}

CABEZA_MAP = {
    ("phillips", "cruz", "cruz phillips", "ph2"): "Phillips (Cruz)",
    ("plana", "avellanada", "de hundir"): "Plana (Avellanada)",
    ("lenteja", "fijadora", "extra plana", "truss"): "Lenteja (Fijadora)",
    ("hexagonal", "copa"): "Hexagonal (Copa)",
    ("trompeta", "bugle", "crs"): "Trompeta (Drywall)",
    ("redonda", "pan head", "pan"): "Redonda (Pan head)",
}

MATERIAL_MAP = {
    ("inox", "inoxidable", "acero inox"): "Acero Inoxidable (Inox)",
    ("zincado", "galvanizado", "zinc", "brillante", "zc",
     "zbr", "zb"): "Acero Zincado (Galvanizado)",
    ("empavonado", "fosfatado", "negro",
     "pavonado"): "Acero Fosfatado (Negro / Empavonado)",
    ("bronceado", "bicromatado", "amarillo",
     "iridiscente"): "Acero Bicromatado (Bronceado / Amarillo)",
    ("acero", "carbono"): "Acero Estandar",
}

# Abreviaciones que requieren match por word-boundary (evita falsos positivos)
BOUNDARY_MATCH_TERMS = {"zc", "zb", "zbr", "crs", "ph2"}
