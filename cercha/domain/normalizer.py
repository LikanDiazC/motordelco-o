"""Normalizador unificado Easy/Sodimac → esquema estándar para embeddings.

Resuelve la asimetría de specs entre tiendas:
- Easy llama "Largo" / "Longitud" / lo pone en el título. Sodimac usa "Largo" o "Medida".
- Easy: "Diámetro"; Sodimac: "Diámetro" (a veces inconsistente con el título).
- Formatos mezclan pulgadas, mm y fracciones. Todo se convierte a milímetros.
- Marcas en Sodimac vienen ALL-CAPS, en Easy en Title-Case → se expone `marca_norm`.
- Easy suele pegar la marca al final del título ("...200un Mamut") → se limpia.
- `material` tiene vocabulario distinto entre tiendas ("Fierro"/"Metal" vs "Acero")
  → se expone `material_norm` con sinónimos unificados.
- `tipo_rosca` rara vez viene en las specs → se extrae del título por regex.

Produce el JSON canónico que alimenta el vectorizer:
{
  "id_producto": "sodimac-110295767",
  "tienda": "sodimac",
  "sku": "...",
  "url_producto": "...",
  "url_imagen": "...",
  "metadata_basica": {marca, marca_norm, titulo, titulo_limpio, precio_clp, categorias},
  "metadata_tecnica": {material, material_norm, tipo_cabeza, tipo_rosca, ..., dimensiones: {largo_mm, diametro_mm, medida_cruda}},
  "contenido_vectorial": {descripcion_limpia, texto_a_vectorizar}
}
"""

from __future__ import annotations

import re

from cercha.domain.measure_parser import parsear_medida, _normalizar_fraccion
from cercha.domain.taxonomy import detectar_categoria


PULGADA_A_MM = 25.4

# Cada campo estándar → lista ordenada de alias heterogéneos (Easy y Sodimac mezclados).
_ALIASES = {
    "material": ("Material",),
    "tipo_cabeza": ("Tipo de cabeza", "Cabeza", "Tipo cabeza"),
    "tipo_rosca": ("Tipo de rosca", "Rosca"),
    "tipo_punta": ("Tipo de tornillo", "Modelo", "Tipo"),
    "color": ("Color", "Terminación", "Terminal", "Tono", "Acabado"),
    "uso": ("Uso", "Uso Recomendado", "Superficie de aplicación", "Aplicación"),
    "origen": ("Origen", "País de Origen", "País Origen"),
    "garantia": ("Garantía Mínima Legal", "Detalle de la garantía", "Garantía"),
}

# Claves donde vive el "largo" del tornillo (Easy usa varias, Sodimac otras).
_LARGO_KEYS = ("Largo", "Longitud", "Medida", "Medidas", "Largo total")
_DIAM_KEYS = ("Diámetro", "Diametro", "Calibre", "Grosor")
_CANTIDAD_KEYS = ("Cantidad por paquete", "Contenido", "Cantidad", "Unidades por paquete")


# ---------------------------------------------------------------------------
# Sinónimos de material → vocabulario canónico controlado.
# Se aplican después de lower-casing y tienen prioridad por orden de inserción.
# ---------------------------------------------------------------------------
_MATERIAL_SYNONYMS = {
    # acero (categoría predominante)
    "acero": "acero",
    "acero inoxidable": "acero inoxidable",
    "acero al carbono": "acero",
    "acero carbono": "acero",
    "acero zincado": "acero",
    "acero zincado dicromatado": "acero",
    "acero galvanizado": "acero",
    "acero inox": "acero inoxidable",
    "inox": "acero inoxidable",
    "inoxidable": "acero inoxidable",
    "fierro": "acero",
    "hierro": "acero",
    "metal": "acero",          # asumimos acero (el más común en ferretería)
    "metalico": "acero",
    "metálico": "acero",
    # no-ferrosos (mantener la distinción)
    "latón": "latón",
    "laton": "latón",
    "bronce": "bronce",
    "aluminio": "aluminio",
    "cobre": "cobre",
    "zinc": "zinc",
    # plásticos / otros
    "plástico": "plástico",
    "plastico": "plástico",
    "nylon": "plástico",
    "pvc": "plástico",
    "goma": "goma",
    "madera": "madera",
}


