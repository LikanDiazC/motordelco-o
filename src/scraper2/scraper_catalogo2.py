import json
import re
import time
import math
import os
from playwright.sync_api import sync_playwright

def extraer_catalogo_easy(busqueda="tornillo"):
    print(f"🕵️‍♂️ Iniciando Infiltración en Easy.cl buscando: '{busqueda}'...")
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
                url = f"https://www.easy.cl/search/{busqueda}"
            else:
                url = f"https://www.easy.cl/search/{busqueda}?page={pagina_actual}"
            
            page.goto(url)
            time.sleep(3) # Esperamos que cargue
            
            html = page.content()
            
            # Buscamos el cerebro de Next.js
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
            
            if not match:
                print(f"❌ No se encontró JSON en la página {pagina_actual}. Fin del catálogo.")
                break
                
            datos_json = json.loads(match.group(1))
            
            # 🔥 LA NUEVA RUTA SECRETA DE EASY
            server_response = datos_json.get("props", {}).get("pageProps", {}).get("serverProductsResponse", {})
            
            # Calcular páginas totales en la primera pasada
            if pagina_actual == 1:
                total_items = server_response.get("recordsFiltered", 0)
                if total_items > 0:
                    # Easy suele cargar 40 productos por página
                    paginas_totales = math.ceil(total_items / 40)
                    print(f"¡Radar activado! {total_items} productos totales. Calculando {paginas_totales} páginas.")

            productos_encontrados = server_response.get("productList", [])
            
            if len(productos_encontrados) == 0:
                print(f"Página {pagina_actual} vacía. Llegamos al final.")
                break
            
            print(f"-> Extrayendo {len(productos_encontrados)} productos...")
            
            for item in productos_encontrados:
                titulo = item.get("productName", "Sin titulo")
                sku = item.get("sku", "Sin SKU")
                marca = item.get("brand", "Sin marca")
                
                # Extraer Precio (Easy lo separa en normal y oferta)
                precios = item.get("prices", {})
                precio_normal = precios.get("normalPrice") or 0
                precio_oferta = precios.get("offerPrice") or precio_normal
                precio_final = precio_oferta if precio_oferta else precio_normal
                
                # Extraer URL exacta
                link_text = item.get("linkText", "")
                url_exacta = f"https://www.easy.cl/{link_text}"

                # 🧬 Extraer Especificaciones para la Inteligencia Artificial
                specs_crudas = item.get("specifications", [])
                especificaciones = {}
                for spec in specs_crudas:
                    nombre_spec = spec.get("name", "")
                    valores_spec = spec.get("values", [])
                    if nombre_spec and valores_spec:
                        # Tomamos el primer valor de la lista de especificaciones
                        especificaciones[nombre_spec] = valores_spec[0]

                todos_los_productos.append({
                    "sku": sku,
                    "marca": marca,
                    "titulo": titulo,
                    "precio_clp": float(precio_final),
                    "url": url_exacta,
                    "especificaciones": especificaciones
                })
            
            pagina_actual += 1

        browser.close()

        # Guardamos en la nueva carpeta data2
        os.makedirs('data2', exist_ok=True)
        ruta_salida = 'data2/tornillos_easy_crudo.json'
        
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            json.dump(todos_los_productos, f, ensure_ascii=False, indent=4)
            
        print(f"\n✅ ¡Catálogo Easy extraído con éxito!")
        print(f"📁 Se guardaron {len(todos_los_productos)} productos en: {ruta_salida}")

if __name__ == "__main__":
    # OJO: Easy busca mejor en singular "tornillo" que en plural
    extraer_catalogo_easy(busqueda="tornillo")