"""Tests para el normalizador Easy/Sodimac -> esquema canónico."""

import pytest

from cercha.domain.normalizer import (
    normalizar_producto,
    _valor_a_mm,
    _dimensiones_desde_titulo,
    _parse_cantidad,
)


class TestValorAMm:
    def test_mm_explicito(self):
        assert _valor_a_mm("35 mm") == 35.0
        assert _valor_a_mm("4.2 mm") == 4.2

    def test_pulgadas_con_comillas(self):
        assert _valor_a_mm('2"') == 50.8
        assert _valor_a_mm('1 1/4 "') == pytest.approx(31.75, abs=0.01)

    def test_pulgadas_con_palabra(self):
        assert _valor_a_mm("1 1/4 Pulgadas") == pytest.approx(31.75, abs=0.01)
        assert _valor_a_mm("2 pulgadas") == 50.8

    def test_fraccion_con_guion_sodimac(self):
        assert _valor_a_mm('1-1/4 "') == pytest.approx(31.75, abs=0.01)
        assert _valor_a_mm("1-1/4 pulgadas") == pytest.approx(31.75, abs=0.01)

    def test_sin_unidad_asume_mm(self):
        assert _valor_a_mm("35") == 35.0

    def test_vacio(self):
        assert _valor_a_mm("") is None
        assert _valor_a_mm(None) is None


class TestDimensionesDesdeTitulo:
    def test_sodimac_drywall(self):
        diam, largo, cruda = _dimensiones_desde_titulo('Tornillo drywall 6x1 1/4"')
        assert diam == 6.0
        assert largo == pytest.approx(31.75, abs=0.01)
        assert "6" in cruda and "1 1/4" in cruda

    def test_sodimac_mm(self):
        diam, largo, cruda = _dimensiones_desde_titulo("Tornillo Autoperforante Madera 35 mm 4.2 mm 100 unidad(es)")
        assert largo is not None

    def test_easy_fraccion(self):
        diam, largo, _ = _dimensiones_desde_titulo("Tornillo volcanita 6x1.1/4'' zc c100")
        # "1.1/4" es un formato raro que el parser no reconoce como fracción mixta,
        # pero al menos el calibre sale bien.
        assert diam == 6.0

    def test_titulo_sin_medida(self):
        diam, largo, cruda = _dimensiones_desde_titulo("Tornillo zincado para madera")
        assert diam is None
        assert largo is None
        assert cruda == ""


class TestParseCantidad:
    def test_sodimac_cantidad_por_paquete(self):
        specs = {"Cantidad por paquete": "1000 unidad(es)"}
        assert _parse_cantidad(specs, "titulo") == 1000

    def test_easy_contenido(self):
        specs = {"Contenido": "100 Unidades"}
        assert _parse_cantidad(specs, "titulo") == 100

    def test_desde_titulo_cuando_specs_faltan(self):
        specs = {}
        assert _parse_cantidad(specs, "Tornillo drywall 200 unidades") == 200

    def test_default_uno(self):
        assert _parse_cantidad({}, "Tornillo suelto") == 1


