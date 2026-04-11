import json
import csv
import os

def generar_csv_auditoria():
    print("🔍 Analizando el catálogo para separar Tornillos de los Intrusos...")
    
    # Usamos el archivo profundo porque es el que tiene la data cruda más completa
    ruta_entrada = r'C:\Users\likan\Desktop\Motion Control\Proyectos\Programa Cercha\Comparador\motordelco-o\data\tornillos_catalogo_profundo.json'
    ruta_salida = r'C:\Users\likan\Desktop\Motion Control\Proyectos\Programa Cercha\Comparador\motordelco-o\data\auditoria_tornillos.csv'
    
    if not os.path.exists(ruta_entrada):
        print(f"❌ Error: No encuentro el archivo {ruta_entrada}")
        return

    with open(ruta_entrada, 'r', encoding='utf-8') as f:
        productos = json.load(f)

    # Preparar el archivo CSV (usamos 'utf-8-sig' para que Excel lea bien los tildes)
    with open(ruta_salida, 'w', newline='', encoding='utf-8-sig') as f_csv:
        # Usamos punto y coma (;) para que Excel en español separe bien las columnas
        writer = csv.writer(f_csv, delimiter=';')
        
        # Escribir los encabezados
        writer.writerow(['Clasificación', 'Título del Producto', 'Precio', 'URL'])
        
        tornillos_count = 0
        otros_count = 0

        for prod in productos:
            titulo = prod.get('titulo', '')
            precio = prod.get('precio_clp', 0)
            url = prod.get('url', 'N/A')
            
            # Regla simple: ¿Dice tornillo en el título?
            if "tornillo" in titulo.lower():
                clasificacion = "🟢 TORNILLO"
                tornillos_count += 1
            else:
                clasificacion = "🔴 INTRUSO (Otro)"
                otros_count += 1
                
            writer.writerow([clasificacion, titulo, precio, url])

    print("\n📊 RESULTADOS DE LA AUDITORÍA:")
    print(f" - Tornillos reales encontrados: {tornillos_count}")
    print(f" - Productos intrusos (No dicen tornillo): {otros_count}")
    print(f"\n✅ Archivo CSV generado con éxito en: {ruta_salida}")
    print("💡 Ve a tu carpeta 'data', dale doble clic a 'auditoria_tornillos.csv' y ábrelo en Excel.")

if __name__ == "__main__":
    generar_csv_auditoria()