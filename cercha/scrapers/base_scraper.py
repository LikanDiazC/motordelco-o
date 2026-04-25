"""Clase base abstracta para scrapers. Toda la lógica común de Playwright vive aquí."""

import json
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from playwright.sync_api import sync_playwright

from cercha.config import SCRAPE_DELAY_SECONDS, SCRAPE_CHECKPOINT_EVERY, PAGE_LOAD_TIMEOUT_MS


# Cada cuántos productos reiniciamos el browser completo. Chromium acumula
# estado (DOM zombies, caches, sockets) que crece linealmente con el número
# de goto()s; reiniciar periódicamente evita que se degrade hasta colgarse.
_PRODUCTOS_POR_SESION = 50

# Watchdog: si extraer_ficha() no retorna en este tiempo, matamos el
# proceso de Chromium por la fuerza para forzar un reinicio de sesión.
_WATCHDOG_SEGUNDOS = 90


# ---------------------------------------------------------------------------
# Helpers de estabilidad del browser
# ---------------------------------------------------------------------------

# Argumentos de lanzamiento de Chromium que reducen crashes en headless:
#   --disable-gpu            evita crashes de renderizado en servidores sin GPU
#   --no-sandbox             necesario en Windows/CI sin acceso a sandboxing
#   --disable-dev-shm-usage  evita que /dev/shm se llene en Linux (OOM)
#   --disable-setuid-sandbox idem en contenedores
_BROWSER_ARGS = [
    "--disable-gpu",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-setuid-sandbox",
]

# Tipos de recurso que bloqueamos durante el scraping.
# Images y media son los causantes de OOM/crashes (descargas de MB por producto).
# Fonts y stylesheets se mantienen para no romper la hidratación JS de Sodimac.
_TIPOS_A_BLOQUEAR = {"image", "media"}


def _crear_pagina(browser, bloquear_recursos: bool = False):
    """Crea una página nueva con timeout por defecto ajustado.

    Si `bloquear_recursos` es True, intercepta y aborta peticiones de
    imágenes, vídeos, fuentes y hojas de estilo para reducir uso de memoria.
    """
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(PAGE_LOAD_TIMEOUT_MS)

    if bloquear_recursos:
        def _bloquear(route):
            if route.request.resource_type in _TIPOS_A_BLOQUEAR:
                route.abort()
            else:
                route.continue_()
        page.route("**/*", _bloquear)

    return page


def es_error_fatal(exc: Exception) -> bool:
    """True si la excepción indica que la página/browser crasheó o fue cerrado.

    Exportado para que los `extraer_ficha` de las subclases puedan re-lanzar
    errores de crash en lugar de silenciarlos (necesario para la recuperación).
    """
    msg = str(exc).lower()
    return any(k in msg for k in (
        "page crashed",
        "target closed",
        "browser has been closed",
        "connection closed",
        "session closed",
    ))


# ---------------------------------------------------------------------------
# Clases base
# ---------------------------------------------------------------------------

