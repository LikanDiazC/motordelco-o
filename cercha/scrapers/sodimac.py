"""Scrapers específicos de Sodimac. Solo contienen lógica de parseo particular del sitio."""

import json
from cercha.config import STORES, PAGE_LOAD_TIMEOUT_MS
from cercha.scrapers.base_scraper import BaseCatalogScraper, BaseDeepScraper, es_error_fatal


SODIMAC_BUSQUEDAS = [
    "tornillos", "pernos tuercas", "tablero mdf", "plancha osb",
    "pintura latex", "cemento mortero",
]

# CDN de imágenes de Sodimac Chile. El mediaId del catálogo se concatena
# aquí para formar la URL pública (ej. "47333_001/public").
SODIMAC_MEDIA_BASE = "https://media.sodimac.cl/sodimacCL"


class SodimacCatalogScraper(BaseCatalogScraper):

    def __init__(self, busquedas: "str | list[str]" = SODIMAC_BUSQUEDAS):
        super().__init__(busquedas, STORES["sodimac"]["catalog_raw"])

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

        precios = self._extraer_precios(item.get("prices", []))

        titulo_url = titulo.replace(" ", "-").replace("/", "-")
        url = f"https://www.sodimac.cl/sodimac-cl/articulo/{producto_id}/{titulo_url}/{sku}"

        rating, review_count = _rating_desde_item(item)

        resultado = {
            "sku": sku,
            "marca": marca,
            "titulo": titulo,
            "precio_clp": precios["precio_clp"],
            "precio_normal_clp": precios["precio_normal_clp"],
            "url": url,
            "url_imagen": self._extraer_imagen(item, producto_id),
            "urls_imagen": self._extraer_imagenes(item, producto_id),
        }
        if rating is not None:
            resultado["rating"] = rating
        if review_count is not None:
            resultado["review_count"] = review_count
        return resultado

    def _extraer_precios(self, precios_raw: list) -> dict:
        """Extrae precio actual y precio normal.

        Sodimac expone varios precios en `prices[]` con campo `type`
        (`normalPrice`, `cmrPrice`, `internetPrice`, ...). El primero
        suele ser el precio a mostrar (oferta/actual), pero puede no
        coincidir con el `normalPrice`; guardamos ambos para calcular
        descuentos downstream.
        """
        if not precios_raw:
            return {"precio_clp": 0.0, "precio_normal_clp": 0.0}

        precio_actual = _parse_precio_clp(precios_raw[0].get("price", 0))
        precio_normal = precio_actual  # default: asumimos que no hay oferta
        for p in precios_raw:
            if isinstance(p, dict) and p.get("type") == "normalPrice":
                precio_normal = _parse_precio_clp(p.get("price", 0))
                break

        # Si el "normal" es menor que el actual, algo anda al revés:
        # usamos el mayor como normal para evitar descuentos negativos.
        if precio_normal < precio_actual:
            precio_normal = precio_actual

        return {"precio_clp": precio_actual, "precio_normal_clp": precio_normal}

    def _extraer_imagen(self, item: dict, producto_id: str) -> str:
        """URL de la imagen principal (primera de la lista)."""
        urls = self._extraer_imagenes(item, producto_id)
        return urls[0] if urls else ""

    def _extraer_imagenes(self, item: dict, producto_id: str) -> list:
        """Obtiene todas las URLs de imagen disponibles, deduplicadas y en orden.

        Sodimac expone las imágenes en varios campos según la versión del
        front. `mediaUrls` suele contener varios mediaIds (vista principal,
        ángulos, en contexto, etc.) — guardarlos todos permite mostrar
        galería sin re-scrapear.
        """
        urls: list[str] = []

        def _resolver(v):
            if isinstance(v, list) and v:
                v = v[0]
            if isinstance(v, str) and v:
                return v if v.startswith("http") else f"{SODIMAC_MEDIA_BASE}/{v}/public"
            return None

        # mediaUrls: lista principal de medias
        for u in item.get("mediaUrls") or []:
            r = _resolver(u)
            if r and r not in urls:
                urls.append(r)

        # primaryImage/image: campo simple
        for clave in ("primaryImage", "image"):
            r = _resolver(item.get(clave))
            if r and r not in urls:
                urls.append(r)

        # media[]: lista de dicts {url, imageUrl}
        for m in item.get("media") or []:
            if isinstance(m, dict):
                r = _resolver(m.get("url") or m.get("imageUrl"))
                if r and r not in urls:
                    urls.append(r)

        # Fallback: construir por productId + posición
        if not urls and producto_id:
            urls.append(f"{SODIMAC_MEDIA_BASE}/{producto_id}_001/public")

        return urls


