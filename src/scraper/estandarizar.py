import json
import os
import re

# ==========================================
# 📚 DICCIONARIOS DE ESTANDARIZACIÓN CERCHA
# ==========================================
USO_MAP = {
    ("yeso-carton", "yeso carton", "volcanita", "drywall", "yesocarton"): "Yeso-cartón (Volcanita / Drywall)",
    ("metalcon", "perfil", "tabiqueria", "hojalateria", "metal"): "Metal (Metalcon / Perfiles)", # Quitamos "acero" de aquí
    ("aglomerado", "mdf", "melamina", "pino", "madera", "cholguan", "terciado"): "Madera (Aglomerado / MDF / Melamina)",
    ("techo", "techumbre", "zinc", "calamina", "v2", "v8", "tejado"): "Techumbre (Techo / Zinc / Calamina)",
    ("concreto", "hormigon", "ladrillo", "albañileria", "cemento"): "Concreto (Hormigón / Ladrillo)",
    ("fibrocemento", "internit", "pizarreño"): "Fibrocemento (Internit / Pizarreño)"
}

PUNTA_MAP = {
    ("autoperforante", "auto perforante", "punta broca", "autotaladrante"): "Autoperforante (Punta Broca)",
    ("punta espada", "punta fina", "punta clavo", "aguja"): "Punta Fina (Punta Espada / Clavo)",
    ("tirafondo", "tira fondo", "perno madera"): "Tirafondo (Madera Estructural)"
}

CABEZA_MAP = {
    ("phillips", "cruz", "cruz phillips"): "Phillips (Cruz)",
    ("plana", "avellanada", "de hundir"): "Plana (Avellanada)",
    ("lenteja", "fijadora", "extra plana"): "Lenteja (Fijadora)",
    ("hexagonal", "copa"): "Hexagonal (Copa)",
    ("trompeta", "bugle"): "Trompeta (Drywall)",
    ("redonda", "pan head", "pan"): "Redonda (Pan head)"
}

MATERIAL_MAP = {
    ("inox", "inoxidable", "acero inox"): "Acero Inoxidable (Inox)",
    ("zincado", "galvanizado", "zinc", "brillante"): "Acero Zincado (Galvanizado)",
    ("empavonado", "fosfatado", "negro", "pavonado"): "Acero Fosfatado (Negro / Empavonado)",
    ("bronceado", "bicromatado", "amarillo"): "Acero Bicromatado (Bronceado / Amarillo)",
    ("acero", "carbono"): "Acero Estándar" # Agregamos acero aquí, en su lugar correcto
}

def deducir_caracteristica(texto, diccionario_map, valor_defecto):
    """Busca en el texto las variaciones y devuelve el término estándar."""
    texto_limpio = texto.lower()
    for variaciones, termino_estandar in diccionario_map.items():
        for var in variaciones:
            if var in texto_limpio:
                return termino_estandar
    return valor_defecto

def estandarizar_medida_desde_titulo(titulo):
    texto = titulo.lower().replace('"', ' " ')
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

def estandarizar_para_ia():
    print("🧬 Iniciando Ingeniería de Características (Con Separación de Contextos)...")
    
    ruta_entrada = r'C:\Users\likan\Desktop\Motion Control\Proyectos\Programa Cercha\Comparador\motordelco-o\data\solo_tornillos.json'
    ruta_salida = r'C:\Users\likan\Desktop\Motion Control\Proyectos\Programa Cercha\Comparador\motordelco-o\data\tornillos_para_vectores.json'
    
    if not os.path.exists(ruta_entrada):
        print(f"❌ No se encontró el archivo: {ruta_entrada}")
        return

    with open(ruta_entrada, 'r', encoding='utf-8') as f:
        tornillos = json.load(f)

    tornillos_listos = []
    
    for prod in tornillos:
        titulo = prod.get('titulo', '').strip()
        specs = prod.get('especificaciones', {})
        
        # 🔥 EL ARREGLO: Separamos los textos para no contaminar la búsqueda 🔥
        texto_para_uso = f"{titulo} {specs.get('Uso', '')} {specs.get('Superficie de aplicación', '')} {specs.get('Recomendaciones', '')}"
        texto_para_material = f"{titulo} {specs.get('Material', '')}"
        texto_para_cabeza = f"{titulo} {specs.get('Tipo de cabeza', '')}"
        
        # 1. Aplicar la deducción inteligente en sus textos correspondientes
        uso_final = deducir_caracteristica(texto_para_uso, USO_MAP, "Construcción general")
        punta_final = deducir_caracteristica(titulo, PUNTA_MAP, "Punta Estándar")
        cabeza_final = deducir_caracteristica(texto_para_cabeza, CABEZA_MAP, "Cabeza Estándar")
        material_final = deducir_caracteristica(texto_para_material, MATERIAL_MAP, "Acero Estándar")
        
        # 2. Estandarizar la Medida 
        diametro = specs.get('Diámetro', '').strip()
        largo = specs.get('Largo', '').strip()
        medida_specs = f"{diametro} x {largo}".strip(' x')
        
        if not medida_specs or medida_specs == "x":
            medida_specs = estandarizar_medida_desde_titulo(titulo)
            if not medida_specs:
                medida_specs = "Medida no detectada"

        # 3. CREAR LA SÚPER ORACIÓN
        super_oracion = f"{titulo} {punta_final} {medida_specs} {uso_final} {cabeza_final} {material_final}"
        
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

    print(f"✅ ¡Catálogo estandarizado al 100%!")
    print(f"📁 Guardado en: {ruta_salida}\n")
    
    if tornillos_listos:
        print("💡 Ejemplo Súper Oración (SKU 110310551 corregido):")
        print("-" * 60)
        print(f"{tornillos_listos[0]['texto_embedding']}")
        print("-" * 60)

if __name__ == "__main__":
    estandarizar_para_ia()