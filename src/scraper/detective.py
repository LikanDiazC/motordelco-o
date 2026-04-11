import json
import os

def auditar_perdidos():
    print("🕵️‍♂️ Iniciando auditoría: Buscando 'Tornillos Perdidos'...")
    
    # Rutas absolutas
    ruta_original = r'C:\Users\likan\Desktop\Motion Control\Proyectos\Programa Cercha\Comparador\motordelco-o\data\tornillos_catalogo_profundo.json'
    ruta_vectores = r'C:\Users\likan\Desktop\Motion Control\Proyectos\Programa Cercha\Comparador\motordelco-o\data\tornillos_para_vectores.json'
    
    with open(ruta_original, 'r', encoding='utf-8') as f:
        catalogo_crudo = json.load(f)
        
    with open(ruta_vectores, 'r', encoding='utf-8') as f:
        catalogo_vectores = json.load(f)

    # 1. Sacar la lista de los SKU que SÍ pasaron
    skus_salvados = {prod['sku'] for prod in catalogo_vectores}
    
    # 2. Palabras clave de ferretería que NO son "tornillo"
    palabras_sospechosas = ['perno', 'autoperforante', 'soberbio', 'tirafondo', 'roscalata', 'fijacion', 'fijador', 'anclaje']
    
    perdidos_importantes = []
    basura_confirmada = 0
    
    for prod in catalogo_crudo:
        sku = prod.get('sku')
        titulo = prod.get('titulo', '').lower()
        
        # Si el producto NO está en nuestra base de datos final
        if sku not in skus_salvados:
            es_sospechoso = False
            for palabra in palabras_sospechosas:
                if palabra in titulo:
                    es_sospechoso = True
                    break
            
            if es_sospechoso:
                perdidos_importantes.append(prod.get('titulo', ''))
            else:
                basura_confirmada += 1

    print("\n" + "="*50)
    print("📊 RESULTADOS DE LA AUDITORÍA:")
    print("="*50)
    print(f"✅ Tornillos en tu sistema actual : {len(skus_salvados)}")
    print(f"🗑️ Basura descartada correctamente: {basura_confirmada} (Candados, brocas, tuercas, etc)")
    print(f"⚠️ Posibles 'Tornillos' perdidos : {len(perdidos_importantes)}")
    
    if perdidos_importantes:
        print("\n👀 Muestra de lo que quedó fuera (Revisa si querías conservar esto):")
        for i, titulo in enumerate(perdidos_importantes[:15]): # Muestra los primeros 15
            print(f" - {titulo}")

if __name__ == "__main__":
    auditar_perdidos()