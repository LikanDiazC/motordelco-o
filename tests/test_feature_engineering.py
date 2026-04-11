"""Tests para la ingeniería de características."""

import pytest
from cercha.domain.feature_engineering import (
    construir_super_oracion,
    deducir_caracteristica,
    es_tornillo,
    extraer_medida,
)
from cercha.domain.dictionaries import USO_MAP, PUNTA_MAP, CABEZA_MAP, MATERIAL_MAP


class TestDeducirCaracteristica:
    def test_uso_volcanita(self):
        r = deducir_caracteristica("tornillo volcanita 6x1", USO_MAP, "default")
        assert "Volcanita" in r

    def test_uso_madera(self):
        r = deducir_caracteristica("tirafondo madera aglomerada", USO_MAP, "default")
        assert "Madera" in r

    def test_punta_autoperforante(self):
        r = deducir_caracteristica("autoperforante hexagonal", PUNTA_MAP, "default")
        assert "Autoperforante" in r

    def test_cabeza_lenteja(self):
        r = deducir_caracteristica("cabeza lenteja punta fina", CABEZA_MAP, "default")
        assert "Lenteja" in r

    def test_material_zincado(self):
        r = deducir_caracteristica("tornillo zincado", MATERIAL_MAP, "default")
        assert "Zincado" in r

    def test_boundary_match_zc(self):
        """Abreviación 'zc' solo matchea como palabra completa."""
        r = deducir_caracteristica("tornillo zc 6x1", MATERIAL_MAP, "default")
        assert "Zincado" in r
        # No debería matchear dentro de otra palabra
        r2 = deducir_caracteristica("tornillo bronceado", MATERIAL_MAP, "default")
        assert "Bicromatado" in r2

    def test_default_cuando_no_match(self):
        r = deducir_caracteristica("producto genérico sin info", USO_MAP, "mi_default")
        assert r == "mi_default"


class TestEsTornillo:
    def test_tornillo(self):
        assert es_tornillo("Tornillo Volcanita 6x1") is True

    def test_tirafondo(self):
        assert es_tornillo("TIRAFONDO 1/4 x 2") is True

    def test_autoperforante(self):
        assert es_tornillo("Autoperforante hexagonal 12x2") is True

    def test_no_tornillo(self):
        assert es_tornillo("Sierra circular Bosch") is False
        assert es_tornillo("Taladro percutor 13mm") is False


class TestConstruirSuperOracion:
    def test_estructura_simetrica(self):
        """Verifica que la súper oración siempre tiene la misma estructura."""
        # Simular producto Sodimac
        resultado_s = construir_super_oracion(
            "Tornillo Autoperforante Madera 10mm 100 unidades",
            {"Material": "Acero", "Tipo de cabeza": "Phillips", "Largo": "50mm", "Diámetro": "10mm"},
        )
        # Simular producto Easy
        resultado_e = construir_super_oracion(
            "Tornillo autoperforante madera 10mm 100 unidades Mamut",
            {"Material": "Acero", "Terminación": "Zincado"},
            "tornillo para uso en madera",
        )

        # Ambos deben tener la misma estructura: titulo + punta + medida + uso + cabeza + material
        for r in [resultado_s, resultado_e]:
            parts = r["texto_embedding"]
            # Debe contener el título original
            assert "ornillo" in parts.lower()
            # Debe contener features extraídas
            assert r["uso"] in parts
            assert r["cabeza"] in parts
            assert r["material"] in parts

    def test_extrae_medida_desde_specs(self):
        r = construir_super_oracion(
            "Tornillo para madera",
            {"Diámetro": "6mm", "Largo": "40mm"},
        )
        assert "6mm" in r["medida"]
        assert "40mm" in r["medida"]

    def test_extrae_medida_desde_titulo(self):
        r = construir_super_oracion(
            "Tornillo volcanita 6 x 1 5/8 100un",
            {},
        )
        assert r["medida"] != "Medida no detectada"


class TestExtraerMedida:
    def test_desde_specs(self):
        m = extraer_medida("Tornillo X", {"Diámetro": "10mm", "Largo": "50mm"})
        assert "10mm" in m and "50mm" in m

    def test_desde_titulo_cuando_specs_vacias(self):
        m = extraer_medida("Tornillo 6 x 1 5/8 pulgadas", {})
        assert m != "Medida no detectada"

    def test_fallback_medida_no_detectada(self):
        m = extraer_medida("Tornillo generico", {})
        assert m == "Medida no detectada"
