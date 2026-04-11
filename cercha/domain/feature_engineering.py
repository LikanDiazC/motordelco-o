"""Ingeniería de características unificada para todas las tiendas.

Construye la Súper Oración con estructura IDÉNTICA para cualquier fuente,
eliminando el bug de asimetría entre Sodimac y Easy.
"""

import re
from cercha.domain.dictionaries import (
    USO_MAP, PUNTA_MAP, CABEZA_MAP, MATERIAL_MAP, BOUNDARY_MATCH_TERMS
)
from cercha.domain.measure_parser import parsear_medida


def deducir_caracteristica(texto: str, diccionario_map: dict, valor_defecto: str) -> str:
    """Busca variaciones en el texto y devuelve el término estándar."""
    texto_limpio = texto.lower()
    for variaciones, termino_estandar in diccionario_map.items():
        for var in variaciones:
            if var in BOUNDARY_MATCH_TERMS:
                if re.search(rf'\b{re.escape(var)}\b', texto_limpio):
                    return termino_estandar
            elif var in texto_limpio:
                return termino_estandar
    return valor_defecto


def extraer_medida(titulo: str, specs: dict) -> str:
    """Extrae y normaliza la medida. Prioriza título (preserva unidad original).

    El título "8X2" es más útil que specs "Diámetro: 8mm, Largo: 50.8" porque
    preserva la unidad que el usuario usa para buscar.
    """
    # Prioridad 1: título (tiene el formato que el usuario busca)
    medida_titulo = _medida_desde_titulo(titulo)
    if medida_titulo:
        return medida_titulo

    # Prioridad 2: specs (cuando el título no tiene patrón AxB)
    diametro = str(specs.get("Diametro", specs.get("Diámetro", ""))).strip()
    diametro = diametro.replace(" Milimetros", "mm").replace(" Milímetros", "mm")
    largo = str(specs.get("Largo", "")).strip()

    if diametro and largo:
        return f"{diametro} x {largo}"

    return "Medida no detectada"


def _medida_desde_titulo(titulo: str) -> str:
    """Extrae medida del título usando regex escalonado."""
    texto = titulo.lower().replace("''", '"').replace('"', ' " ')

    # Patrón especial: Turbo Screw "14[6]x100 mm" o "#14(6) 100/60 X 100"
    match_turbo = re.search(r'#?(\d+)\s*[\(\[]\d+[\)\]]\s*x?\s*', texto)
    if match_turbo:
        calibre = match_turbo.group(1)
        resto = texto[match_turbo.end():]
        resto = re.sub(r'\d+/\d+', '', resto)  # quitar fracciones rosca/hilo
        m_largo = re.search(r'(\d+(?:\.\d+)?)\s*(mm)?', resto)
        if m_largo:
            unidad = f" {m_largo.group(2)}" if m_largo.group(2) else ""
            return f"{calibre} x {m_largo.group(1)}{unidad}"

    # Patrón AxB (más común): "6 x 1 5/8", "10x40", "1/4 x 2 1/2"
    patron_axb = (
        r'(\d+(?:/\d+)?)\s*x\s*'
        r'(\d+(?:\s+\d+/\d+|\s*-\s*\d+/\d+|/\d+|\.\d+)?)'
        r'(?:\s*(mm|pulgadas?|"))?'
    )
    match_axb = re.search(patron_axb, texto)
    if match_axb:
        calibre = match_axb.group(1)
        largo = match_axb.group(2).replace("-", " ").strip()
        unidad = match_axb.group(3) or ""
        if unidad in ('"', "pulgada", "pulgadas"):
            return f'{calibre} x {largo}"'
        elif unidad == "mm":
            return f"{calibre} x {largo} mm"
        return f"{calibre} x {largo}"

    # Patrón pulgadas + mm: '1/2" 10mm'
    patron_pulg_mm = r'(\d+(?:-\d+/\d+|/\d+)?)\s*"\s*(\d+(?:\.\d+)?)\s*mm'
    match_pm = re.search(patron_pulg_mm, texto)
    if match_pm:
        return f'{match_pm.group(1)}" x {match_pm.group(2)}mm'

    # Solo pulgadas: "1/4", "1-1/2"
    patron_pulg = r'(\d+[\s-]\d+/\d+|\d+/\d+)(?:\s*(?:pulgadas?|"))'
    match_p = re.search(patron_pulg, texto)
    if match_p:
        return f'{match_p.group(1)}"'

    # Solo mm: "40mm", "3.5 mm"
    patron_mm = r'(\d+(?:\.\d+)?)\s*mm'
    match_m = re.search(patron_mm, texto)
    if match_m:
        return f"{match_m.group(1)} mm"

    return ""


def construir_super_oracion(titulo: str, specs: dict, descripcion_extra: str = "") -> dict:
    """Pipeline unificado de features para CUALQUIER tienda.

    Retorna un diccionario con todas las características extraídas
    y la súper oración simétrica.
    """
    # Construir contextos separados para evitar contaminación cruzada
    texto_uso = " ".join(filter(None, [
        titulo,
        specs.get("Uso", ""),
        specs.get("Uso Recomendado", ""),
        specs.get("Superficie de aplicación", ""),
        specs.get("Recomendaciones", ""),
        descripcion_extra,
    ]))
    texto_material = " ".join(filter(None, [
        titulo,
        specs.get("Material", ""),
        specs.get("Terminación", ""),
    ]))
    texto_cabeza = " ".join(filter(None, [
        titulo,
        specs.get("Tipo de cabeza", ""),
    ]))
    texto_punta = " ".join(filter(None, [
        titulo,
        specs.get("Modelo", ""),
        specs.get("Tipo de tornillo", ""),
    ]))

    uso = deducir_caracteristica(texto_uso, USO_MAP, "Construccion general")
    punta = deducir_caracteristica(texto_punta, PUNTA_MAP, "Punta Estandar")
    cabeza = deducir_caracteristica(texto_cabeza, CABEZA_MAP, "Cabeza Estandar")
    material = deducir_caracteristica(texto_material, MATERIAL_MAP, "Acero Estandar")
    medida = extraer_medida(titulo, specs)

    # SÚPER ORACIÓN SIMÉTRICA: misma estructura para todas las tiendas
    super_oracion = f"{titulo} {punta} {medida} {uso} {cabeza} {material}"

    return {
        "uso": uso,
        "punta": punta,
        "cabeza": cabeza,
        "material": material,
        "medida": medida,
        "texto_embedding": super_oracion,
    }


def es_tornillo(titulo: str) -> bool:
    """Filtro para descartar productos que no son tornillos."""
    keywords = ("tornillo", "tirafondo", "soberbio", "autoperforante", "roscalata")
    return any(k in titulo.lower() for k in keywords)
