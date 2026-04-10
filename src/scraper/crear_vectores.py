import json
import pickle
import os
import shutil
from sentence_transformers import SentenceTransformer

def limpiar_cache_local():
    ruta_cache = './modelo_temporal'
    if os.path.exists(ruta_cache):
        print(f"Limpiando caché antigua en {ruta_cache}...")
        try:
            shutil.rmtree(ruta_cache)
        except Exception as e:
            pass

def compilar_cerebro():
    print("Cargando el catálogo normalizado...")
    ruta_json = 'data/tornillos_normalizados_completo.json'
        
    try:
        with open(ruta_json, 'r', encoding='utf-8') as f:
            productos = json.load(f)
    except FileNotFoundError:
        print(f"❌ ERROR: No encuentro el archivo JSON en {ruta_json}")
        return
        
    textos_para_ia = []
    for p in productos:
        material = p.get('especificaciones', {}).get('Material', '')
        cabeza = p.get('especificaciones', {}).get('Tipo de cabeza', '')
        titulo = p.get('titulo_normalizado', p.get('titulo', ''))
        texto_enriquecido = f"{titulo} Material: {material} Cabeza: {cabeza}"
        textos_para_ia.append(texto_enriquecido)
    
    limpiar_cache_local()
    
    print("Cargando la Red Neuronal (MiniLM)...")
    try:
        modelo = SentenceTransformer(
            'paraphrase-multilingual-MiniLM-L12-v2',
            cache_folder='./modelo_temporal'
        )
    except Exception as e:
        print("\n❌ Error cargando modelo. Revisa tu conexión o Token de HuggingFace.")
        return
    
    print(f"Transformando {len(textos_para_ia)} productos a vectores 3D...")
    vectores = modelo.encode(textos_para_ia, show_progress_bar=True)
    
    base_de_conocimiento = {
        "productos": productos,
        "vectores": vectores
    }
    
    os.makedirs('data', exist_ok=True)
    
    print("Guardando el cerebro vectorial (.pkl)...")
    with open('data/cerebro_sodimac.pkl', 'wb') as f:
        pickle.dump(base_de_conocimiento, f)
        
    print("¡Cerebro creado exitosamente en data/cerebro_sodimac.pkl! 🧠")

if __name__ == "__main__":
    compilar_cerebro()