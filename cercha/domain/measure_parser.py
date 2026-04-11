"""Parser estructurado de medidas de tornillos.

Resuelve el bug crítico de extraer_numeros() que destruía fracciones.
Ahora trata las medidas como unidades atómicas (calibre x largo) en vez de
conjuntos de dígitos sueltos.
"""

import re
from dataclasses import dataclass
from typing import Optional
from fractions import Fraction


@dataclass
class MedidaTornillo:
    calibre: str
    largo: str
    unidad: str = ""

    def __repr__(self):
        u = f" {self.unidad}" if self.unidad else ""
        return f"{self.calibre} x {self.largo}{u}"


def _normalizar_texto_medida(texto: str) -> str:
    """Prepara el texto para extracción de medidas."""
    t = texto.lower()
    t = t.replace("''", '"').replace("\u201d", '"').replace("\u201c", '"')
    # Separar dígitos pegados a letras: "6x1" → "6 x 1", "40mm" → "40 mm"
    t = re.sub(r'(\d)\s*x\s*(\d)', r'\1 x \2', t)
    return t


def _normalizar_fraccion(valor: str) -> float:
    """Convierte string con fracciones a float para comparación numérica.

    Soporta: "1/2" → 0.5, "1 5/8" → 1.625, "2" → 2.0, "3.5" → 3.5
    """
    valor = valor.strip().replace("-", " ")

    # Caso: número mixto "1 5/8" o "2 1/2"
    match_mixto = re.match(r'^(\d+)\s+(\d+)/(\d+)$', valor)
    if match_mixto:
        entero = int(match_mixto.group(1))
        num = int(match_mixto.group(2))
        den = int(match_mixto.group(3))
        if den == 0:
            return float(entero)
        return entero + num / den

    # Caso: fracción simple "5/8" o "1/4"
    match_frac = re.match(r'^(\d+)/(\d+)$', valor)
    if match_frac:
        num = int(match_frac.group(1))
        den = int(match_frac.group(2))
        if den == 0:
            return 0.0
        return num / den

    # Caso: decimal o entero
    try:
        return float(valor.replace(",", "."))
    except ValueError:
        return 0.0


def parsear_medida(texto: str) -> Optional[MedidaTornillo]:
    """Extrae la medida estructurada de un texto (título de producto o query).

    Maneja formatos chilenos:
      - "6 x 1 5/8"    → calibre=6, largo=1 5/8
      - "1/4 x 2 1/2"  → calibre=1/4, largo=2 1/2
      - "10 x 40 mm"   → calibre=10, largo=40, unidad=mm
      - "#14 x 100"    → calibre=14, largo=100
      - "8x2"          → calibre=8, largo=2
      - "3.5 x 25"     → calibre=3.5, largo=25
      - "#14(6) 100/60 X 100" → calibre=14, largo=100 (formato Turbo Screw)
    """
    t = _normalizar_texto_medida(texto)

    # Pre-filtro: eliminar patrones engañosos antes de parsear
    # "#14(6) 100/60 X 100" → el "100/60" es rosca/hilo, no medida. Limpiar.
    t = re.sub(r'(\d+)/(\d+)\s*x\s*(\d+)\s*(?:unds?|un\b)', r'\3 unds', t)

    # Patrón especial: Turbo Screw con gauge entre paréntesis o corchetes
    # Formatos: "#14(6) 100/60 X 100", "14[6]x100 mm", "#10(5) 50/50 X 1000"
    match_turbo = re.search(r'#?(\d+)\s*[\(\[]\d+[\)\]]', t)
    if match_turbo:
        calibre_turbo = match_turbo.group(1)
        # Buscar el largo después: puede ser "x NNN" o "NNN mm"
        resto = t[match_turbo.end():]
        # Ignorar fracciones tipo "100/60" y buscar el número real de largo
        resto = re.sub(r'\d+/\d+', '', resto)
        m_largo = re.search(r'(?:x\s*)?(\d+(?:\.\d+)?)\s*(mm)?', resto)
        if m_largo:
            return MedidaTornillo(
                calibre=calibre_turbo,
                largo=m_largo.group(1).strip(),
                unidad=_normalizar_unidad(m_largo.group(2)),
            )

    # Patrón principal: calibre x largo [unidad]
    # Calibre: número, fracción, decimal, o con #
    p_calibre = r'#?(\d+(?:\.\d+)?(?:/\d+)?)'
    # Largo: puede ser mixto ("1 5/8"), fracción ("1/2"), decimal, o entero
    p_largo = r'(\d+(?:\.\d+)?(?:[\s-]+\d+/\d+|/\d+)?)'
    # Unidad opcional
    p_unidad = r'(?:\s*(mm|pulgadas?|"))?'

    patron = p_calibre + r'\s*x\s*' + p_largo + p_unidad
    match = re.search(patron, t)

    if match:
        return MedidaTornillo(
            calibre=match.group(1).strip(),
            largo=match.group(2).strip(),
            unidad=_normalizar_unidad(match.group(3)),
        )

    # Patrón B: largo con unidad explícita, sin calibre (ej: "50mm", "2 pulgadas", '1 5/8"')
    # Rescata queries como "tornillo madera 50mm" donde no existe un "calibre x largo".
    # Sin este patrón, parsear_medida devuelve None y search_engine asume "sin medida",
    # disparando el falso positivo dim_coincide=True para cualquier candidato.
    p_largo_unidad = r'(\d+(?:\.\d+)?(?:[\s-]+\d+/\d+|/\d+)?)\s*(mm|pulgadas?|")(?=\s|$)'
    match_lu = re.search(p_largo_unidad, t)
    if match_lu:
        return MedidaTornillo(
            calibre="",
            largo=match_lu.group(1).strip(),
            unidad=_normalizar_unidad(match_lu.group(2)),
        )

    # Último recurso: fracción suelta sin calibre ni unidad (ej: "fibrocemento 1 1/4")
    # Retorna solo el largo para que al menos se compare dimensionalmente
    p_solo = r'(\d+\s+\d+/\d+|\d+/\d+)(?:\s*(?:"|pulgadas?))?'
    match_solo = re.search(p_solo, t)
    if match_solo:
        return MedidaTornillo(calibre="", largo=match_solo.group(1).strip())

    return None


