"""Tests para el parser de medidas. Verifica que los bugs de fracciones están corregidos."""

import pytest
from cercha.domain.measure_parser import (
    parsear_medida,
    medidas_compatibles,
    extraer_numeros_fallback,
    _normalizar_fraccion,
)


class TestNormalizarFraccion:
    def test_entero(self):
        assert _normalizar_fraccion("6") == 6.0

    def test_fraccion_simple(self):
        assert _normalizar_fraccion("1/2") == 0.5
        assert _normalizar_fraccion("1/4") == 0.25
        assert abs(_normalizar_fraccion("5/8") - 0.625) < 0.001

    def test_fraccion_mixta(self):
        assert _normalizar_fraccion("1 5/8") == 1.625
        assert _normalizar_fraccion("2 1/2") == 2.5
        assert _normalizar_fraccion("1 1/4") == 1.25

    def test_decimal(self):
        assert _normalizar_fraccion("3.5") == 3.5
        assert _normalizar_fraccion("40") == 40.0

    def test_con_guion(self):
        # Sodimac usa "1-5/8" para fracciones mixtas
        assert _normalizar_fraccion("1-5/8") == 1.625


class TestParsearMedida:
    def test_formato_basico(self):
        m = parsear_medida("tornillo 6 x 2")
        assert m is not None
        assert m.calibre == "6"
        assert m.largo == "2"

    def test_formato_pegado(self):
        m = parsear_medida("tornillo 8x2")
        assert m is not None
        assert m.calibre == "8"
        assert m.largo == "2"

    def test_fraccion_en_largo(self):
        m = parsear_medida("tornillo 6 x 1 5/8")
        assert m is not None
        assert m.calibre == "6"
        assert m.largo == "1 5/8"

    def test_fraccion_en_calibre(self):
        m = parsear_medida("tornillo 1/4 x 2 1/2")
        assert m is not None
        assert m.calibre == "1/4"
        assert m.largo == "2 1/2"

    def test_con_mm(self):
        m = parsear_medida("tornillo 4 x 40 mm")
        assert m is not None
        assert m.calibre == "4"
        assert m.largo == "40"
        assert m.unidad == "mm"

    def test_con_pulgadas(self):
        m = parsear_medida("tornillo 6 x 1 5/8\"")
        assert m is not None
        assert m.calibre == "6"

    def test_numeral(self):
        m = parsear_medida("tornillo #14 x 100")
        assert m is not None
        assert m.calibre == "14"
        assert m.largo == "100"

    def test_solo_largo_mm(self):
        """'50mm' sin calibre → calibre vacío, largo=50, unit=mm."""
        m = parsear_medida("tornillo madera 50mm")
        assert m is not None
        assert m.calibre == ""
        assert m.largo == "50"
        assert m.unidad == "mm"

    def test_solo_largo_pulgadas(self):
        """'2 pulgadas' sin calibre → calibre vacío, largo=2, unit=pulgadas."""
        m = parsear_medida("tornillo madera 2 pulgadas")
        assert m is not None
        assert m.calibre == ""
        assert m.largo == "2"
        assert m.unidad == "pulgadas"

    def test_solo_largo_comillas(self):
        """'1 5/8\"' sin calibre → calibre vacío, largo fracción, unit pulgadas."""
        m = parsear_medida('tornillo madera 1 5/8"')
        assert m is not None
        assert m.calibre == ""
        assert m.largo == "1 5/8"
        assert m.unidad == "pulgadas"

    def test_patron_axb_no_afectado_por_patron_b(self):
        """'8x50mm' sigue parseando con calibre=8, no como largo solo."""
        m = parsear_medida("tornillo 8x50mm")
        assert m is not None
        assert m.calibre == "8"
        assert m.largo == "50"
        assert m.unidad == "mm"

    def test_sin_medida(self):
        m = parsear_medida("tornillo para madera zincado")
        assert m is None

    def test_decimal(self):
        m = parsear_medida("tornillo 3.5 x 25")
        assert m is not None
        assert m.calibre == "3.5"
        assert m.largo == "25"