class BaseCatalogScraper(ABC):
    """Scraper de catálogo paginado. Soporta uno o múltiples términos de búsqueda."""

    def __init__(self, busquedas: "str | list[str]", ruta_salida: Path):
        self.busquedas = [busquedas] if isinstance(busquedas, str) else busquedas
        self.busqueda = self.busquedas[0]  # compatibilidad con construir_url()
        self.ruta_salida = ruta_salida

    @abstractmethod
    def construir_url(self, pagina: int) -> str:
        """Construye la URL para una página específica del catálogo."""

    @abstractmethod
    def extraer_paginacion(self, datos_json: dict) -> tuple:
        """Extrae (total_items, items_por_pagina) del JSON de la primera página."""

    @abstractmethod
    def extraer_productos(self, datos_json: dict) -> list:
        """Extrae la lista cruda de productos del JSON de una página."""

    @abstractmethod
    def parsear_producto(self, item: dict) -> dict:
        """Convierte un item crudo del JSON al formato estándar de Cercha."""

    def ejecutar(self):
        """Ejecuta el scraping para todos los términos de búsqueda, deduplicando por SKU."""
        import math
        todos: dict[str, dict] = {}  # sku → producto (dedup automático)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=_BROWSER_ARGS)
            # Catálogo: bloqueamos imágenes/fuentes; sólo necesitamos __NEXT_DATA__ (SSR)
            page = _crear_pagina(browser, bloquear_recursos=True)

            for termino in self.busquedas:
                self.busqueda = termino
                print(f"\n  Buscando: '{termino}'")
                pagina_actual = 1
                paginas_totales = 1

                while pagina_actual <= paginas_totales:
                    print(f"    Pagina {pagina_actual}/{paginas_totales}...")
                    url = self.construir_url(pagina_actual)
                    try:
                        # domcontentloaded: el HTML/JSON SSR ya está disponible;
                        # no esperar que todos los recursos externos terminen de cargar.
                        page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS,
                                  wait_until="domcontentloaded")
                    except Exception as e:
                        print(f"    Error al cargar página {pagina_actual}: {e}")
                        if es_error_fatal(e):
                            page = _crear_pagina(browser, bloquear_recursos=True)
                        pagina_actual += 1
                        continue

                    time.sleep(SCRAPE_DELAY_SECONDS)

                    datos_json = self._extraer_next_data(page)
                    if not datos_json:
                        print(f"    Sin datos JSON en pagina {pagina_actual}. Fin.")
                        break

                    if pagina_actual == 1:
                        total, per_page = self.extraer_paginacion(datos_json)
                        if total > 0 and per_page > 0:
                            paginas_totales = math.ceil(total / per_page)
                            print(f"    {total} productos en {paginas_totales} paginas.")

                    items = self.extraer_productos(datos_json)
                    if not items:
                        break

                    for item in items:
                        prod = self.parsear_producto(item)
                        if prod:
                            todos[prod['sku']] = prod  # dedup por SKU

                    pagina_actual += 1

            browser.close()

        resultado = list(todos.values())
        self.ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ruta_salida, 'w', encoding='utf-8') as f:
            json.dump(resultado, f, ensure_ascii=False, indent=4)

        print(f"\n  {len(resultado)} productos únicos guardados en {self.ruta_salida}")
        return resultado

    def _extraer_next_data(self, page) -> dict:
        """Extrae el JSON de __NEXT_DATA__ embebido en el HTML."""
        import re
        try:
            html = page.content()
        except Exception:
            return {}
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html, re.DOTALL
        )
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return {}


