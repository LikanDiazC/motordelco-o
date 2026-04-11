import json
import os
import re

# ==========================================
# 📚 DICCIONARIOS DE ESTANDARIZACIÓN CERCHA
# ==========================================
USO_MAP = {
    ("yeso-carton", "yeso carton", "volcanita", "vulcanita", "drywall", "yesocarton", "volc"): "Yeso-cartón (Volcanita / Drywall)",
    ("metalcon", "perfil", "tabiqueria", "hojalateria", "metal"): "Metal (Metalcon / Perfiles)",
    ("aglomerado", "mdf", "melamina", "pino", "madera", "cholguan", "terciado"): "Madera (Aglomerado / MDF / Melamina)",
    ("techo", "techumbre", "calamina", "v2", "v8", "tejado", "cubierta"): "Techumbre (Techo / Zinc / Calamina)",
    ("concreto", "hormigon", "ladrillo", "albañileria", "cemento"): "Concreto (Hormigón / Ladrillo)",
    ("fibrocemento", "internit", "pizarreño"): "Fibrocemento (Internit / Pizarreño)"
}

PUNTA_MAP = {
    ("autoperforante", "auto perforante", "punta broca", "autotaladrante"): "Autoperforante (Punta Broca)",
    ("punta espada", "punta fina", "punta clavo", "aguja"): "Punta Fina (Punta Espada / Clavo)",
    ("tirafondo", "tira fondo", "perno madera"): "Tirafondo (Madera Estructural)"
}

CABEZA_MAP = {
    ("phillips", "cruz", "cruz phillips", "ph2"): "Phillips (Cruz)",
    ("plana", "avellanada", "de hundir"): "Plana (Avellanada)",
    ("lenteja", "fijadora", "extra plana", "truss"): "Lenteja (Fijadora)",
    ("hexagonal", "copa"): "Hexagonal (Copa)",
    ("trompeta", "bugle", "crs"): "Trompeta (Drywall)",
    ("redonda", "pan head", "pan"): "Redonda (Pan head)"
}

MATERIAL_MAP = {
    ("inox", "inoxidable", "acero inox"): "Acero Inoxidable (Inox)",
    ("zincado", "galvanizado", "zinc", "brillante", "zc", "zbr", "zb"): "Acero Zincado (Galvanizado)",
    ("empavonado", "fosfatado", "negro", "pavonado"): "Acero Fosfatado (Negro / Empavonado)",
    ("bronceado", "bicromatado", "amarillo", "iridiscente"): "Acero Bicromatado (Bronceado / Amarillo)",
    ("acero", "carbono"): "Acero Estándar"
}

def deducir_caracteristica(texto, diccionario_map, valor_defecto):
    """Busca en el texto las variaciones y devuelve el término estándar."""
    texto_limpio = texto.lower()
    for variaciones, termino_estandar in diccionario_map.items():
        for var in variaciones:
            # Para abreviaciones cortas de Easy como 'zc', exigimos que sea una palabra completa
            if var in ['zc', 'zb', 'zbr', 'crs']:
                if re.search(rf'\b{var}\b', texto_limpio):
                    return termino_estandar
            elif var in texto_limpio:
                return termino_estandar
    return valor_defecto

def estandarizar_medida_desde_titulo(titulo):
    # Reemplazamos las dos comillas simples de Easy por una doble, y luego espaciamos
    texto = titulo.lower().replace("''", '"').replace('"', ' " ')
    
    patron_axb = r'(\d+(?:/\d+)?)\s*x\s*(\d+[ -]\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)(?:\s*(pulgada|mm|"))?'
    match_axb = re.search(patron_axb, texto)
    if match_axb: return f"{match_axb.group(1)}x{match_axb.group(2)}\"".replace(' ', '')
        
    patron_sodimac = r'(\d+(?:-\d+/\d+|/\d+)?)\s*"\s*(\d+(?:\.\d+)?)\s*mm'
    match_sodimac = re.search(patron_sodimac, texto)
    if match_sodimac: return f"{match_sodimac.group(1)}\" y {match_sodimac.group(2)}mm"
        
    patron_pulg = r'(\d+[ -]\d+/\d+|\d+/\d+)(?:\s*(pulgada|"))'
    match_pulg = re.search(patron_pulg, texto)
    if match_pulg: return f"{match_pulg.group(1)}\""
        
    patron_mm = r'(\d+(?:\.\d+)?)\s*mm'
    match_mm = re.search(patron_mm, texto)
    if match_mm: return f"{match_mm.group(1)}mm"
    return ""

