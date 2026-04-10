import json
import time
import os
from playwright.sync_api import sync_playwright

def extraer_ficha_tecnica(page, url_producto):
    datos_extraidos = {
        "descripcion": "Sin descripción",
        "especificaciones": {}
    }
    try:
        page.goto(url_producto, timeout=20000)
        try:
            page.wait_for_selector("table.specification-table", timeout=4000)
        except:
            return datos_extraidos

        desc_elemento = page.query_selector(".fb-product-information-tab__copy")
        if desc_elemento:
            datos_extraidos["descripcion"] = desc_elemento.inner_text().replace('\n', ' ').strip()
            
        filas = page.query_selector_all("table.specification-table tr")
        for fila in filas:
            nombre = fila.query_selector(".property-name")
            valor = fila.query_selector(".property-value")
            if nombre and valor:
                datos_extraidos["especificaciones"][nombre.inner_text().strip()] = valor.inner_text().strip()
                
    except Exception as e:
        print(f"  [!] Error al cargar: {url_producto}")
        
    return datos_extraidos

def procesar_catalogo():
    archivo_entrada = 'data/tornillos_catalogo_completo.json'
    archivo_salida = 'data/tornillos_catalogo_profundo.json'
    
    with open(archivo_entrada, 'r', encoding='utf-8') as f:
        productos_base = json.load(f)
        
    productos_enriquecidos = []
    skus_procesados = set()
    
    if os.path.exists(archivo_salida):
        with open(archivo_salida, 'r', encoding='utf-8') as f:
            productos_enriquecidos = json.load(f)
            skus_procesados = {p['sku'] for p in productos_enriquecidos}
            
    restantes = len(productos_base) - len(skus_procesados)
    if restantes == 0:
        print("Catálogo ya 100% enriquecido.")
        return

    print(f"Retomando... Faltan {restantes} productos por enriquecer.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        page = browser.new_page()
        
        for i, producto in enumerate(productos_base):
            if producto['sku'] in skus_procesados:
                continue
                
            print(f"[{i+1}/{len(productos_base)}] Extrayendo datos de: {producto['url']}")
            info_profunda = extraer_ficha_tecnica(page, producto['url'])
            
            producto_final = {**producto, **info_profunda}
            productos_enriquecidos.append(producto_final)
            skus_procesados.add(producto['sku'])
            
            if len(skus_procesados) % 10 == 0:
                with open(archivo_salida, 'w', encoding='utf-8') as f:
                    json.dump(productos_enriquecidos, f, ensure_ascii=False, indent=4)
                print("  💾 Checkpoint guardado.")
                
            time.sleep(2)
            
        browser.close()
        
    with open(archivo_salida, 'w', encoding='utf-8') as f:
        json.dump(productos_enriquecidos, f, ensure_ascii=False, indent=4)
    print("\n🏁 Proceso de Deep Scraping completado.")

if __name__ == "__main__":
    procesar_catalogo()