class SodimacDeepScraper(BaseDeepScraper):

    def __init__(self):
        super().__init__(
            STORES["sodimac"]["catalog_raw"],
            STORES["sodimac"]["catalog_deep"],
        )

    def extraer_ficha(self, page, producto: dict) -> dict:
        datos = {
            "descripcion": "",
            "especificaciones": {},
            "categorias": [],
        }
        try:
            # domcontentloaded: evita quedar pegado esperando recursos lentos/colgados.
            # La tabla de specs se carga vía JS, así que la esperamos explícitamente abajo.
            page.goto(producto['url'], timeout=PAGE_LOAD_TIMEOUT_MS,
                      wait_until="domcontentloaded")
            try:
                page.wait_for_selector("table.specification-table", timeout=5000)
            except Exception:
                # Sin tabla de specs igual intentamos categorías + imagen.
                pass

            desc_el = page.query_selector(".fb-product-information-tab__copy")
            if desc_el:
                datos["descripcion"] = desc_el.inner_text().replace('\n', ' ').strip()

            filas = page.query_selector_all("table.specification-table tr")
            for fila in filas:
                nombre = fila.query_selector(".property-name")
                valor = fila.query_selector(".property-value")
                if nombre and valor:
                    datos["especificaciones"][nombre.inner_text().strip()] = valor.inner_text().strip()

            datos["categorias"] = _breadcrumbs_sodimac(page)

            # Rating y disponibilidad desde JSON-LD (cuando existe).
            jsonld = _jsonld_producto(page)
            rating, review_count = _rating_desde_jsonld(jsonld)
            if rating is not None and "rating" not in producto:
                datos["rating"] = rating
            if review_count is not None and "review_count" not in producto:
                datos["review_count"] = review_count

            disponibilidad = _availability_desde_jsonld(jsonld)
            if disponibilidad:
                datos["disponibilidad"] = disponibilidad

            # Si el catálogo no trajo imagen, intentamos og:image del detalle.
            if not producto.get("url_imagen"):
                og = page.query_selector('meta[property="og:image"]')
                if og:
                    datos["url_imagen"] = (og.get_attribute("content") or "").strip()

        except Exception as e:
            if es_error_fatal(e):
                raise  # La base class detecta el crash y recrea la página
            print(f"    Error: {e}")

        return datos


def _breadcrumbs_sodimac(page) -> list[str]:
    """Ruta de categorías, buscando en JSON-LD primero y en DOM como fallback."""
    cats = _breadcrumbs_desde_jsonld(page)
    if cats:
        return cats
    return _breadcrumbs_desde_dom(page)


