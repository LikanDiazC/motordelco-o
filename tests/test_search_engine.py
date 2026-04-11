"""Tests para el motor de búsqueda."""

import pytest
import numpy as np
from cercha.domain.search_engine import limpiar_texto, extraer_cantidad, buscar_en_tienda
from cercha.judge import evaluar_match
from cercha.config import LEXICAL_BONUS_PER_WORD, STOP_WORDS


class TestLimpiarTexto:
    def test_minusculas(self):
        assert limpiar_texto("TORNILLO") == "tornillo"

    def test_acentos(self):
        assert "tornillo" in limpiar_texto("Tórnillo")

    def test_sinonimos_volcanita(self):
        assert "drywall" in limpiar_texto("tornillo volcanita")

    def test_separacion_digitos_letras(self):
        result = limpiar_texto("6x1")
        assert "6" in result and "x" in result and "1" in result

    def test_no_rompe_fracciones(self):
        result = limpiar_texto("1/2 pulgada")
        # La fracción debe preservarse (/ no es letra ni dígito)
        assert "1/2" in result


class TestExtraerCantidad:
    def test_unidades_simple(self):
        assert extraer_cantidad("Tornillo 6x1 100 unidades") == 100

    def test_unidades_sodimac(self):
        assert extraer_cantidad("Tornillo Madera 10mm 40 unidad(es)") == 40

    def test_bolsa(self):
        assert extraer_cantidad("Tornillo (bolsa 1.000 Un)") == 1000

    def test_sin_cantidad(self):
        assert extraer_cantidad("Tornillo avellanado 6x1") == 1

    def test_unds(self):
        assert extraer_cantidad("Tornillo Turbo 100 Unds") == 100

    def test_no_captura_medida_como_cantidad(self):
        """No debe confundir el '6' de la medida con la cantidad."""
        result = extraer_cantidad("Tornillo 6 x 1 5/8 zincado")
        assert result == 1  # No hay indicador de cantidad

    def test_pack(self):
        assert extraer_cantidad("Pack de 50 tornillos") == 50

    def test_from_specs_contenido(self):
        """Easy: 'Contenido: 600 unidades' en specs."""
        specs = {"Contenido": "600 unidades"}
        assert extraer_cantidad("Tornillo drywall 6x1 5/8 Mamut", specs) == 600

    def test_from_specs_contenido_caja(self):
        """Easy: 'Contenido: 1 Caja de tornillos (100 unidades)'."""
        specs = {"Contenido": "1 Caja de tornillos (100 unidades)"}
        assert extraer_cantidad("Tornillo Volcanita 6x1 5/8", specs) == 100

    def test_from_specs_cantidad_paquete(self):
        """Sodimac: 'Cantidad por paquete: 500'."""
        specs = {"Cantidad por paquete": "500"}
        assert extraer_cantidad("Tornillo Volcanita Punta Fina 6x1", specs) == 500

    def test_bal_pattern(self):
        """Easy: 'bal600u' en título."""
        assert extraer_cantidad("Tornillo volcanita hf zc 6x15/8 bal 600u+ph 2 Imporper") == 600

    def test_b_pattern(self):
        """Easy: 'b500' en título."""
        assert extraer_cantidad("Tornillo punta volcanita 6x2 zc b500 Imporper") == 500

    def test_un_dot_pattern(self):
        """Easy: '3 un.' al final."""
        assert extraer_cantidad("Tornillo turbo screw torx 14[6]x100 mm 3 un.") == 3


class TestEvaluarMatch:
    def test_match_alta_similitud_con_dimension(self):
        assert evaluar_match(0.85, True) is True

    def test_no_match_sin_dimension(self):
        """Sin dimensiones, incluso alta similitud no basta."""
        assert evaluar_match(0.85, False) is False

    def test_match_baja_similitud_con_dimension(self):
        """Con dimensiones exactas, el umbral baja a 0.55."""
        assert evaluar_match(0.60, True) is True

    def test_no_match_muy_baja_similitud(self):
        """Debajo de 0.55 incluso con dimensiones no matchea."""
        assert evaluar_match(0.50, True) is False

    def test_no_match_ambos_fallan(self):
        assert evaluar_match(0.50, False) is False

    def test_umbral_adaptativo_caso_8x2(self):
        """Query corta '8x2' con similitud 0.67 y dimensiones OK → debe matchear."""
        assert evaluar_match(0.67, True) is True

    def test_frontera_sin_dimension(self):
        """Sin dimensiones, el umbral es 0.70."""
        assert evaluar_match(0.70, False) is False
        assert evaluar_match(0.699, False) is False