# ---------------------------------------------------------------------------
# Patrones para extraer `tipo_rosca` desde el título / descripción.
# Orden: más específico primero.
# ---------------------------------------------------------------------------
_ROSCA_PATTERNS = [
    (re.compile(r"\bautoperfor(?:ante|adora|able)\b", re.I), "autoperforante"),
    (re.compile(r"\bautorroscante\b", re.I),                  "autorroscante"),
    (re.compile(r"\brosca\s+gruesa\b", re.I),                 "gruesa"),
    (re.compile(r"\brosca\s+fina\b", re.I),                   "fina"),
    (re.compile(r"\brosca\s+ordinaria\b", re.I),              "ordinaria"),
    (re.compile(r"\brosca\s+m[eé]trica\b", re.I),             "métrica"),
    (re.compile(r"\brosca\s+completa\b", re.I),               "completa"),
    (re.compile(r"\brosca\s+parcial\b", re.I),                "parcial"),
    (re.compile(r"\brosca\s+madera\b", re.I),                 "madera"),
    (re.compile(r"\brosca\s+chapa\b", re.I),                  "chapa"),
    (re.compile(r"\btirafond[oa]\b", re.I),                   "tirafondo"),
    (re.compile(r"\bdrywall\b", re.I),                        "gruesa"),   # drywall usa rosca gruesa
    (re.compile(r"\bvolcanita\b", re.I),                      "gruesa"),
]


def _get_first(specs: dict, keys: tuple) -> str:
    """Primer valor no vacío en el diccionario para cualquier alias."""
    if not specs:
        return ""
    for k in keys:
        v = specs.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _extraer_numero(texto: str) -> float | None:
    """Extrae el primer número (incluyendo fracciones) de un texto."""
    if not texto:
        return None
    t = texto.strip().lower().replace(",", ".")
    # Fracción mixta "1 1/4", "1-1/4"
    m = re.search(r'(\d+)[\s-]+(\d+)/(\d+)', t)
    if m:
        entero, num, den = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return entero + num / den if den else float(entero)
    # Fracción simple "5/8"
    m = re.search(r'(\d+)/(\d+)', t)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        return num / den if den else None
    # Decimal o entero
    m = re.search(r'\d+(?:\.\d+)?', t)
    return float(m.group(0)) if m else None


def _valor_a_mm(raw: str) -> float | None:
    """Convierte un valor textual con unidad a milímetros."""
    if not raw:
        return None
    texto = raw.lower().strip()
    es_pulgadas = bool(re.search(r'(pulgadas?|")', texto))
    es_cm = bool(re.search(r'\bcm\b|centim', texto))
    num = _extraer_numero(texto)
    if num is None:
        return None
    if es_pulgadas:
        return round(num * PULGADA_A_MM, 2)
    if es_cm:
        return round(num * 10.0, 2)
    return round(num, 2)


def _dimensiones_desde_titulo(titulo: str) -> tuple[float | None, float | None, str]:
    """Extrae (diametro_mm, largo_mm, medida_cruda) desde el título."""
    med = parsear_medida(titulo)
    if not med:
        return None, None, ""

    cruda_partes = []
    if med.calibre:
        cruda_partes.append(med.calibre)
    if med.largo:
        cruda_partes.append(f"x {med.largo}")
    if med.unidad:
        sufijo = '"' if med.unidad == "pulgadas" else f" {med.unidad}"
        cruda_partes.append(sufijo if med.unidad != "pulgadas" else '"')
    medida_cruda = " ".join(cruda_partes).replace(' "', '"').strip()

    diam_mm = None
    if med.calibre:
        cal = _normalizar_fraccion(med.calibre)
        diam_mm = round(cal, 2) if cal > 0 else None

    largo_mm = None
    if med.largo:
        lar = _normalizar_fraccion(med.largo)
        if lar > 0:
            if med.unidad == "pulgadas":
                largo_mm = round(lar * PULGADA_A_MM, 2)
            elif med.unidad == "mm":
                largo_mm = round(lar, 2)
            elif lar < 10:
                largo_mm = round(lar * PULGADA_A_MM, 2)
            else:
                largo_mm = round(lar, 2)

    return diam_mm, largo_mm, medida_cruda


