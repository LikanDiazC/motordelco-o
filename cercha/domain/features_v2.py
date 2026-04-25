"""Features v2: señales ortogonales al weak labeling (para reducir data leakage).

Features v1 (usadas por weak_labels.py): cosine_sim, brand_match, jaccard_titulo,
diff_largo_mm, diff_diametro_mm, material_match, etc.

Features v2 (NUEVAS, no usadas en las reglas de etiquetado):
  - char_jaccard_3gram: Jaccard de trigramas de caracteres (captura typos/variantes)
  - char_jaccard_4gram: Jaccard de 4-gramas de caracteres
  - nums_overlap:       Intersección de números extraídos del título (3/8, 5mm, 25)
  - codigos_match:      ¿los códigos técnicos (M8, #6, N°8) coinciden?
  - longitud_ratio:     ratio entre longitudes de títulos (penaliza comparar muy cortos/largos)
  - token_raros:        tokens raros compartidos (>4 letras, no frecuentes)
  - primera_palabra_match: ¿empieza con la misma palabra significativa?
  - levenshtein_marca:  distancia de edición normalizada entre marcas

Estos features complementan (no reemplazan) las v1. El objetivo es que el modelo
tenga poder discriminativo real más allá de memorizar las reglas de generación.
"""
from __future__ import annotations

import re
from functools import lru_cache

_TOKEN_RE = re.compile(r"[a-záéíóúñA-ZÁÉÍÓÚÑ0-9]+", re.IGNORECASE)
_NUM_RE   = re.compile(r"\d+(?:[.,/]\d+)?(?:/\d+)?")  # captura 3, 3.5, 3/8, 1/2
_CODIGO_RE = re.compile(r"(?:#|n[°º]|M|m)\s*\d+", re.IGNORECASE)  # #6, N°8, M10, M 8
_STOPWORDS = {
    "de", "la", "el", "los", "las", "un", "una", "y", "o", "en", "para", "con",
    "por", "al", "del", "sin", "x", "mm", "cm", "kg", "g", "ml", "l", "und",
    "unidades", "unidad", "pza", "pzas", "pcs", "pieza", "piezas", "uds", "u",
    "set", "pack", "paquete",
}


