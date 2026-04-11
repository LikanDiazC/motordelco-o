import json
import os
import pickle
from sentence_transformers import SentenceTransformer

def crear_cerebro_vectorial():
    print("🧠 Iniciando la creación del NUEVO cerebro vectorial...")
    print("📥 Cargando modelo de IA (MiniLM)...")
    
    # Cargamos el modelo multilingüe
    modelo = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

    # Tus rutas absolutas
    ruta_entrada = r'C:\Users\likan\Desktop\Motion Control\Proyectos\Programa Cercha\Comparador\motordelco-o\data\tornillos_para_vectores.json'
    ruta_salida = r'C:\Users\likan\Desktop\Motion Control\Proyectos\Programa Cercha\Comparador\motordelco-o\data\cerebro_sodimac.pkl'

    if not os.path.exists(ruta_entrada):
        print(f"❌ Error: No se encontró el archivo {ruta_entrada}")
        return

    with open(ruta_entrada, 'r', encoding='utf-8') as f:
        tornillos = json.load(f)

    # Separamos los textos que la IA va a leer y guardamos la metadata útil
    textos_para_ia = []
    metadata_productos = []

    print(f"⚙️ Procesando {len(tornillos)} Súper Oraciones...")
    for prod in tornillos:
        # 🔥 EL CAMBIO MAESTRO: La IA ahora lee todo el contexto, no solo el nombre
        textos_para_ia.append(prod['texto_embedding'])
        
        # Guardamos la info extra para cuando hagamos la búsqueda en vivo
        metadata_productos.append({
            "sku": prod['sku'],
            "titulo": prod['titulo'],
            "precio": prod['precio_clp'],
            "url": prod['url'],
            "medida_limpia": prod['medida_extraida'] # La medida purificada para el Regex
        })

    print("🚀 Vectorizando... (Calculando coordenadas matemáticas en 384 dimensiones)")
    # Convertimos los textos en vectores
    vectores = modelo.encode(textos_para_ia, show_progress_bar=True)

    print("💾 Guardando la nueva memoria en el disco duro...")
    with open(ruta_salida, 'wb') as f:
        pickle.dump({'vectores': vectores, 'metadata': metadata_productos}, f)

    print(f"✅ ¡Éxito! El nuevo cerebro está listo y sobreescrito.")
    print(f"📁 Archivo actualizado: {ruta_salida}")

if __name__ == "__main__":
    crear_cerebro_vectorial()