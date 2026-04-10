import json
import re

def normalizar_titulo(titulo):
    texto = titulo.lower()
    reemplazos = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}
    for original, nuevo in reemplazos.items():
        texto = texto.replace(original, nuevo)
    
    sinonimos = {
        "yeso-carton": "drywall",
        "yesocarton": "drywall",
        "yeso carton": "drywall",
        "volcanita": "drywall",
        "\"": "pulgada"
    }
    for var, est in sinonimos.items():
        texto = texto.replace(var, est)
    return " ".join(texto.split())

def extraer_dimensiones(texto):
    dimensiones = []
    
    patron_axb = r'(\d+(?:/\d+)?)\s*x\s*(\d+[ -]\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)(?:\s*(pulgada|mm))?'
    match_axb = re.search(patron_axb, texto)
    
    if match_axb:
        medida = f"{match_axb.group(1)}x{match_axb.group(2)}"
        unidad = match_axb.group(3)
        if unidad == "pulgada" or "/" in match_axb.group(2): medida += "\""
        elif unidad == "mm": medida += "mm"
        dimensiones.append(medida)
    else:
        patron_pulg = r'(\d+[ -]\d+/\d+|\d+/\d+)(?:\s*pulgada)?|(\d+(?:\.\d+)?)\s*pulgada'
        match_pulg = re.search(patron_pulg, texto)
        if match_pulg:
            valor = match_pulg.group(1) if match_pulg.group(1) else match_pulg.group(2)
            dimensiones.append(f"{valor}\"")
            
    patron_mm = r'(\d+(?:\.\d+)?)\s*mm'
    match_mm = re.search(patron_mm, texto)
    if match_mm and not (match_axb and match_axb.group(3) == "mm"):
        dimensiones.append(f"{match_mm.group(1)}mm")
        
    return " y ".join(dimensiones) if dimensiones else "Dimensión no encontrada"

def procesar_normalizacion():
    archivo_entrada = 'data/tornillos_catalogo_profundo.json'
    archivo_salida = 'data/tornillos_normalizados_completo.json'
    
    with open(archivo_entrada, 'r', encoding='utf-8') as f:
        productos = json.load(f)
        
    productos_normalizados = []
    for prod in productos:
        titulo_limpio = normalizar_titulo(prod['titulo'])
        dimension = extraer_dimensiones(titulo_limpio)
        
        productos_normalizados.append({
            **prod, 
            "titulo_normalizado": titulo_limpio,
            "dimension_detectada": dimension
        })
        
    with open(archivo_salida, 'w', encoding='utf-8') as f:
        json.dump(productos_normalizados, f, ensure_ascii=False, indent=4)
        
    print(f"Limpieza terminada. {len(productos_normalizados)} productos normalizados.")

if __name__ == "__main__":
    procesar_normalizacion()