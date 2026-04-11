"""Scrapers específicos de Sodimac. Solo contienen lógica de parseo particular del sitio."""

import json
import time
from cercha.config import STORES, PAGE_LOAD_TIMEOUT_MS
from cercha.scrapers.base_scraper import BaseCatalogScraper, BaseDeepScraper


class SodimacCatalogScraper(BaseCatalogScraper):

    def __init__(self, busqueda: str = "tornillos"):
        super().__init__(busqueda, STORES["sodimac"]["catalog_raw"])

    def construir_url(self, pagina: int) -> str:
        base = f"https://www.sodimac.cl/sodimac-cl/buscar?Ntt={self.busqueda}"
        if pagina > 1:
            return f"{base}&page={pagina}&store=so_com"
        return base

    def extraer_paginacion(self, datos_json: dict) -> tuple:
        pag = datos_json.get("props", {}).get("pageProps", {}).get("pagination", {})
        return pag.get("count", 0), pag.get("perPage", 48)

    def extraer_productos(self, datos_json: dict) -> list:
        return datos_json.get("props", {}).get("pageProps", {}).get("results", [])

    def parsear_producto(self, item: dict) -> dict:
        titulo = item.get("displayName", "Sin titulo")
        sku = item.get("skuId", "Sin SKU")
        marca = item.get("brand", "Sin marca")
        producto_id = item.get("productId", sku)

        precio = self._extraer_precio(item.get("prices", []))

        titulo_url = titulo.replace(" ", "-").replace("/", "-")
        url = f"https://www.sodimac.cl/sodimac-cl/articulo/{producto_id}/{titulo_url}/{sku}"

        return {
            "sku": sku,
            "marca": marca,
            "titulo": titulo,
            "precio_clp": precio,
            "url": url,
        }

    def _extraer_precio(self, precios_raw: list) -> float:
        """Extracción robusta de precio que tolera múltiples formatos de la API."""
        if not precios_raw:
            return 0.0
        precio = precios_raw[0].get("price", 0)
        if isinstance(precio, list):
            precio = precio[0] if precio else 0
        if isinstance(precio, str):
            return float(precio.replace(".", "").replace(",", "."))
        return float(precio)


class SodimacDeepScraper(BaseDeepScraper):

    def __init__(self):
        super().__init__(
            STORES["sodimac"]["catalog_raw"],
            STORES["sodimac"]["catalog_deep"],
        )

    def extraer_ficha(self, page, producto: dict) -> dict:
        datos = {"descripcion": "", "especificaciones": {}}
        try:
            page.goto(producto['url'], timeout=PAGE_LOAD_TIMEOUT_MS)
            try:
                page.wait_for_selector("table.specification-table", timeout=4000)
            except Exception:
                return datos

            desc_el = page.query_selector(".fb-product-information-tab__copy")
            if desc_el:
                datos["descripcion"] = desc_el.inner_text().replace('\n', ' ').strip()

            filas = page.query_selector_all("table.specification-table tr")
            for fila in filas:
                nombre = fila.query_selector(".property-name")
                valor = fila.query_selector(".property-value")
                if nombre and valor:
                    datos["especificaciones"][nombre.inner_text().strip()] = valor.inner_text().strip()

        except Exception as e:
            print(f"    Error: {e}")

        return datos
