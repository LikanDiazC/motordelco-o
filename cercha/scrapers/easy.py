"""Scrapers específicos de Easy. Solo contienen lógica de parseo particular del sitio."""

import json
import re
import time
from cercha.config import STORES, PAGE_LOAD_TIMEOUT_MS
from cercha.scrapers.base_scraper import BaseCatalogScraper, BaseDeepScraper, es_error_fatal


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

        precios = item.get("prices", {}) or {}
        try:
            precio_normal = float(precios.get("normalPrice") or 0)
        except (TypeError, ValueError):
            precio_normal = 0.0
        try:
            precio_oferta = float(precios.get("offerPrice") or 0)
        except (TypeError, ValueError):
            precio_oferta = 0.0

        # precio_clp es lo que cobra la tienda hoy (oferta si hay, normal si no).
        # precio_normal_clp se guarda aparte para calcular descuentos downstream.
        precio_final = precio_oferta if precio_oferta else precio_normal
        if precio_normal == 0:
            precio_normal = precio_final

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
            "precio_clp": precio_final,
            "precio_normal_clp": precio_normal,
            "url": url,
            "url_imagen": _imagen_easy_desde_item(item),
            "urls_imagen": _imagenes_easy_desde_item(item),
            "especificaciones": especificaciones,
        }


def _imagen_easy_desde_item(item: dict) -> str:
    """Primera URL de imagen disponible (compatibilidad con código existente)."""
    urls = _imagenes_easy_desde_item(item)
    return urls[0] if urls else ""


def _imagenes_easy_desde_item(item: dict) -> list:
    """Todas las URLs de imagen del item de Easy, deduplicadas y en orden.

    Easy (VTEX) expone la imagen en varios lugares según el contexto:
    - item["imageUrl"]: campo directo en el productList del search API.
    - item["items"][0]["images"][]: lista VTEX completa (N imágenes por SKU).
    - item["items"][0]["imageUrl"]: URL simple del SKU.
    - item["imagesUrl"] / item["images"]: formas antiguas a nivel producto.
    - item["image"] / item["productImage"] / item["mainImageUrl"]: campos sueltos.
    """
    urls: list[str] = []

    def _add(v):
        if isinstance(v, str) and v and v not in urls:
            urls.append(v)

    # 1) Campo directo más común en productList de búsqueda de Easy
    _add(item.get("imageUrl"))

    # 2) Estructura VTEX estándar: items[*].images[*].imageUrl
    for sku_item in item.get("items") or []:
        if not isinstance(sku_item, dict):
            continue
        imagenes = sku_item.get("images")
        if isinstance(imagenes, list):
            for img in imagenes:
                if isinstance(img, dict):
                    _add(img.get("imageUrl") or img.get("url"))
                elif isinstance(img, str):
                    _add(img)
        _add(sku_item.get("imageUrl"))

    # 3) Listas de imágenes a nivel de producto
    for clave in ("imagesUrl", "images"):
        v = item.get(clave)
        if isinstance(v, list):
            for img in v:
                if isinstance(img, dict):
                    _add(img.get("imageUrl") or img.get("url"))
                elif isinstance(img, str):
                    _add(img)

    # 4) Campos de cadena de texto directos
    for clave in ("image", "productImage", "mainImageUrl"):
        _add(item.get(clave))

    return urls


class EasyDeepScraper(BaseDeepScraper):

    def __init__(self):
        super().__init__(
            STORES["easy"]["catalog_raw"],
            STORES["easy"]["catalog_deep"],
        )

    def extraer_ficha(self, page, producto: dict) -> dict:
        datos = {
            "descripcion_completa": "",
            "especificaciones": producto.get("especificaciones", {}),
            "categorias": [],
        }
        try:
            # domcontentloaded: el __NEXT_DATA__ SSR ya está en el primer HTML;
            # no esperar que terminen de cargar JS/imágenes externos.
            page.goto(producto['url'], timeout=PAGE_LOAD_TIMEOUT_MS,
                      wait_until="domcontentloaded")
            time.sleep(1)

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

            datos["categorias"] = _categorias_easy(data_producto, queries)

            # --- Campos nuevos: EAN, rating, disponibilidad, galería ---
            ean = _ean_desde_data(data_producto, html)
            if ean:
                datos["ean"] = ean

            rating, review_count = _rating_desde_data(data_producto)
            if rating is not None and "rating" not in producto:
                datos["rating"] = rating
            if review_count is not None and "review_count" not in producto:
                datos["review_count"] = review_count

            disp = _disponibilidad_desde_data(data_producto)
            if disp:
                datos["disponibilidad"] = disp

            # Galería completa (si el listado sólo trajo 1 imagen, el detalle suele tener más).
            urls_gal = _imagenes_easy_desde_data(data_producto)
            if urls_gal:
                existentes = set(producto.get("urls_imagen") or [])
                nuevas = [u for u in urls_gal if u not in existentes]
                if nuevas:
                    datos["urls_imagen"] = (producto.get("urls_imagen") or []) + nuevas

            if not producto.get("url_imagen"):
                datos["url_imagen"] = _imagen_easy_desde_data(data_producto) or _og_image(page)

        except Exception as e:
            if es_error_fatal(e):
                raise  # La base class detecta el crash y recrea la página
            print(f"    Error: {e}")

        return datos