def _breadcrumbs_desde_jsonld(page) -> list[str]:
    """BreadcrumbList en cualquier <script type='application/ld+json'>."""
    scripts = page.query_selector_all('script[type="application/ld+json"]')
    for s in scripts:
        raw = (s.inner_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for entry in items:
            if not isinstance(entry, dict):
                continue
            if entry.get("@type") == "BreadcrumbList":
                return _nombres_breadcrumb(entry.get("itemListElement", []))
            for sub in entry.get("@graph", []) or []:
                if isinstance(sub, dict) and sub.get("@type") == "BreadcrumbList":
                    return _nombres_breadcrumb(sub.get("itemListElement", []))
    return []


def _nombres_breadcrumb(item_list: list) -> list[str]:
    """Extrae nombres del itemListElement de un BreadcrumbList JSON-LD.

    Ordena por `position` (1 = raíz, valores mayores = hojas) para garantizar
    que el resultado salga en orden raíz→hoja independientemente del orden en
    que el sitio emita los items.
    """
    # Ordenar por position si existe (evita el orden leaf-first de Sodimac)
    try:
        item_list = sorted(
            item_list,
            key=lambda el: int(el.get("position", 999)) if isinstance(el, dict) else 999,
        )
    except Exception:
        pass  # Si falla la ordenación, usamos el orden original

    nombres = []
    for el in item_list:
        if not isinstance(el, dict):
            continue
        nombre = el.get("name")
        if not nombre and isinstance(el.get("item"), dict):
            nombre = el["item"].get("name")
        if isinstance(nombre, str):
            nombre = nombre.strip()
            if nombre and nombre.lower() not in ("inicio", "home", "sodimac"):
                nombres.append(nombre)
    return nombres


def _breadcrumbs_desde_dom(page) -> list[str]:
    """Selectores típicos del breadcrumb de Sodimac (clases cambian con deploys)."""
    selectores = (
        'nav[aria-label*="breadcrumb" i] a',
        'nav[aria-label*="Breadcrumb"] a',
        'ol.breadcrumb li',
        '[data-testid="breadcrumb"] a',
        '[class*="breadcrumb" i] a',
    )
    for sel in selectores:
        els = page.query_selector_all(sel)
        if len(els) >= 2:
            nombres = []
            for e in els:
                txt = (e.inner_text() or "").strip()
                if txt and txt.lower() not in ("inicio", "home", "sodimac", "/"):
                    nombres.append(txt)
            if nombres:
                return nombres
    return []


# ---------------------------------------------------------------------------
# Helpers puros (sin estado / sin page)
# ---------------------------------------------------------------------------

def _parse_precio_clp(valor) -> float:
    """Convierte un precio en cualquier formato (str, int, float, list) a float CLP.

    Sodimac expone precios como strings con separador de miles (`"6.651"`),
    listas (`["6.651"]`) y a veces ints. Aceptamos todo sin romper.
    """
    if isinstance(valor, list):
        valor = valor[0] if valor else 0
    if isinstance(valor, str):
        try:
            return float(valor.replace(".", "").replace(",", "."))
        except ValueError:
            return 0.0
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def _rating_desde_item(item: dict) -> tuple:
    """Extrae (rating, review_count) de un item del catálogo.

    Sodimac suele exponer `rating` y `totalReviews` a nivel de item.
    Devolvemos None si no hay rating (producto sin reseñas).
    """
    rating_raw = item.get("rating") or item.get("ratingValue")
    reviews_raw = (item.get("totalReviews")
                   or item.get("reviewCount")
                   or item.get("reviews"))

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

    return _to_float(rating_raw), _to_int(reviews_raw)


def _jsonld_producto(page) -> dict:
    """Devuelve el primer JSON-LD con `@type: Product` de la página, o {}."""
    scripts = page.query_selector_all('script[type="application/ld+json"]')
    for s in scripts:
        raw = (s.inner_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for entry in items:
            if isinstance(entry, dict) and entry.get("@type") == "Product":
                return entry
            for sub in (entry.get("@graph", []) if isinstance(entry, dict) else []) or []:
                if isinstance(sub, dict) and sub.get("@type") == "Product":
                    return sub
    return {}


def _rating_desde_jsonld(jsonld: dict) -> tuple:
    """Extrae (rating, review_count) del aggregateRating del JSON-LD."""
    ar = jsonld.get("aggregateRating") if isinstance(jsonld, dict) else None
    if not isinstance(ar, dict):
        return None, None

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

    return _to_float(ar.get("ratingValue")), _to_int(ar.get("reviewCount"))


def _availability_desde_jsonld(jsonld: dict) -> str:
    """Extrae `offers.availability` → 'InStock' / 'OutOfStock' / ''."""
    if not isinstance(jsonld, dict):
        return ""
    offers = jsonld.get("offers")
    if isinstance(offers, list) and offers:
        offers = offers[0]
    if not isinstance(offers, dict):
        return ""
    av = offers.get("availability") or ""
    # Schema.org típicamente es "http://schema.org/InStock"; nos quedamos con lo último.
    return av.rsplit("/", 1)[-1] if isinstance(av, str) else ""