class TestMedidasCompatibles:
    def test_identicas(self):
        q = parsear_medida("6 x 2")
        p = parsear_medida("6 x 2")
        assert medidas_compatibles(q, p) is True

    def test_fraccion_vs_fraccion(self):
        q = parsear_medida("6 x 1 5/8")
        p = parsear_medida("6x1-5/8")
        assert medidas_compatibles(q, p) is True

    def test_no_match_largo_distinto(self):
        q = parsear_medida("8 x 2")
        p = parsear_medida("8 x 1/2")
        assert medidas_compatibles(q, p) is False

    def test_no_match_calibre_distinto(self):
        q = parsear_medida("6 x 2")
        p = parsear_medida("8 x 2")
        assert medidas_compatibles(q, p) is False

    def test_caso_real_bug_anterior(self):
        """Verifica que el bug reportado (8x2 matcheando con 8x1/2) está corregido."""
        q = parsear_medida("tornillo 8x2")
        p = parsear_medida("Tornillo autoperforante 8x1/2''")
        assert medidas_compatibles(q, p) is False

    def test_cuarto_pulgada(self):
        q = parsear_medida("1/4 x 2 1/2")
        p = parsear_medida("tirafondo 1/4 x 2 1/2")
        assert medidas_compatibles(q, p) is True

    def test_conversion_pulgadas_mm(self):
        """8x2 (pulgadas) debe matchear con 8mm x 50.8 (mm)."""
        q = parsear_medida("tornillo 8x2")
        p = parsear_medida("8 x 50.8")
        assert q is not None and p is not None
        assert medidas_compatibles(q, p) is True

    def test_conversion_no_falso_positivo(self):
        """8x2 NO matchea con 8x3 ni con conversiones incorrectas."""
        q = parsear_medida("8x2")
        p = parsear_medida("8x3")
        assert medidas_compatibles(q, p) is False

    def test_query_solo_largo_matchea_producto_con_calibre(self):
        """Query '50mm' (sin calibre) matchea producto '8x50mm' por largo."""
        q = parsear_medida("tornillo madera 50mm")
        p = parsear_medida("tornillo 8 x 50 mm")
        assert q is not None and p is not None
        assert q.calibre == ""   # solo largo en la query
        assert medidas_compatibles(q, p) is True

    def test_query_solo_largo_rechaza_largo_distinto(self):
        """Query '50mm' NO matchea '8x40mm' (largo diferente)."""
        q = parsear_medida("tornillo madera 50mm")
        p = parsear_medida("tornillo 8 x 40 mm")
        assert q is not None and p is not None
        assert medidas_compatibles(q, p) is False

    def test_falso_positivo_bypass_corregido(self):
        """Bug de bypass: '50mm' ya NO devuelve None → medida_query no es None
        → search_engine no ejecuta la rama 'sin medidas' (dim_coincide=True ciego)."""
        m = parsear_medida("tornillo madera 50mm")
        # La corrección exige que devuelva algo (no None)
        assert m is not None, (
            "parsear_medida devuelve None para '50mm', activando el bypass "
            "dim_coincide=True en search_engine"
        )

    def test_turbo_screw_format(self):
        """Formato Turbo Screw #14(6) 100/60 X 100 → calibre 14, largo 100."""
        m = parsear_medida("Tornillo Turbo Screw #14(6) 100/60 X 100 Unds")
        assert m is not None
        assert m.calibre == "14"
        assert m.largo == "100"

    def test_turbo_screw_compatible_con_query(self):
        q = parsear_medida("tornillo turbo screw 14 x 100 mm")
        p = parsear_medida("Tornillo Turbo Screw #14(6) 100/60 X 100 Unds")
        assert q is not None and p is not None
        assert medidas_compatibles(q, p) is True


class TestExtraerNumerosFallback:
    def test_respeta_fracciones(self):
        nums = extraer_numeros_fallback("tornillo 1/4 zincado")
        assert "1/4" in nums
        # No debe tener "1" y "4" sueltos
        assert "1" not in nums or "1/4" in nums

    def test_fraccion_mixta(self):
        nums = extraer_numeros_fallback("tornillo 1 5/8 pulgadas")
        assert "1 5/8" in nums

    def test_multiples_numeros(self):
        nums = extraer_numeros_fallback("tornillo 6 x 40 mm 100 unidades")
        assert "6" in nums
        assert "40" in nums
        assert "100" in nums
