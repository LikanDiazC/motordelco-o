import json
import re
import time
import math
import os
from playwright.sync_api import sync_playwright

def extraer_catalogo(busqueda="tornillos"):
    todos_los_productos = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        pagina_actual = 1
        paginas_totales = 1 
        
        while pagina_actual <= paginas_totales:
            print(f"\nNavegando a la página {pagina_actual} de {paginas_totales}...")
            
            if pagina_actual == 1:
                url = f"https://www.sodimac.cl/sodimac-cl/buscar?Ntt={busqueda}"
            else:
                url = f"https://www.sodimac.cl/sodimac-cl/buscar?Ntt={busqueda}&page={pagina_actual}&store=so_com"
            
            page.goto(url)
            time.sleep(3)
            
            html = page.content()
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
            
            if not match:
                print(f"No se encontró JSON en la página {pagina_actual}. Fin del catálogo.")
                break
                
            datos_json = json.loads(match.group(1))
            
            if pagina_actual == 1:
                paginacion = datos_json.get("props", {}).get("pageProps", {}).get("pagination", {})
                total_items = paginacion.get("count", 0)
                items_por_pagina = paginacion.get("perPage", 48)
                if total_items > 0 and items_por_pagina > 0:
                    paginas_totales = math.ceil(total_items / items_por_pagina)
                    print(f"¡Radar activado! {total_items} productos en {paginas_totales} páginas.")

            productos_encontrados = datos_json.get("props", {}).get("pageProps", {}).get("results", [])
            
            if len(productos_encontrados) == 0:
                print(f"Página {pagina_actual} vacía. Llegamos al final.")
                break
            
            print(f"-> Extrayendo {len(productos_encontrados)} productos...")
            
            for item in productos_encontrados:
                titulo = item.get("displayName", "Sin titulo")
                sku = item.get("skuId", "Sin SKU")
                marca = item.get("brand", "Sin marca")
                producto_id = item.get("productId", sku)
                
                precios = item.get("prices", [])
                precio = precios[0].get("price", ["0"])[0] if precios else "0"

                titulo_url = titulo.replace(" ", "-").replace("/", "-")
                url_exacta = f"https://www.sodimac.cl/sodimac-cl/articulo/{producto_id}/{titulo_url}/{sku}"

                todos_los_productos.append({
                    "sku": sku,
                    "marca": marca,
                    "titulo": titulo,
                    "precio_clp": float(precio.replace(".", "")),
                    "url": url_exacta
                })
            
            pagina_actual += 1

        browser.close()

        os.makedirs('data', exist_ok=True)
        with open('data/tornillos_catalogo_completo.json', 'w', encoding='utf-8') as f:
            json.dump(todos_los_productos, f, ensure_ascii=False, indent=4)
            
        print(f"\n¡Catálogo extraído! {len(todos_los_productos)} productos guardados.")

if __name__ == "__main__":
    extraer_catalogo(busqueda="tornillos")