import json
import os
import pickle
from sentence_transformers import SentenceTransformer

def crear_cerebro_vectorial_easy():
    print("🧠 Iniciando la creación del Cerebro Vectorial de EASY...")
    print("📥 Cargando modelo de IA (MiniLM)...")
    
    modelo = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

    ruta_entrada = 'C:\\Users\\likan\\Desktop\\Motion Control\\Proyectos\\Programa Cercha\\Comparador\\motordelco-o\\data2\\tornillos_easy_vectores.json'
    ruta_salida = 'C:\\Users\\likan\\Desktop\\Motion Control\\Proyectos\\Programa Cercha\\Comparador\\motordelco-o\\data2\\cerebro_easy.pkl'

    if not os.path.exists(ruta_entrada):
        print(f"❌ Error: No se encontró el archivo {ruta_entrada}")
        return

    with open(ruta_entrada, 'r', encoding='utf-8') as f:
        tornillos = json.load(f)

    textos_para_ia = []
    metadata_productos = []

    print(f"⚙️ Vectorizando {len(tornillos)} productos de Easy...")
    for prod in tornillos:
        textos_para_ia.append(prod['texto_embedding'])
        
        metadata_productos.append({
            "sku": prod['sku'],
            "titulo": prod['titulo'],
            "precio": prod['precio_clp'],
            "url": prod['url'],
            "medida_limpia": prod['medida_extraida']
        })

    # Convertimos a tensores
    vectores = modelo.encode(textos_para_ia, show_progress_bar=True)

    print("💾 Guardando la memoria de Easy en el disco duro...")
    with open(ruta_salida, 'wb') as f:
        pickle.dump({'vectores': vectores, 'metadata': metadata_productos}, f)

    print(f"✅ ¡Éxito! El cerebro de Easy está listo.")
    print(f"📁 Archivo creado: {ruta_salida}")

if __name__ == "__main__":
    crear_cerebro_vectorial_easy()