class BaseDeepScraper(ABC):
    """Scraper de fichas técnicas individuales, con checkpoint y recuperación de crashes."""

    def __init__(self, ruta_entrada: Path, ruta_salida: Path):
        self.ruta_entrada = ruta_entrada
        self.ruta_salida = ruta_salida

    @abstractmethod
    def extraer_ficha(self, page, producto: dict) -> dict:
        """Extrae datos profundos de la página de un producto individual.

        IMPORTANTE: si `es_error_fatal(exc)` devuelve True, la excepción debe
        re-lanzarse (raise) en lugar de silenciarse, para que el loop de
        recuperación de `ejecutar()` pueda crear una nueva página.
        """

    def ejecutar(self):
        """Procesa todos los productos con checkpoints, watchdog y reinicio periódico.

        Estrategia de robustez tras haberse quedado pegado en producto 480:
          1. Reiniciamos el browser cada `_PRODUCTOS_POR_SESION` productos para
             evitar acumulación de estado en Chromium.
          2. Watchdog por producto: si `extraer_ficha` no retorna en
             `_WATCHDOG_SEGUNDOS`, matamos Chromium y reiniciamos sesión.
          3. Logs de tiempo por producto para identificar cuellos de botella.
        """
        with open(self.ruta_entrada, 'r', encoding='utf-8') as f:
            productos = json.load(f)

        # Cargar progreso previo
        procesados = []
        skus_hechos = set()
        if self.ruta_salida.exists():
            with open(self.ruta_salida, 'r', encoding='utf-8') as f:
                procesados = json.load(f)
                skus_hechos = {p['sku'] for p in procesados}

        restantes = [p for p in productos if p['sku'] not in skus_hechos]
        if not restantes:
            print("  Catalogo ya 100% enriquecido.")
            return procesados

        print(f"  Faltan {len(restantes)} productos por enriquecer.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=_BROWSER_ARGS)
            page = _crear_pagina(browser, bloquear_recursos=True)
            productos_en_sesion = 0

            for i, prod in enumerate(restantes):
                # --- Reinicio proactivo del browser ---
                # Después de N productos cerramos y relanzamos Chromium para
                # evitar la degradación progresiva que nos colgó en #480.
                if productos_en_sesion >= _PRODUCTOS_POR_SESION:
                    print(f"    ↻ Reinicio proactivo de browser tras "
                          f"{productos_en_sesion} productos en sesión.")
                    try:
                        page.close()
                    except Exception:
                        pass
                    try:
                        browser.close()
                    except Exception:
                        pass
                    browser = p.chromium.launch(headless=True, args=_BROWSER_ARGS)
                    page = _crear_pagina(browser, bloquear_recursos=True)
                    productos_en_sesion = 0

                t_inicio = time.time()
                print(f"  [{i+1}/{len(restantes)}] {prod['titulo'][:60]}")

                ficha = {}
                for intento in range(2):  # hasta 1 reintento tras crash
                    # --- Watchdog ---
                    # Si extraer_ficha no retorna en _WATCHDOG_SEGUNDOS,
                    # matamos el proceso Chromium (lo cual hará que la llamada
                    # lance una excepción fatal, que capturamos abajo).
                    watchdog_disparado = {"fired": False}

                    def _matar_browser():
                        watchdog_disparado["fired"] = True
                        try:
                            proc = getattr(browser, "process", None)
                            if proc is not None:
                                proc.kill()
                        except Exception:
                            pass

                    timer = threading.Timer(_WATCHDOG_SEGUNDOS, _matar_browser)
                    timer.daemon = True
                    timer.start()

                    try:
                        ficha = self.extraer_ficha(page, prod)
                        timer.cancel()
                        break  # éxito
                    except Exception as e:
                        timer.cancel()

                        hubo_watchdog = watchdog_disparado["fired"]
                        es_fatal = es_error_fatal(e) or hubo_watchdog

                        if intento == 0 and es_fatal:
                            motivo = "watchdog" if hubo_watchdog else e.__class__.__name__
                            print(f"    ⚠ Crash/timeout ({motivo}) tras "
                                  f"{time.time() - t_inicio:.1f}s, "
                                  f"reiniciando browser completo...")
                            try:
                                page.close()
                            except Exception:
                                pass
                            try:
                                browser.close()
                            except Exception:
                                pass
                            # Relanzamos browser entero (no sólo la página):
                            # si hubo watchdog, el proceso Chromium está muerto.
                            browser = p.chromium.launch(headless=True, args=_BROWSER_ARGS)
                            page = _crear_pagina(browser, bloquear_recursos=True)
                            productos_en_sesion = 0
                            # continuar el bucle for → intento 1
                        else:
                            print(f"    ✗ Error ignorado (intento {intento+1}): {e}")
                            ficha = {}
                            break

                elapsed = time.time() - t_inicio
                if elapsed > 15:
                    print(f"    ⏱ Lento: {elapsed:.1f}s")

                producto_final = {**prod, **ficha}
                procesados.append(producto_final)
                skus_hechos.add(prod['sku'])
                productos_en_sesion += 1

                # Checkpoint cada N productos
                if len(skus_hechos) % SCRAPE_CHECKPOINT_EVERY == 0:
                    self._guardar(procesados)
                    print("    Checkpoint guardado.")

                time.sleep(SCRAPE_DELAY_SECONDS)

            try:
                browser.close()
            except Exception:
                pass

        self._guardar(procesados)
        print(f"  Scraping profundo completado: {len(procesados)} productos.")
        return procesados

    def _guardar(self, data):
        self.ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ruta_salida, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