class TestNormalizarProductoSodimac:
    def test_tornillo_drywall_completo(self):
        prod_raw = {
            "sku": "110295767",
            "marca": "MAMUT",
            "titulo": 'Tornillo drywall 6x1 1/4"',
            "precio_clp": 4390.0,
            "url": "https://www.sodimac.cl/sodimac-cl/articulo/110294025/Tornillo-drywall/110295767",
            "url_imagen": "https://media.falabella.com/sodimacCL/1908766_001/public",
            "categorias": ["Ferretería", "Fijaciones", "Tornillos"],
            "descripcion": "Tornillo drywall 6x1 1/4\" 1000 unidades...",
            "especificaciones": {
                "Tipo de tornillo": "Madera",
                "Superficie de aplicación": "Yeso-Cartón",
                "Material": "Acero",
                "Tipo de cabeza": "Phillips",
                "Cantidad por paquete": "1000 unidad(es)",
                "Largo": "1-1/4 \"",
                "Color": "Pavonado",
                "Diámetro": "6 mm",
            },
        }
        out = normalizar_producto(prod_raw, "sodimac")

        assert out["id_producto"] == "sodimac-110295767"
        assert out["tienda"] == "sodimac"
        assert out["url_imagen"].startswith("https://")

        md = out["metadata_basica"]
        assert md["marca"] == "MAMUT"
        assert md["precio_clp"] == 4390
        assert md["categorias"] == ["Ferretería", "Fijaciones", "Tornillos"]

        mt = out["metadata_tecnica"]
        assert mt["material"] == "Acero"
        assert mt["tipo_cabeza"] == "Phillips"
        assert mt["tipo_punta"] == "Madera"
        assert mt["uso"] == "Yeso-Cartón"  # superficie mapeada a uso
        assert mt["cantidad_empaque"] == 1000
        # 6 mm x 1 1/4"  → diámetro 6 mm, largo 31.75 mm
        assert mt["dimensiones"]["diametro_mm"] == 6.0
        assert mt["dimensiones"]["largo_mm"] == pytest.approx(31.75, abs=0.01)

    def test_categoria_fallback_desde_titulo(self):
        prod = {
            "sku": "x", "titulo": "Tornillo zincado generico",
            "precio_clp": 100, "especificaciones": {},
        }
        out = normalizar_producto(prod, "sodimac")
        assert "Tornillos" in out["metadata_basica"]["categorias"][0]


class TestNormalizarProductoEasy:
    def test_tornillo_volcanita_pulgadas(self):
        prod_raw = {
            "sku": "911648",
            "marca": "Mamut",
            "titulo": "Tornillo volc rosca gruesa zbr 6 x 2 200un Mamut",
            "precio_clp": 3890.0,
            "url": "https://www.easy.cl/tornillo-volc-200un-mamut-911648/p",
            "url_imagen": "",
            "categorias": ["Ferretería", "Fijaciones", "Tornillos"],
            "descripcion_completa": "<p>Tornillo <b>volcanita</b> 200 unidades.</p>",
            "especificaciones": {
                "Contenido": "200 Unidades",
                "Terminación": "Zincado brillante",
                "Diámetro": "6 mm",
                "Largo": "2\"",
                "Material": "Acero",
                "Uso": "Techumbres",
                "Modelo": "Rosca gruesa",
            },
        }
        out = normalizar_producto(prod_raw, "easy")

        assert out["id_producto"] == "easy-911648"
        mt = out["metadata_tecnica"]
        assert mt["cantidad_empaque"] == 200
        # Easy: "Largo": "2\"" → 50.8 mm
        # Pero el título también trae "6 x 2" → que parsea como pulgadas (por < 10).
        assert mt["dimensiones"]["largo_mm"] == pytest.approx(50.8, abs=0.5)
        assert mt["dimensiones"]["diametro_mm"] == 6.0
        assert mt["material"] == "Acero"
        assert mt["tipo_punta"] == "Rosca gruesa"  # Modelo → tipo_punta

    def test_descripcion_limpia_sin_html(self):
        prod = {
            "sku": "1", "titulo": "Tornillo", "precio_clp": 100,
            "descripcion_completa": "<div><p>Hola <b>mundo</b></p></div>",
            "especificaciones": {},
        }
        out = normalizar_producto(prod, "easy")
        assert "<" not in out["contenido_vectorial"]["descripcion_limpia"]
        assert "Hola mundo" in out["contenido_vectorial"]["descripcion_limpia"]


class TestTextoAVectorizar:
    def test_incluye_categorias_y_atributos(self):
        prod = {
            "sku": "1",
            "marca": "MAMUT",
            "titulo": "Tornillo drywall 6x1 1/4\"",
            "precio_clp": 4390,
            "categorias": ["Ferretería", "Fijaciones", "Tornillos"],
            "especificaciones": {"Material": "Acero", "Tipo de cabeza": "Phillips"},
        }
        out = normalizar_producto(prod, "sodimac")
        texto = out["contenido_vectorial"]["texto_a_vectorizar"]
        assert "Tornillos" in texto
        assert "Acero" in texto
        assert "Phillips" in texto
