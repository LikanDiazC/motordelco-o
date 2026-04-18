"""Scrapers específicos de Easy. Solo contienen lógica de parseo particular del sitio."""

import json
import re
import time
from cercha.config import STORES, PAGE_LOAD_TIMEOUT_MS
from cercha.scrapers.base_scraper import BaseCatalogScraper, BaseDeepScraper


EASY_BUSQUEDAS = [
    "tornillo", "perno tuerca", "mdf osb terciado",
    "pintura latex", "cemento mortero",
]


class EasyCatalogScraper(BaseCatalogScraper):

    def __init__(self, busquedas: "str | list[str]" = EASY_BUSQUEDAS):
        super().__init__(busquedas, STORES["easy"]["catalog_raw"])

    def construir_url(self, pagina: int) -> str:
        base = f"https://www.easy.cl/search/{self.busqueda}"
        if pagina > 1:
            return f"{base}?page={pagina}"
        return base

    def extraer_paginacion(self, datos_json: dict) -> tuple:
        server = (datos_json.get("props", {})
                  .get("pageProps", {})
                  .get("serverProductsResponse", {}))
        total = server.get("recordsFiltered", 0)
        return total, 40  # Easy usa 40 por página

    def extraer_productos(self, datos_json: dict) -> list:
        return (datos_json.get("props", {})
                .get("pageProps", {})
                .get("serverProductsResponse", {})
                .get("productList", []))

    def parsear_producto(self, item: dict) -> dict:
        titulo = item.get("productName", "Sin titulo")
        sku = item.get("sku", "Sin SKU")
        marca = item.get("brand", "Sin marca")

        precios = item.get("prices", {})
        precio_normal = precios.get("normalPrice") or 0
        precio_oferta = precios.get("offerPrice") or precio_normal
        precio_final = precio_oferta if precio_oferta else precio_normal

        link_text = item.get("linkText", "")
        url = f"https://www.easy.cl/{link_text}"

        # Specs del listado (básicas)
        specs_crudas = item.get("specifications", [])
        especificaciones = {}
        for spec in specs_crudas:
            nombre = spec.get("name", "")
            valores = spec.get("values", [])
            if nombre and valores:
                especificaciones[nombre] = valores[0]

        return {
            "sku": sku,
            "marca": marca,
            "titulo": titulo,
            "precio_clp": float(precio_final),
            "url": url,
            "especificaciones": especificaciones,
        }


class EasyDeepScraper(BaseDeepScraper):

    def __init__(self):
        super().__init__(
            STORES["easy"]["catalog_raw"],
            STORES["easy"]["catalog_deep"],
        )

    def extraer_ficha(self, page, producto: dict) -> dict:
        datos = {"descripcion_completa": "", "especificaciones": producto.get("especificaciones", {})}
        try:
            page.goto(producto['url'], timeout=PAGE_LOAD_TIMEOUT_MS)
            time.sleep(2)

            html = page.content()
            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                html, re.DOTALL
            )
            if not match:
                return datos

            datos_json = json.loads(match.group(1))
            queries = (datos_json.get("props", {})
                       .get("pageProps", {})
                       .get("dehydratedState", {})
                       .get("queries", []))

            data_producto = {}
            for q in queries:
                state_data = q.get("state", {}).get("data", {})
                if "specifications" in state_data:
                    data_producto = state_data
                    break

            datos["descripcion_completa"] = data_producto.get("description", "")

            specs_crudas = data_producto.get("specifications", {})
            specs_limpias = {}
            for clave, valor_lista in specs_crudas.items():
                if isinstance(valor_lista, list) and valor_lista:
                    specs_limpias[clave] = valor_lista[0]
                else:
                    specs_limpias[clave] = valor_lista
            datos["especificaciones"] = specs_limpias

        except Exception as e:
            print(f"    Error: {e}")

        return datos