def _parse_cantidad(specs: dict, titulo: str) -> int:
    raw = _get_first(specs, _CANTIDAD_KEYS)
    if raw:
        m = re.search(r'(\d+)', raw.replace(".", "").replace(",", ""))
        if m:
            return int(m.group(1))
    m = re.search(r'(\d+)\s*(?:unidades?|unds?|un\b|tornillos?)', titulo, re.I)
    if m:
        return int(m.group(1))
    return 1


def _limpiar_descripcion(desc_raw: str) -> str:
    if not desc_raw:
        return ""
    s = re.sub(r'<[^>]+>', ' ', desc_raw)
    s = (s.replace('&quot;', '"').replace('&amp;', '&')
           .replace('&nbsp;', ' ').replace('&#x27;', "'"))
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _categorias(prod: dict, titulo: str, tienda: str = "") -> list[str]:
    """Obtiene la ruta de categorías en orden raíz→hoja."""
    cats = prod.get("categorias") or []
    cats = [c for c in cats if c]
    if not cats:
        cat = detectar_categoria(titulo)
        if cat.id != "general":
            return [cat.nombre]
        return []

    if tienda == "sodimac" and len(cats) >= 2:
        ultima = cats[-1].lower()
        primera = cats[0].lower()
        es_raiz_al_final = any(
            kw in ultima for kw in ("ferretería", "fijacion", "fijación")
        )
        es_raiz_al_inicio = any(
            kw in primera for kw in ("ferretería", "fijacion", "fijación")
        )
        if es_raiz_al_final and not es_raiz_al_inicio:
            cats = cats[::-1]

    return cats