def _categorias_easy(data_producto: dict, queries: list) -> list[str]:
    """Busca la ruta de categorías en el árbol dehydrated de React Query.

    Easy usa VTEX, donde las categorías llegan como:
    - data["categoryTree"]: lista de {name, url, children?}
    - data["categories"]: lista de strings tipo "/Ferretería/Fijaciones/Tornillos/"
    - data["breadcrumb"]: lista de {name, href}
    """
    # 1) categoryTree dentro del producto
    arbol = data_producto.get("categoryTree")
    if isinstance(arbol, list) and arbol:
        nombres = []
        for nodo in arbol:
            if isinstance(nodo, dict):
                nombre = nodo.get("name") or nodo.get("categoryName")
                if nombre:
                    nombres.append(nombre.strip())
        if nombres:
            return nombres

    # 2) Lista "categories" estilo "/Cat1/Cat2/Cat3/"
    cats = data_producto.get("categories")
    if isinstance(cats, list) and cats:
        # Usar la ruta más profunda (última)
        ruta = cats[0]
        if isinstance(ruta, str):
            partes = [p.strip() for p in ruta.split("/") if p.strip()]
            if partes:
                return partes

    # 3) Breadcrumb explícito
    bread = data_producto.get("breadcrumb")
    if isinstance(bread, list) and bread:
        nombres = []
        for el in bread:
            if isinstance(el, dict):
                nombre = el.get("name") or el.get("label")
                if nombre:
                    nombres.append(nombre.strip())
        if nombres:
            return nombres

    # 4) Recorrer queries por si la categoría vino en otra entrada
    for q in queries:
        state_data = q.get("state", {}).get("data") or {}
        for clave in ("categoryTree", "breadcrumb", "categories"):
            v = state_data.get(clave)
            if isinstance(v, list) and v:
                if isinstance(v[0], dict):
                    nombres = [x.get("name") or x.get("label") for x in v if isinstance(x, dict)]
                    nombres = [n.strip() for n in nombres if n]
                    if nombres:
                        return nombres
                elif isinstance(v[0], str):
                    partes = [p.strip() for p in v[0].split("/") if p.strip()]
                    if partes:
                        return partes

    return []


def _imagen_easy_desde_data(data_producto: dict) -> str:
    urls = _imagenes_easy_desde_data(data_producto)
    return urls[0] if urls else ""


def _imagenes_easy_desde_data(data_producto: dict) -> list:
    """Todas las URLs de imagen del producto VTEX (items[*].images[*])."""
    urls: list[str] = []
    for sku_item in data_producto.get("items") or []:
        if not isinstance(sku_item, dict):
            continue
        imagenes = sku_item.get("images")
        if isinstance(imagenes, list):
            for img in imagenes:
                u = None
                if isinstance(img, dict):
                    u = img.get("imageUrl") or img.get("url")
                elif isinstance(img, str):
                    u = img
                if isinstance(u, str) and u and u not in urls:
                    urls.append(u)
    return urls


def _ean_desde_data(data_producto: dict, html: str) -> str:
    """Extrae el EAN/GTIN del producto.

    Lo busca primero en items[*].ean (estructura VTEX nativa) y, si no está,
    hace fallback al JSON-LD embebido (<script type="application/ld+json">)
    que suele contener `"gtin13":"..."` en una entry con @type Product.
    """
    for sku_item in data_producto.get("items") or []:
        if isinstance(sku_item, dict):
            ean = sku_item.get("ean") or sku_item.get("EAN")
            if isinstance(ean, str) and ean.strip():
                return ean.strip()

    # Fallback: buscar gtin8/gtin12/gtin13/gtin14 en cualquier JSON-LD.
    match = re.search(r'"gtin(?:8|12|13|14)?"\s*:\s*"(\d{8,14})"', html)
    if match:
        return match.group(1)

    return ""


def _rating_desde_data(data_producto: dict) -> tuple:
    """Devuelve (rating, review_count) si VTEX los expone en el producto."""
    def _to_float(v):
        try:
            return round(float(v), 2) if v is not None else None
        except (TypeError, ValueError):
            return None

    def _to_int(v):
        try:
            return int(float(v)) if v is not None else None
        except (TypeError, ValueError):
            return None

    rating = _to_float(data_producto.get("averageRating")
                       or data_producto.get("rating"))
    reviews = _to_int(data_producto.get("totalReviews")
                      or data_producto.get("reviewCount"))
    return rating, reviews


def _disponibilidad_desde_data(data_producto: dict) -> str:
    """InStock / OutOfStock desde items[*].sellers[*].commertialOffer.AvailableQuantity."""
    for sku_item in data_producto.get("items") or []:
        if not isinstance(sku_item, dict):
            continue
        for seller in sku_item.get("sellers") or []:
            if not isinstance(seller, dict):
                continue
            offer = seller.get("commertialOffer") or {}
            qty = offer.get("AvailableQuantity")
            if isinstance(qty, (int, float)) and qty > 0:
                return "InStock"
    return "OutOfStock" if data_producto.get("items") else ""


def _og_image(page) -> str:
    og = page.query_selector('meta[property="og:image"]')
    if og:
        return (og.get_attribute("content") or "").strip()
    return ""
