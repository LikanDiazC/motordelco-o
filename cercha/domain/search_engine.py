"""Motor de búsqueda híbrido (semántico + léxico + dimensional).

Corrige los bugs del sistema anterior:
- Fracciones se comparan como unidades atómicas (no dígitos sueltos)
- Bono léxico controlado
- Sin dependencia de XGBoost
"""

import re
import numpy as np

from cercha.config import LEXICAL_BONUS_PER_WORD, TOP_K_CANDIDATES
from cercha.domain.measure_parser import (
    parsear_medida, medidas_compatibles, extraer_numeros_fallback
)
from cercha.judge import evaluar_match, MatchResult


def limpiar_texto(texto: str) -> str:
    """Normaliza texto para búsqueda: minúsculas, sinónimos, separación dígitos/letras."""
    t = texto.lower()
    reemplazos = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'yeso-carton': 'drywall', 'yesocarton': 'drywall',
        'volcanita': 'drywall', 'vulcanita': 'drywall',
    }
    for ori, des in reemplazos.items():
        t = t.replace(ori, des)
    # Separar dígitos de letras pero NO romper fracciones (la "/" se preserva)
    t = re.sub(r'(\d)([a-z])', r'\1 \2', t)
    t = re.sub(r'([a-z])(\d)', r'\1 \2', t)
    return t.strip()


def extraer_cantidad(titulo: str, specs: dict = None) -> int:
    """Extrae la cantidad de unidades del paquete.

    Fuentes (en orden de prioridad):
    1. Specs "Contenido" (Easy) o "Cantidad por paquete" (Sodimac)
    2. Título del producto (regex)
    """
    # Fuente 1: Specs (más confiable que el título)
    if specs:
        # Easy: "Contenido": "600 unidades" o "1 Caja de tornillos (100 unidades)"
        contenido = str(specs.get('Contenido', ''))
        if contenido:
            # Primero buscar patrón "(NNN unidades)" dentro de texto complejo
            m_paren = re.search(r'\((\d+)\s*unidades?\)', contenido.lower())
            if m_paren:
                return max(1, int(m_paren.group(1)))
            # Luego patrón simple "NNN unidades/Unidades/Tornillos"
            m_cont = re.search(r'(\d+)\s*(?:unidades?|tornillos?)', contenido.lower())
            if m_cont:
                return max(1, int(m_cont.group(1)))

        # Sodimac: "Cantidad por paquete": "100"
        cant_paq = specs.get('Cantidad por paquete', '')
        if cant_paq:
            try:
                return max(1, int(str(cant_paq).strip()))
            except ValueError:
                pass

    # Fuente 2: Título del producto
    texto = titulo.lower().replace('.', '').replace(',', '')

    # Patrón 1: "100 unidades", "50 unds", "1000 un"
    match = re.search(
        r'(\d+)\s*(?:unidades|unidad\(es\)|unidad|unds|und|un\b|pcs|pz|piezas|uds)',
        texto
    )
    if match:
        return max(1, int(match.group(1)))

    # Patrón 2: "caja 100", "pack 50", "bolsa de 20", "balde 500"
    match_caja = re.search(
        r'(?:caja|pack|bolsa|balde|set|kit)\s*(?:de\s*)?(\d+)',
        texto
    )
    if match_caja:
        return max(1, int(match_caja.group(1)))

    # Patrón 3: Easy "bal600u", "bal250u", "bal1000u" (balde de N unidades)
    match_bal = re.search(r'bal\s*(\d+)\s*u', texto)
    if match_bal:
        return max(1, int(match_bal.group(1)))

    # Patrón 4: Easy "b500", "b1000", "b100" (bolsa de N) - solo si N >= 50
    match_b = re.search(r'\bb(\d+)\b', texto)
    if match_b:
        n = int(match_b.group(1))
        if n >= 50:  # Evitar confundir calibres pequeños con cantidades
            return n

    # Patrón 5: Sodimac format "100 unidad(es)" al final
    match_ud = re.search(r'(\d+)\s*unidad\(es\)\s*$', texto)
    if match_ud:
        return max(1, int(match_ud.group(1)))

    # Patrón 6: "N un." al final (Easy: "10 un.", "3 un.")
    match_un_dot = re.search(r'(\d+)\s*un\.\s*$', texto)
    if match_un_dot:
        return max(1, int(match_un_dot.group(1)))

    return 1


