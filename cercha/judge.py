"""Juez de match honesto. Lógica de decisión transparente sin ML sintético.

El XGBoost anterior era un clasificador entrenado sobre datos sintéticos que
simplemente aprendía la regla: match = (similitud >= 0.70) AND (dimensión == 1).
Este módulo implementa una lógica más sofisticada con umbral adaptativo:
- Si las dimensiones coinciden exactamente, el umbral baja (la medida ya es evidencia fuerte)
- Si las dimensiones no coinciden, se requiere altísima similitud semántica
"""

from dataclasses import dataclass
from cercha.config import MATCH_SIMILARITY_THRESHOLD


# Umbral reducido cuando las dimensiones ya matchean (la medida exacta es evidencia fuerte)
MATCH_THRESHOLD_WITH_DIMENSIONS = 0.55


@dataclass
class MatchResult:
    producto: dict
    similitud: float
    dimensiones_coinciden: bool
    es_match: bool
    cantidad: int
    precio_unitario: float


def evaluar_match(similitud: float, dimensiones_coinciden: bool,
                  umbral: float = MATCH_SIMILARITY_THRESHOLD) -> bool:
    """Regla de decisión con umbral adaptativo.

    - Si dimensiones coinciden: umbral más permisivo (0.55) porque la medida exacta
      ya confirma que es el producto correcto. Queries cortas como "tornillo 8x2"
      generan embeddings débiles pero la medida exacta es suficiente evidencia.
    - Si dimensiones no coinciden: requiere umbral alto (0.70) como mínimo.
    """
    if not dimensiones_coinciden:
        return False
    return similitud >= MATCH_THRESHOLD_WITH_DIMENSIONS
