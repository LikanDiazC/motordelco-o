"""Clase base abstracta para scrapers. Toda la lógica común de Playwright vive aquí."""

import json
import time
import os
from abc import ABC, abstractmethod
from pathlib import Path
from playwright.sync_api import sync_playwright

from cercha.config import SCRAPE_DELAY_SECONDS, SCRAPE_CHECKPOINT_EVERY, PAGE_LOAD_TIMEOUT_MS


class BaseCatalogScraper(ABC):
    """Scraper de catálogo paginado. Subclases definen cómo interpretar cada sitio."""

    def __init__(self, busqueda: str, ruta_salida: Path):
        self.busqueda = busqueda
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
        """Ejecuta el scraping completo con paginación automática."""
        todos = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context().new_page()

            pagina_actual = 1
            paginas_totales = 1

            while pagina_actual <= paginas_totales:
                print(f"  Pagina {pagina_actual}/{paginas_totales}...")
                url = self.construir_url(pagina_actual)
                page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS)
                time.sleep(SCRAPE_DELAY_SECONDS + 1)

                datos_json = self._extraer_next_data(page)
                if not datos_json:
                    print(f"  Sin datos JSON en pagina {pagina_actual}. Fin.")
                    break

                if pagina_actual == 1:
                    total, per_page = self.extraer_paginacion(datos_json)
                    if total > 0 and per_page > 0:
                        import math
                        paginas_totales = math.ceil(total / per_page)
                        print(f"  {total} productos en {paginas_totales} paginas.")

                items = self.extraer_productos(datos_json)
                if not items:
                    break

                for item in items:
                    prod = self.parsear_producto(item)
                    if prod:
                        todos.append(prod)

                pagina_actual += 1

            browser.close()

        self.ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ruta_salida, 'w', encoding='utf-8') as f:
            json.dump(todos, f, ensure_ascii=False, indent=4)

        print(f"  {len(todos)} productos guardados en {self.ruta_salida}")
        return todos

    def _extraer_next_data(self, page) -> dict:
        """Extrae el JSON de __NEXT_DATA__ embebido en el HTML."""
        import re
        html = page.content()
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html, re.DOTALL
        )
        if not match:
            return {}
        return json.loads(match.group(1))


class BaseDeepScraper(ABC):
    """Scraper de fichas técnicas individuales, con checkpoint."""

    def __init__(self, ruta_entrada: Path, ruta_salida: Path):
        self.ruta_entrada = ruta_entrada
        self.ruta_salida = ruta_salida

    @abstractmethod
    def extraer_ficha(self, page, producto: dict) -> dict:
        """Extrae datos profundos de la página de un producto individual."""

    def ejecutar(self):
        """Procesa todos los productos con checkpoints intermedios."""
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
            browser = p.chromium.launch(headless=True)
            page = browser.new_context().new_page()

            for i, prod in enumerate(restantes):
                print(f"  [{i+1}/{len(restantes)}] {prod['titulo'][:60]}")

                ficha = self.extraer_ficha(page, prod)
                producto_final = {**prod, **ficha}
                procesados.append(producto_final)
                skus_hechos.add(prod['sku'])

                # Checkpoint cada N productos
                if len(skus_hechos) % SCRAPE_CHECKPOINT_EVERY == 0:
                    self._guardar(procesados)
                    print("    Checkpoint guardado.")

                time.sleep(SCRAPE_DELAY_SECONDS)

            browser.close()

        self._guardar(procesados)
        print(f"  Scraping profundo completado: {len(procesados)} productos.")
        return procesados

    def _guardar(self, data):
        self.ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ruta_salida, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