def buscar_en_tienda(query_limpia: str, vector_query, metadata: list,
                     vectores, umbral_match: float = 0.70) -> MatchResult:
    """Ejecuta búsqueda híbrida en una tienda.

    Pipeline:
    1. Similitud coseno con todos los vectores → rankeo base
    2. Bono léxico por coincidencia exacta de palabras
    3. Top K candidatos
    4. Filtro dimensional (medidas coinciden?)
    5. Juez de match
    """
    # Paso 1: Similitud coseno (numpy puro, sin dependencia de sentence_transformers)
    q = np.array(vector_query).flatten()
    v = np.array(vectores)
    # Cosine similarity = dot(a, b) / (||a|| * ||b||)
    norm_q = np.linalg.norm(q)
    norms_v = np.linalg.norm(v, axis=1)
    # Proteger contra división por cero
    norms_v = np.maximum(norms_v, 1e-10)
    similitudes = (v @ q / (norms_v * max(norm_q, 1e-10))).tolist()

    # Paso 2: Bono léxico
    palabras_query = set(query_limpia.split())
    for idx in range(len(metadata)):
        palabras_prod = set(limpiar_texto(metadata[idx]['titulo']).split())
        interseccion = palabras_query.intersection(palabras_prod)
        bono = len(interseccion) * LEXICAL_BONUS_PER_WORD
        similitudes[idx] = min(1.0, similitudes[idx] + bono)

    # Paso 3: Top K
    indices_top = np.argsort(similitudes)[::-1][:TOP_K_CANDIDATES]

    # Paso 4: Filtro dimensional con parser estructurado
    medida_query = parsear_medida(query_limpia)
    candidato = None
    similitud_candidato = 0.0
    dim_coincide = False

    for idx in indices_top:
        prod = metadata[idx]
        sim_actual = similitudes[idx]

        # Intentar comparación estructurada de medidas
        texto_prod = f"{prod['titulo']} {prod.get('medida_limpia', '')}"
        medida_prod = parsear_medida(texto_prod)

        if medida_query and medida_prod:
            # Mejor caso: ambos parsean → comparación estructurada
            if medidas_compatibles(medida_query, medida_prod):
                candidato = prod
                similitud_candidato = sim_actual
                dim_coincide = True
                break
        elif medida_query and not medida_prod:
            # Query tiene medida pero producto no parsea → skip (no asumir match)
            continue
        elif not medida_query:
            # Query sin medidas (ej: "tornillo madera") → confiar en la semántica
            candidato = prod
            similitud_candidato = sim_actual
            dim_coincide = True
            break

    # Si ninguno pasó el filtro, tomar el mejor por similitud
    if not candidato:
        mejor_idx = indices_top[0]
        candidato = metadata[mejor_idx]
        similitud_candidato = similitudes[mejor_idx]
        dim_coincide = False

    # Paso 5: Juez
    es_match = evaluar_match(similitud_candidato, dim_coincide, umbral_match)
    specs = candidato.get('specs', None)
    cantidad = extraer_cantidad(candidato['titulo'], specs)
    precio = candidato.get('precio', 0)
    precio_unitario = precio / cantidad if cantidad > 0 else precio

    return MatchResult(
        producto=candidato,
        similitud=similitud_candidato,
        dimensiones_coinciden=dim_coincide,
        es_match=es_match,
        cantidad=cantidad,
        precio_unitario=precio_unitario,
    )
