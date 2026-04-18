"""Juez de match honesto. Lógica de decisión transparente sin ML sintético.

Umbral adaptativo por categoría:
- Si las dimensiones coinciden: umbral reducido (la medida es evidencia fuerte)
- Si no coinciden: umbral alto por categoría (default 0.70)
"""

from dataclasses import dataclass
from cercha.config import MATCH_SIMILARITY_THRESHOLD
from cercha.domain.taxonomy import CATEGORIAS, Categoria


@dataclass
class MatchResult:
    producto: dict
    similitud: float
    dimensiones_coinciden: bool
    es_match: bool
    cantidad: int
    precio_unitario: float


def evaluar_match(similitud: float, dimensiones_coinciden: bool,
                  categoria: Categoria | None = None,
                  umbral: float = MATCH_SIMILARITY_THRESHOLD) -> bool:
    """Regla de decisión con umbral adaptativo por categoría.

    Si la categoría tiene dimensiones (tornillos, pernos, maderas):
      - Con dimensión coincidente → umbral bajo de la categoría
      - Sin dimensión → False
    Si la categoría no tiene dimensiones (pinturas, cementos):
      - Usa umbral_sin_dimension de la categoría directamente
    """
    if categoria is None:
        categoria = CATEGORIAS["general"]

    if dimensiones_coinciden:
        return similitud >= categoria.umbral_con_dimension

    # Solo pinturas y cementos permiten match puramente semántico (no tienen dimensión crítica)
    if categoria.id in ("pinturas", "cementos"):
        return similitud >= categoria.umbral_sin_dimension

    return False
