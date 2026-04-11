import os
import pickle
import numpy as np
import pandas as pd
import xgboost as xgb
from sentence_transformers import SentenceTransformer, util
import re

def limpiar_texto(texto):
    t = texto.lower()
    reemplazos = {'á':'a', 'é':'e', 'í':'i', 'ó':'o', 'ú':'u', 'yeso-carton':'drywall', 'yesocarton':'drywall', 'volcanita':'drywall'}
    for ori, des in reemplazos.items(): 
        t = t.replace(ori, des)
        
    # 🔥 EL PARCHE MÁGICO: Separar números de letras automáticamente
    # Convierte "70mm" en "70 mm" y "1/2pulgada" en "1/2 pulgada"
    t = re.sub(r'(\d)([a-z])', r'\1 \2', t)
    t = re.sub(r'([a-z])(\d)', r'\1 \2', t)
    
    return t.strip()

def extraer_numeros(texto):
    """Extrae todos los números (enteros o decimales) de un texto."""
    return set(re.findall(r'\d+(?:[.,]\d+)?', texto))

def iniciar_buscador():
    print("🚀 INICIANDO MOTOR CERCHA V2.5 (BÚSQUEDA HÍBRIDA)...")
    ruta_cerebro = r'C:\Users\likan\Desktop\Motion Control\Proyectos\Programa Cercha\Comparador\motordelco-o\data\cerebro_sodimac.pkl'

    if not os.path.exists(ruta_cerebro):
        print(f"❌ Error: No encontré {ruta_cerebro}")
        return

    with open(ruta_cerebro, 'rb') as f:
        datos_cerebro = pickle.load(f)
    
    vectores_sodimac = datos_cerebro['vectores']
    metadata_sodimac = datos_cerebro['metadata']

    modelo = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

    # Entrenamos a XGBoost
    np.random.seed(42)
    sim = np.random.uniform(0.1, 1.0, 1000)
    dim = np.random.choice([0, 1], 1000)
    match = ((sim >= 0.70) & (dim == 1)).astype(int)
    
    df_entrenamiento = pd.DataFrame({'similitud_texto': sim, 'misma_dimension': dim, 'es_match': match})
    juez_xgboost = xgb.XGBClassifier(eval_metric='logloss')
    juez_xgboost.fit(df_entrenamiento[['similitud_texto', 'misma_dimension']], df_entrenamiento['es_match'])

    print("\n✅ ¡SISTEMA LISTO! Escribe un producto.")

    while True:
        query_usuario = input("\n🔎 ¿Qué producto tienes?: ")
        if query_usuario.lower() in ['salir', 'exit', 'quit']: break

        query_limpia = limpiar_texto(query_usuario)
        numeros_usuario = extraer_numeros(query_limpia)
        
        # 1. Búsqueda Semántica Vectorial
        vector_query = modelo.encode([query_limpia], convert_to_tensor=True)
        similitudes = util.cos_sim(vector_query, vectores_sodimac)[0].tolist()
        
        # 2. Búsqueda Lexical (El Sistema Híbrido)
        # Si el título tiene palabras exactas de tu búsqueda, le regalamos puntos extra de similitud
        palabras_query = set(query_limpia.split())
        for idx in range(len(metadata_sodimac)):
            palabras_titulo = set(limpiar_texto(metadata_sodimac[idx]['titulo']).split())
            interseccion_palabras = palabras_query.intersection(palabras_titulo)
            
            # Bono: +5% de similitud por cada palabra exacta que coincida
            bono = len(interseccion_palabras) * 0.05 
            similitudes[idx] = min(1.0, similitudes[idx] + bono) # Tope máximo 100% (1.0)

        # Ordenar los resultados mejorados
        indices_top = np.argsort(similitudes)[::-1][:15]

        candidato_elegido = None
        porcentaje_similitud = 0
        dimension_coincide = 0

        # 3. El Embudo de Medidas Matemático
        for idx in indices_top:
            prod_sodimac = metadata_sodimac[idx]
            similitud_actual = similitudes[idx]
            
            # Extraemos los números del producto (título + medida extraída)
            numeros_prod = extraer_numeros(prod_sodimac['titulo'] + " " + prod_sodimac.get('medida_limpia', ''))

            hay_match_medida = False
            
            # Condición de éxito: Si TODOS los números que escribiste están en el producto
            if numeros_usuario and numeros_usuario.issubset(numeros_prod):
                hay_match_medida = True
            # Si no escribiste números, confiamos 100% en la IA
            elif not numeros_usuario:
                 hay_match_medida = True

            if hay_match_medida:
                candidato_elegido = prod_sodimac
                porcentaje_similitud = similitud_actual
                dimension_coincide = 1
                break

        # Backup si falla el embudo
        if not candidato_elegido:
            mejor_idx = indices_top[0]
            candidato_elegido = metadata_sodimac[mejor_idx]
            porcentaje_similitud = similitudes[mejor_idx]
            dimension_coincide = 0

        print("\n" + "-"*55)
        print("🎯 MEJOR CANDIDATO ENCONTRADO:")
        print(f"📌 Título  : {candidato_elegido['titulo']}")
        print(f"💵 Precio  : ${candidato_elegido['precio']}")
        print(f"📏 IA Match: {porcentaje_similitud*100:.2f}% (Semántico + Palabras Exactas)")

        prediccion = juez_xgboost.predict(pd.DataFrame({
            'similitud_texto': [porcentaje_similitud],
            'misma_dimension': [dimension_coincide]
        }))[0]

        print("\n👨‍⚖️ VEREDICTO DEL JUEZ XGBOOST:")
        if prediccion == 1:
            print("-> 🟢 ¡ES MATCH! (Aprobado automáticamente)")
        else:
            print("-> 🔴 RECHAZADO (Revisión manual requerida)")
        print("-"*55)

if __name__ == "__main__":
    iniciar_buscador()