def _normalizar_unidad(raw: Optional[str]) -> str:
    if not raw:
        return ""
    raw = raw.strip().lower()
    if raw in ('"', "pulgada", "pulgadas"):
        return "pulgadas"
    return raw


_PULGADA_A_MM = 25.4


def _valores_equivalentes(val_a: float, val_b: float) -> bool:
    """Compara dos valores numéricos considerando posible conversión pulgadas↔mm.

    Si los valores no coinciden directamente, intenta la conversión:
    - 2 pulgadas = 50.8mm
    - 1 5/8 pulgadas = 41.275mm
    """
    if abs(val_a - val_b) < 0.01:
        return True
    # Intentar: val_a en pulgadas, val_b en mm
    if val_a > 0 and abs(val_a * _PULGADA_A_MM - val_b) < 0.5:
        return True
    # Intentar: val_b en pulgadas, val_a en mm
    if val_b > 0 and abs(val_b * _PULGADA_A_MM - val_a) < 0.5:
        return True
    return False


def medidas_compatibles(query: MedidaTornillo, producto: MedidaTornillo) -> bool:
    """Compara dos medidas estructuralmente, tolerando formatos distintos.

    Maneja:
    - "6 x 1 5/8" compatible con "6x1-5/8"
    - "8 x 2" compatible con "8mm x 50.8" (conversión pulgadas↔mm)
    - "6 x 1 5/8" NO compatible con "6x1/2"
    """
    cal_q = _normalizar_fraccion(query.calibre) if query.calibre else 0.0
    cal_p = _normalizar_fraccion(producto.calibre) if producto.calibre else 0.0

    largo_q = _normalizar_fraccion(query.largo)
    largo_p = _normalizar_fraccion(producto.largo)

    largo_ok = _valores_equivalentes(largo_q, largo_p)

    # Si la query no tiene calibre (ej: "fibrocemento 1 1/4"), solo comparar largo
    if not query.calibre:
        return largo_ok

    calibre_ok = _valores_equivalentes(cal_q, cal_p)
    return calibre_ok and largo_ok


def extraer_numeros_fallback(texto: str) -> set:
    """Fallback para textos sin patrón AxB reconocible.

    Extrae todos los números respetando fracciones como unidades atómicas.
    "tornillo 1/4 zincado" → {"1/4"} en vez de {"1", "4"}
    """
    t = texto.lower()
    numeros = set()

    # Primero extraer fracciones mixtas: "1 5/8", "2 1/2"
    for m in re.finditer(r'(\d+)\s+(\d+/\d+)', t):
        numeros.add(m.group(0).strip())
        t = t.replace(m.group(0), " ")

    # Luego fracciones simples: "1/4", "5/8"
    for m in re.finditer(r'\d+/\d+', t):
        numeros.add(m.group(0))
        t = t.replace(m.group(0), " ")

    # Finalmente números simples (decimales o enteros)
    for m in re.finditer(r'\d+(?:[.,]\d+)?', t):
        numeros.add(m.group(0))

    return numeros