class TestLexicalBonusStopWords:
    """Verifica que el bono léxico NO infle el puntaje por stop words.

    Estrategia: vectores ortogonales → cosine sim = 0.0 exacto.
    Cualquier bono incorrecto se refleja directamente en resultado.similitud.
    """

    def _make_store(self, titulo: str):
        """Crea metadata y vectores mínimos para una tienda de un solo producto."""
        metadata = [{'titulo': titulo, 'precio': 1000}]
        # Vector ortogonal al query → cosine = 0.0 garantizado
        vectores = np.array([[0.0, 1.0]])
        return metadata, vectores

    @property
    def _query_vector(self):
        return np.array([1.0, 0.0])

    # ------------------------------------------------------------------
    # Casos que NO deben sumar bono
    # ------------------------------------------------------------------

    def test_preposicion_de_no_suma_bono(self):
        """'de' es stop word → intersección vacía → bono 0."""
        metadata, vectores = self._make_store("perno de acero")
        # "tornillo de madera" ∩ "perno de acero" en contenido = {} (solo "de" coincide)
        resultado = buscar_en_tienda(
            "tornillo de madera", self._query_vector, metadata, vectores
        )
        assert resultado.similitud == pytest.approx(0.0, abs=1e-6), (
            "Stop word 'de' infló el puntaje léxico"
        )

    def test_preposicion_para_no_suma_bono(self):
        """'para' es stop word → no debe aportar bono."""
        metadata, vectores = self._make_store("perno para madera")
        # "tornillo para drywall" ∩ "perno para madera" en contenido = {}
        resultado = buscar_en_tienda(
            "tornillo para drywall", self._query_vector, metadata, vectores
        )
        assert resultado.similitud == pytest.approx(0.0, abs=1e-6), (
            "Stop word 'para' infló el puntaje léxico"
        )

    def test_separador_x_no_suma_bono(self):
        """'x' (separador dimensional como en '6x2') es stop word."""
        metadata, vectores = self._make_store("perno x acero")
        resultado = buscar_en_tienda(
            "tornillo x drywall", self._query_vector, metadata, vectores
        )
        assert resultado.similitud == pytest.approx(0.0, abs=1e-6), (
            "Stop word 'x' infló el puntaje léxico"
        )

    def test_multiples_stop_words_no_acumulan(self):
        """Varias stop words coincidentes ('de', 'para', 'con') no acumulan bono."""
        metadata, vectores = self._make_store("perno para madera con acabado de acero")
        # Único match de contenido posible sería "acero" vs query sin "acero"
        resultado = buscar_en_tienda(
            "tornillo de 6 para drywall con punta",
            self._query_vector, metadata, vectores,
        )
        assert resultado.similitud == pytest.approx(0.0, abs=1e-6), (
            "Múltiples stop words acumularon bono incorrecto"
        )

    def test_stop_words_conocidas_estan_en_el_set(self):
        """Smoke test: las stop words del bug report están en STOP_WORDS."""
        for palabra in ("de", "para", "con", "x"):
            assert palabra in STOP_WORDS, f"'{palabra}' debería estar en STOP_WORDS"

    # ------------------------------------------------------------------
    # Casos que SÍ deben sumar bono (regresión)
    # ------------------------------------------------------------------

    def test_palabra_contenido_si_suma_bono(self):
        """Una palabra de contenido compartida SÍ debe sumar bono."""
        metadata, vectores = self._make_store("tornillo de acero zincado")
        # "tornillo" no es stop word → intersección = {"tornillo"} → bono = 0.05
        resultado = buscar_en_tienda(
            "tornillo para drywall", self._query_vector, metadata, vectores
        )
        expected = 1 * LEXICAL_BONUS_PER_WORD
        assert resultado.similitud == pytest.approx(expected, abs=1e-6), (
            "Palabra de contenido 'tornillo' no sumó bono"
        )

    def test_dos_palabras_contenido_suman_bono_doble(self):
        """Dos palabras de contenido coincidentes suman bono x2."""
        metadata, vectores = self._make_store("tornillo drywall zincado largo")
        # "tornillo" y "drywall" coinciden → bono = 2 * 0.05 = 0.10
        resultado = buscar_en_tienda(
            "tornillo de drywall", self._query_vector, metadata, vectores
        )
        expected = 2 * LEXICAL_BONUS_PER_WORD
        assert resultado.similitud == pytest.approx(expected, abs=1e-6), (
            "Dos palabras de contenido no sumaron bono doble"
        )

    def test_bono_maximo_cappado_a_1(self):
        """El bono nunca puede llevar similitud por encima de 1.0."""
        # Vectores idénticos → cosine = 1.0; bono adicional debe quedar capeado
        vectores_iguales = np.array([[1.0, 0.0]])
        metadata = [{'titulo': 'tornillo drywall zincado', 'precio': 1000}]
        resultado = buscar_en_tienda(
            "tornillo drywall", self._query_vector, metadata, vectores_iguales
        )
        assert resultado.similitud <= 1.0
