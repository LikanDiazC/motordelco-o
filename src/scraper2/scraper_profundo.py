import json
import re
import time
import os
from playwright.sync_api import sync_playwright

def extraccion_profunda_easy():
    print("🤿 Iniciando Buceo Profundo en el catálogo de Easy...")
    
    ruta_entrada = 'C:\\Users\\likan\\Desktop\\Motion Control\\Proyectos\\Programa Cercha\\Comparador\\motordelco-o\\data2\\tornillos_easy_crudo.json'
    ruta_salida = 'C:\\Users\\likan\\Desktop\\Motion Control\\Proyectos\\Programa Cercha\\Comparador\\motordelco-o\\data2\\tornillos_easy_profundo.json'
    
    if not os.path.exists(ruta_entrada):
        print(f"❌ Error: Primero debes correr el scraper_easy.py. No encuentro {ruta_entrada}")
        return

    with open(ruta_entrada, 'r', encoding='utf-8') as f:
        productos = json.load(f)

    # Si quieres probar rápido, cambia esto a productos[:5] para testear con los primeros 5
    productos_a_procesar = productos 
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for i, prod in enumerate(productos_a_procesar):
            url = prod['url']
            print(f"[{i+1}/{len(productos_a_procesar)}] Extrayendo: {prod['titulo']}")
            
            try:
                page.goto(url, timeout=60000)
                time.sleep(2) # Pausa cortita para no saturar al servidor de Easy
                
                html = page.content()
                match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
                
                if match:
                    datos_json = json.loads(match.group(1))
                    
                    # 🗺️ EL MAPA DEL TESORO QUE DESCUBRISTE
                    # En la página de producto, Easy guarda los datos dentro de dehydratedState -> queries
                    queries = datos_json.get("props", {}).get("pageProps", {}).get("dehydratedState", {}).get("queries", [])
                    
                    data_producto = {}
                    for q in queries:
                        state_data = q.get("state", {}).get("data", {})
                        # Buscamos el bloque que tiene la llave 'specifications' real
                        if "specifications" in state_data:
                            data_producto = state_data
                            break
                    
                    # Extraemos la descripción completa
                    prod['descripcion_completa'] = data_producto.get("description", "")
                    
                    # Extraemos las especificaciones ricas (Material, Diámetro, etc)
                    specs_crudas = data_producto.get("specifications", {})
                    specs_limpias = {}
                    
                    # Easy guarda los valores como listas ej: "Material": ["Acero"]
                    for clave, valor_lista in specs_crudas.items():
                        if isinstance(valor_lista, list) and len(valor_lista) > 0:
                            specs_limpias[clave] = valor_lista[0]
                        else:
                            specs_limpias[clave] = valor_lista
                            
                    # Actualizamos las especificaciones del producto con las nuevas y mejores
                    prod['especificaciones'] = specs_limpias
                else:
                    print("  -> ⚠️ No se encontró la data JSON en esta página.")
                    prod['descripcion_completa'] = ""
            
            except Exception as e:
                print(f"  -> ❌ Error cargando página: {e}")
                prod['descripcion_completa'] = ""

        browser.close()

    # Guardamos el archivo final enriquecido
    with open(ruta_salida, 'w', encoding='utf-8') as f:
        json.dump(productos_a_procesar, f, ensure_ascii=False, indent=4)
        
    print(f"\n✅ ¡Misión Cumplida! Catálogo profundo guardado en {ruta_salida}")

if __name__ == "__main__":
    extraccion_profunda_easy()