def _char_ngrams(s: str, n: int) -> set:
    """Set de n-gramas de caracteres (normalizado, sin espacios múltiples)."""
    if not s:
        return set()
    s = re.sub(r"\s+", " ", s.lower().strip())
    if len(s) < n:
        return {s}
    return {s[i:i+n] for i in range(len(s) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _tokens(texto: str) -> list[str]:
    if not texto:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(texto) if len(t) > 1]


def _tokens_raros(texto: str, min_len: int = 4) -> set:
    """Tokens significativos: >=min_len letras, no stopwords, no numéricos puros."""
    out = set()
    for t in _tokens(texto):
        if len(t) < min_len:
            continue
        if t in _STOPWORDS:
            continue
        if t.isdigit():
            continue
        out.add(t)
    return out


def _extraer_numeros(texto: str) -> set:
    """Extrae números normalizados a fracción o decimal (ej. '3/8', '5.5', '25')."""
    if not texto:
        return set()
    nums = set()
    for m in _NUM_RE.finditer(texto):
        v = m.group(0).replace(",", ".")
        nums.add(v)
    return nums


def _extraer_codigos(texto: str) -> set:
    """Códigos técnicos tipo M8, #6, N°8. Normalizados a 'M8', 'N6'."""
    if not texto:
        return set()
    out = set()
    for m in _CODIGO_RE.finditer(texto):
        raw = m.group(0).replace(" ", "").upper()
        raw = raw.replace("°", "").replace("º", "")
        raw = raw.replace("#", "N").replace("N°", "N").replace("N", "N")  # normaliza
        if not raw:
            continue
        out.add(raw)
    return out


def _primera_palabra_sig(texto: str) -> str:
    """Primera palabra significativa (no stopword, >2 letras)."""
    for t in _tokens(texto):
        if len(t) >= 3 and t not in _STOPWORDS and not t.isdigit():
            return t
    return ""


def _levenshtein(a: str, b: str) -> int:
    """Distancia de edición simple. O(|a|*|b|). Suficiente para marcas cortas."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # DP clásico
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(curr[j-1] + 1, prev[j] + 1, prev[j-1] + cost)
        prev = curr
    return prev[-1]


def _lev_ratio(a: str, b: str) -> float:
    """Similitud Levenshtein normalizada en [0,1]."""
    if not a or not b:
        return 0.0
    maxlen = max(len(a), len(b))
    if maxlen == 0:
        return 1.0
    return 1 - (_levenshtein(a, b) / maxlen)


# ─── API pública ──────────────────────────────────────────────────────────
def calcular_features_v2(titulo_e: str, titulo_s: str, marca_e: str, marca_s: str) -> dict:
    """Calcula los features v2 de un par de títulos + marcas.

    Devuelve un dict con claves prefijadas 'v2_' para distinguirlas.
    """
    titulo_e = titulo_e or ""
    titulo_s = titulo_s or ""
    marca_e  = (marca_e or "").lower().strip()
    marca_s  = (marca_s or "").lower().strip()

    # char n-grams
    ng3_e = _char_ngrams(titulo_e, 3)
    ng3_s = _char_ngrams(titulo_s, 3)
    ng4_e = _char_ngrams(titulo_e, 4)
    ng4_s = _char_ngrams(titulo_s, 4)

    # tokens raros (>=4 letras, no stopword)
    rar_e = _tokens_raros(titulo_e)
    rar_s = _tokens_raros(titulo_s)

    # números parseados
    nums_e = _extraer_numeros(titulo_e)
    nums_s = _extraer_numeros(titulo_s)

    # códigos técnicos
    cod_e = _extraer_codigos(titulo_e)
    cod_s = _extraer_codigos(titulo_s)

    # primera palabra significativa
    pw_e = _primera_palabra_sig(titulo_e)
    pw_s = _primera_palabra_sig(titulo_s)

    # ratio longitud
    le, ls = len(titulo_e), len(titulo_s)
    long_ratio = min(le, ls) / max(le, ls) if max(le, ls) > 0 else 0

    # similitud de marca (maneja typos y marcas abreviadas)
    lev_marca = _lev_ratio(marca_e, marca_s) if marca_e and marca_s else 0.0

    return {
        "v2_char_jaccard_3gram":  round(_jaccard(ng3_e, ng3_s), 4),
        "v2_char_jaccard_4gram":  round(_jaccard(ng4_e, ng4_s), 4),
        "v2_tokens_raros_jaccard": round(_jaccard(rar_e, rar_s), 4),
        "v2_nums_jaccard":        round(_jaccard(nums_e, nums_s), 4),
        "v2_nums_overlap":        len(nums_e & nums_s),
        "v2_codigos_jaccard":     round(_jaccard(cod_e, cod_s), 4),
        "v2_primera_palabra_match": 1 if pw_e and pw_e == pw_s else 0,
        "v2_longitud_ratio":      round(long_ratio, 4),
        "v2_lev_marca":           round(lev_marca, 4),
    }


FEATURE_V2_COLS = [
    "v2_char_jaccard_3gram",
    "v2_char_jaccard_4gram",
    "v2_tokens_raros_jaccard",
    "v2_nums_jaccard",
    "v2_nums_overlap",
    "v2_codigos_jaccard",
    "v2_primera_palabra_match",
    "v2_longitud_ratio",
    "v2_lev_marca",
]


# ─── Test rápido cuando se ejecuta como script ────────────────────────────
if __name__ == "__main__":
    casos = [
        ("Tornillo Volcanita Roscalata gruesa N°6 x 1 5/8'' CRS zincado 100 unidades",
         "Tornillo Volcanita Rosca Madera CRS Zinc 6 x 1 5/8 x 1000 Unidades",
         "imporper", "generico"),
        ("Cargador rápido tornillos en cinta DCF6202",
         "Atornillador impacto 1/4\" 20v max brushless + baterias 2ah + cargador",
         "dewalt", "dewalt"),
        ("Sikaflex 221 blanco 300ml",
         "Sikaflex-221 Sellador adhesivo blanco 300 ml",
         "sika", "sika"),
        ("Prensa tipo C 4'' 83-504",
         "Set De 5 Piezas Para Atornillar",
         "stanley", "stanley"),
    ]
    print("=" * 70)
    print("TEST DE FEATURES V2")
    print("=" * 70)
    for te, ts, me, ms in casos:
        print(f"\nE: {te}")
        print(f"S: {ts}")
        print(f"M: {me} / {ms}")
        feats = calcular_features_v2(te, ts, me, ms)
        for k, v in feats.items():
            print(f"    {k:<30} {v}")
