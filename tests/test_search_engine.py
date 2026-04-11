"""Tests para el motor de búsqueda."""

import pytest
from cercha.domain.search_engine import limpiar_texto, extraer_cantidad
from cercha.judge import evaluar_match


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