# ---------------------------------------------------------------------------
# Normalizaciones añadidas (v3)
# ---------------------------------------------------------------------------
def _normalizar_marca(marca: str) -> str:
    """Devuelve la marca en lowercase, sin caracteres sueltos ni dobles espacios.

    `MAMUT` y `Mamut` → `mamut`. Sirve como clave exacta para matching cruzado.
    """
    if not marca:
        return ""
    s = marca.strip().lower()
    # eliminar caracteres no alfanuméricos al inicio/final (p.ej. comillas extra)
    s = re.sub(r"^[^\w]+|[^\w]+$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _limpiar_titulo(titulo: str, marca: str) -> str:
    """Remueve la marca del final del título (problema típico de Easy).

    Ej: 'Tornillo volc rosca gruesa 6x2 200un Mamut' + marca='Mamut'
        → 'Tornillo volc rosca gruesa 6x2 200un'
    También elimina la marca como palabra aislada al final (sin punctuación previa).
    """
    if not titulo:
        return ""
    t = titulo.strip()
    if marca:
        # escape + word boundary + fin de string con posible puntuación
        patron = re.compile(
            r"[\s,.\-·]+" + re.escape(marca) + r"\s*[.!?]*\s*$",
            re.IGNORECASE,
        )
        t = patron.sub("", t).strip()
    return t


def _normalizar_material(raw: str) -> str:
    """Mapea el material crudo al vocabulario canónico controlado."""
    if not raw:
        return ""
    t = raw.strip().lower()
    # match exacto primero
    if t in _MATERIAL_SYNONYMS:
        return _MATERIAL_SYNONYMS[t]
    # match parcial: el sinónimo más específico que aparezca como substring.
    # Ordenamos por longitud descendente para preferir "acero inoxidable" sobre "acero".
    for key in sorted(_MATERIAL_SYNONYMS.keys(), key=len, reverse=True):
        if key in t:
            return _MATERIAL_SYNONYMS[key]
    return t  # dejar crudo si no hay match (se conserva la variante original)


def _extraer_tipo_rosca(titulo: str, desc: str, spec_raw: str) -> str:
    """Devuelve el tipo de rosca detectado.

    Prioridad: spec explícita > título > descripción.
    """
    # spec cruda (si el vendedor la puso)
    if spec_raw:
        for patron, etiqueta in _ROSCA_PATTERNS:
            if patron.search(spec_raw):
                return etiqueta
        # si la spec es un valor libre razonable, devolverlo en minúsculas
        s = spec_raw.strip().lower()
        if 3 <= len(s) <= 40 and not any(c in s for c in "{}[]<>"):
            return s

    for texto in (titulo, desc):
        if not texto:
            continue
        for patron, etiqueta in _ROSCA_PATTERNS:
            if patron.search(texto):
                return etiqueta
    return ""


def _texto_a_vectorizar(titulo: str, marca: str, categorias: list[str],
                        atribs: dict, desc_limpia: str,
                        dims: dict, cantidad: int) -> str:
    """Arma el texto de embedding (idéntico schema Easy/Sodimac).

    v3: añade dimensiones en mm y cantidad_empaque para que el embedding distinga
    tornillos de distintas medidas aunque el título sea parecido.
    """
    partes = [titulo]
    if marca and marca.lower() not in titulo.lower():
        partes.append(marca)
    if categorias:
        partes.append("Categoría: " + " > ".join(categorias))

    atrib_parts = []
    for clave in ("material", "tipo_cabeza", "tipo_rosca", "tipo_punta", "uso"):
        v = atribs.get(clave)
        if v:
            atrib_parts.append(f"{clave.replace('_', ' ').capitalize()}: {v}")
    if atrib_parts:
        partes.append(". ".join(atrib_parts))

    # Dimensiones y empaque: señal discriminante fuerte para matching
    dim_parts = []
    if dims.get("diametro_mm"):
        dim_parts.append(f"Diámetro {dims['diametro_mm']} mm")
    if dims.get("largo_mm"):
        dim_parts.append(f"Largo {dims['largo_mm']} mm")
    if dim_parts:
        partes.append(". ".join(dim_parts))
    if cantidad and cantidad > 1:
        partes.append(f"Cantidad por paquete: {cantidad}")

    if desc_limpia:
        partes.append(desc_limpia[:300])

    return ". ".join(partes)


def normalizar_producto(prod: dict, tienda: str) -> dict:
    """Canoniza un producto crudo (Easy o Sodimac) al esquema unificado."""
    sku = str(prod.get("sku", "")).strip()
    titulo_raw = str(prod.get("titulo", "")).strip()
    specs = prod.get("especificaciones") or {}
    marca_raw = str(prod.get("marca", "")).strip()
    marca_norm = _normalizar_marca(marca_raw)

    # Título limpio: quita sufijo de marca (crítico en Easy).
    titulo = _limpiar_titulo(titulo_raw, marca_raw)

    # Dimensiones: título manda, specs rellenan.
    diam_t, largo_t, medida_cruda = _dimensiones_desde_titulo(titulo_raw)
    largo_mm = largo_t if largo_t is not None else _valor_a_mm(_get_first(specs, _LARGO_KEYS))
    diam_mm_spec = _valor_a_mm(_get_first(specs, _DIAM_KEYS))
    if diam_mm_spec is not None and (diam_mm_spec < 0.5 or diam_mm_spec > 35):
        diam_mm_spec = None
    diam_mm = diam_t if diam_t is not None else diam_mm_spec

    if not medida_cruda:
        l_raw = _get_first(specs, _LARGO_KEYS)
        d_raw = _get_first(specs, _DIAM_KEYS)
        if d_raw and l_raw:
            medida_cruda = f"{d_raw} x {l_raw}"
        elif l_raw:
            medida_cruda = l_raw

    # Atributos base desde specs
    atribs = {clave: _get_first(specs, alias) for clave, alias in _ALIASES.items()}

    # Descripcion limpia (la usamos para tipo_rosca y texto)
    desc_raw = prod.get("descripcion_completa") or prod.get("descripcion") or ""
    desc_limpia = _limpiar_descripcion(desc_raw)

    # Enriquecer tipo_rosca con regex sobre título/desc si la spec es débil o vacía
    tipo_rosca_detectado = _extraer_tipo_rosca(titulo_raw, desc_limpia, atribs["tipo_rosca"])
    if tipo_rosca_detectado:
        atribs["tipo_rosca"] = tipo_rosca_detectado

    # Normalizar material con mapa de sinónimos
    material_norm = _normalizar_material(atribs["material"])
    # Si no había material en specs, inferir desde descripción cuando el título/desc mencione uno
    if not material_norm:
        for texto in (titulo_raw, desc_limpia):
            inferido = _normalizar_material(texto)
            if inferido and inferido in _MATERIAL_SYNONYMS.values():
                material_norm = inferido
                break

    cantidad = _parse_cantidad(specs, titulo_raw)
    categorias = _categorias(prod, titulo_raw, tienda=tienda)

    dims = {
        "largo_mm": largo_mm,
        "diametro_mm": diam_mm,
        "medida_cruda": medida_cruda,
    }

    texto_vect = _texto_a_vectorizar(
        titulo, marca_raw, categorias, atribs, desc_limpia, dims, cantidad
    )

    # Campos comerciales
    precio_actual = int(prod.get("precio_clp", 0) or 0)
    precio_normal_raw = prod.get("precio_normal_clp")
    precio_normal = int(precio_normal_raw) if precio_normal_raw else precio_actual
    descuento_pct = None
    if precio_normal and precio_normal > precio_actual and precio_actual > 0:
        descuento_pct = round((precio_normal - precio_actual) / precio_normal * 100, 1)

    metadata_basica: dict = {
        "marca": marca_raw,
        "marca_norm": marca_norm,
        "titulo": titulo_raw,
        "titulo_limpio": titulo,
        "precio_clp": precio_actual,
        "precio_normal_clp": precio_normal,
        "categorias": categorias,
    }
    if descuento_pct is not None:
        metadata_basica["descuento_pct"] = descuento_pct
    for campo in ("rating", "review_count", "disponibilidad", "ean"):
        if prod.get(campo) is not None:
            metadata_basica[campo] = prod[campo]

    return {
        "id_producto": f"{tienda}-{sku}",
        "tienda": tienda,
        "sku": sku,
        "url_producto": prod.get("url", ""),
        "url_imagen": prod.get("url_imagen", ""),
        "urls_imagen": prod.get("urls_imagen") or ([prod["url_imagen"]] if prod.get("url_imagen") else []),
        "metadata_basica": metadata_basica,
        "metadata_tecnica": {
            "material": atribs["material"],
            "material_norm": material_norm,
            "tipo_cabeza": atribs["tipo_cabeza"],
            "tipo_rosca": atribs["tipo_rosca"],
            "tipo_punta": atribs["tipo_punta"],
            "color": atribs["color"],
            "uso": atribs["uso"],
            "origen": atribs["origen"],
            "cantidad_empaque": cantidad,
            "dimensiones": dims,
        },
        "contenido_vectorial": {
            "descripcion_limpia": desc_limpia,
            "texto_a_vectorizar": texto_vect,
        },
    }


def normalizar_catalogo(productos: list[dict], tienda: str) -> list[dict]:
    """Normaliza un catálogo completo. Descarta items sin título."""
    return [normalizar_producto(p, tienda) for p in productos if p.get("titulo")]