def estandarizar_easy():
    print("🧬 Iniciando Ingeniería de Características (Motor Easy)...")
    
    ruta_entrada = 'C:\\Users\\likan\\Desktop\\Motion Control\\Proyectos\\Programa Cercha\\Comparador\\motordelco-o\\data2\\tornillos_easy_profundo.json'
    ruta_salida = 'C:\\Users\\likan\\Desktop\\Motion Control\\Proyectos\\Programa Cercha\\Comparador\\motordelco-o\\data2\\tornillos_easy_vectores.json'
    
    if not os.path.exists(ruta_entrada):
        print(f"❌ Error: No se encontró el archivo {ruta_entrada}")
        return

    with open(ruta_entrada, 'r', encoding='utf-8') as f:
        tornillos = json.load(f)

    tornillos_listos = []
    
    for prod in tornillos:
        titulo = prod.get('titulo', '').strip()
        
        # 1. Filtro Estricto (Protección anti-basura)
        titulo_lower = titulo.lower()
        if not any(p in titulo_lower for p in ['tornillo', 'tirafondo', 'soberbio', 'autoperforante', 'roscalata']):
            continue # Ignoramos repuestos de inodoros o sierras que hayan entrado por error
            
        specs = prod.get('especificaciones', {})
        desc_html = prod.get('descripcion_completa', '')
        # Le quitamos todo el código HTML feo a la descripción para que la IA la lea como texto plano
        desc_limpia = re.sub(r'<[^>]+>', ' ', desc_html).replace('&quot;', '"')
        
        # 2. Separación de contextos para evitar "El Efecto Dominó del Acero"
        texto_para_uso = f"{titulo} {specs.get('Uso', '')} {specs.get('Uso Recomendado', '')} {desc_limpia}"
        texto_para_material = f"{titulo} {specs.get('Material', '')} {specs.get('Terminación', '')} {desc_limpia}"
        texto_para_cabeza = f"{titulo} {specs.get('Tipo de cabeza', '')} {desc_limpia}"
        texto_para_punta = f"{titulo} {specs.get('Modelo', '')} {desc_limpia}"
        
        uso_final = deducir_caracteristica(texto_para_uso, USO_MAP, "Construcción general")
        punta_final = deducir_caracteristica(texto_para_punta, PUNTA_MAP, "Punta Estándar")
        cabeza_final = deducir_caracteristica(texto_para_cabeza, CABEZA_MAP, "Cabeza Estándar")
        material_final = deducir_caracteristica(texto_para_material, MATERIAL_MAP, "Acero Estándar")
        
        # 3. Rescate de medidas 
        # Easy a veces escribe "3.5 Milimetros", lo arreglamos a "3.5mm"
        # 3. Rescate de medidas 
        diametro = str(specs.get('Diámetro', '')).strip().replace(' Milimetros', 'mm')
        largo = str(specs.get('Largo', '')).strip()
        
        # Si Easy no llenó bien la tabla, lo rescatamos matemáticamente del título
        if not diametro or not largo:
            medida_specs = estandarizar_medida_desde_titulo(titulo)
            if not medida_specs:
                medida_specs = "Medida no detectada"
        else:
            medida_specs = f"{diametro} x {largo}"
        # 4. CREAR LA SÚPER ORACIÓN (Densidad alta de palabras clave)
        super_oracion = f"{titulo} - Uso: {uso_final} - Cabeza: {cabeza_final}"

        prod_limpio = {
            "sku": prod.get('sku', 'N/A'),
            "titulo": titulo,
            "precio_clp": prod.get('precio_clp', 0),
            "url": prod.get('url', ''),
            "medida_extraida": medida_specs,
            "texto_embedding": super_oracion
        }
        tornillos_listos.append(prod_limpio)

    with open(ruta_salida, 'w', encoding='utf-8') as f:
        json.dump(tornillos_listos, f, indent=4, ensure_ascii=False)

    print(f"✅ ¡Catálogo Easy estandarizado y purificado al 100%!")
    print(f" - Productos totales extraídos de Easy: {len(tornillos)}")
    print(f" - Tornillos reales que pasaron el filtro: {len(tornillos_listos)}")
    print(f" - Basura eliminada: {len(tornillos) - len(tornillos_listos)}")
    print(f"📁 Guardado en: {ruta_salida}\n")

if __name__ == "__main__":
    estandarizar_easy()