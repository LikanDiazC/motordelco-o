import os
import pickle
import numpy as np
import pandas as pd
import xgboost as xgb
from sentence_transformers import SentenceTransformer, util
import re

# ==========================================
# 1. FUNCIONES MATEMÁTICAS Y DE EXTRACCIÓN
# ==========================================
def limpiar_texto(texto):
    t = texto.lower()
    reemplazos = {'á':'a', 'é':'e', 'í':'i', 'ó':'o', 'ú':'u', 'yeso-carton':'drywall', 'yesocarton':'drywall', 'volcanita':'drywall', 'vulcanita':'drywall'}
    for ori, des in reemplazos.items(): t = t.replace(ori, des)
    t = re.sub(r'(\d)([a-z])', r'\1 \2', t) 
    t = re.sub(r'([a-z])(\d)', r'\1 \2', t)
    return t.strip()

def extraer_numeros(texto):
    return set(re.findall(r'\d+(?:[.,]\d+)?', texto))

def extraer_cantidad(titulo):
    """🕵️‍♂️ Busca cuántos tornillos vienen en el paquete leyendo el título."""
    texto = titulo.lower().replace('.', '')
    
    # Busca patrones como "100 unidades", "50 unds", "1000 un", "10 u"
    match = re.search(r'(\d+)\s*(?:unidades|unidad\(es\)|unidad|unds|und|un\b|u\b|pcs|pz|piezas|uds)', texto)
    if match:
        return max(1, int(match.group(1))) # max(1) evita que alguna vez se divida por cero
    
    # Busca patrones como "caja 100", "pack 50", "bolsa de 20"
    match_caja = re.search(r'(?:caja|pack|bolsa|balde)\s*(?:de\s*)?(\d+)', texto)
    if match_caja:
        return max(1, int(match_caja.group(1)))
        
    return 1 # Si no dice nada, asumimos que se vende por 1 unidad

def buscar_en_tienda(query_limpia, numeros_usuario, vector_query, metadata_tienda, vectores_tienda, juez_xgboost):
    similitudes = util.cos_sim(vector_query, vectores_tienda)[0].tolist()
    
    palabras_query = set(query_limpia.split())
    for idx in range(len(metadata_tienda)):
        palabras_titulo = set(limpiar_texto(metadata_tienda[idx]['titulo']).split())
        interseccion = palabras_query.intersection(palabras_titulo)
        bono = len(interseccion) * 0.05 
        similitudes[idx] = min(1.0, similitudes[idx] + bono)

    indices_top = np.argsort(similitudes)[::-1][:15]

    candidato_elegido = None
    porcentaje_similitud = 0
    dimension_coincide = 0

    for idx in indices_top:
        prod = metadata_tienda[idx]
        similitud_actual = similitudes[idx]
        
        texto_medidas = prod['titulo'] + " " + prod.get('medida_limpia', '') + " " + prod.get('medida_extraida', '')
        numeros_prod = extraer_numeros(texto_medidas)

        hay_match = False
        if numeros_usuario and numeros_usuario.issubset(numeros_prod):
            hay_match = True
        elif not numeros_usuario:
             hay_match = True

        if hay_match:
            candidato_elegido = prod
            porcentaje_similitud = similitud_actual
            dimension_coincide = 1
            break

    if not candidato_elegido:
        mejor_idx = indices_top[0]
        candidato_elegido = metadata_tienda[mejor_idx]
        porcentaje_similitud = similitudes[mejor_idx]
        dimension_coincide = 0

    prediccion = juez_xgboost.predict(pd.DataFrame({
        'similitud_texto': [porcentaje_similitud],
        'misma_dimension': [dimension_coincide]
    }))[0]

    return candidato_elegido, porcentaje_similitud, prediccion == 1

# ==========================================
# 2. EL MOTOR DE COMPARACIÓN
# ==========================================
def iniciar_comparador():
    print("="*60)
    print(" 🛒 INICIANDO COMPARADOR CERCHA V3.5 (Con Precios Unitarios) ")
    print("="*60)
    
    ruta_sodimac = r'C:\Users\likan\Desktop\Motion Control\Proyectos\Programa Cercha\Comparador\motordelco-o\data\cerebro_sodimac.pkl'
    ruta_easy = r'C:\Users\likan\Desktop\Motion Control\Proyectos\Programa Cercha\Comparador\motordelco-o\data2\cerebro_easy.pkl'

    print("🧠 Cargando Memoria SODIMAC e EASY...")
    with open(ruta_sodimac, 'rb') as f: datos_sodimac = pickle.load(f)
    with open(ruta_easy, 'rb') as f: datos_easy = pickle.load(f)

    print("🤖 Encendiendo Red Neuronal Semántica...")
    modelo = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

    np.random.seed(42)
    sim = np.random.uniform(0.1, 1.0, 1000)
    dim = np.random.choice([0, 1], 1000)
    match = ((sim >= 0.70) & (dim == 1)).astype(int)
    df_entrenamiento = pd.DataFrame({'similitud_texto': sim, 'misma_dimension': dim, 'es_match': match})
    juez_xgboost = xgb.XGBClassifier(eval_metric='logloss')
    juez_xgboost.fit(df_entrenamiento[['similitud_texto', 'misma_dimension']], df_entrenamiento['es_match'])

    print("\n✅ ¡SISTEMA LISTO! Puedes empezar a buscar.")

    while True:
        query_usuario = input("\n🔎 Busca un producto (o escribe 'salir'): ")
        if query_usuario.lower() in ['salir', 'exit', 'quit']: break

        query_limpia = limpiar_texto(query_usuario)
        numeros_usuario = extraer_numeros(query_limpia)
        vector_query = modelo.encode([query_limpia], convert_to_tensor=True)

        prod_sodimac, sim_sodimac, match_sodimac = buscar_en_tienda(
            query_limpia, numeros_usuario, vector_query, datos_sodimac['metadata'], datos_sodimac['vectores'], juez_xgboost)
        
        prod_easy, sim_easy, match_easy = buscar_en_tienda(
            query_limpia, numeros_usuario, vector_query, datos_easy['metadata'], datos_easy['vectores'], juez_xgboost)

        print("\n" + "="*65)
        print(f"📊 RESULTADOS PARA: '{query_usuario.upper()}'")
        print("="*65)

        # 🔥 CALCULAR PRECIOS UNITARIOS
        precio_unit_s = 0
        if match_sodimac:
            cant_s = extraer_cantidad(prod_sodimac['titulo'])
            precio_unit_s = prod_sodimac['precio'] / cant_s
            marca_s = "🟢"
            print(f"🟠 SODIMAC {marca_s} (Match: {sim_sodimac*100:.1f}%)")
            print(f"   📌 {prod_sodimac['titulo']}")
            print(f"   📦 Cantidad: {cant_s} unidades")
            print(f"   💰 Precio Caja: ${prod_sodimac['precio']:,.0f}  👉 [ Valor Unitario: ${precio_unit_s:,.1f} c/u ]")
        else:
            print("🟠 SODIMAC 🔴")
            print("   ⚠️ No se encontró un producto exacto.")

        print("-" * 65)

        precio_unit_e = 0
        if match_easy:
            cant_e = extraer_cantidad(prod_easy['titulo'])
            precio_unit_e = prod_easy['precio'] / cant_e
            marca_e = "🟢"
            print(f"🔵 EASY {marca_e} (Match: {sim_easy*100:.1f}%)")
            print(f"   📌 {prod_easy['titulo']}")
            print(f"   📦 Cantidad: {cant_e} unidades")
            print(f"   💰 Precio Caja: ${prod_easy['precio']:,.0f}  👉 [ Valor Unitario: ${precio_unit_e:,.1f} c/u ]")
        else:
            print("🔵 EASY 🔴")
            print("   ⚠️ No se encontró un producto exacto.")

        print("="*65)

        # 💡 La Inteligencia de Ahorro AHORA BASADA EN EL PRECIO POR TORNILLO
        if match_sodimac and match_easy:
            if precio_unit_s < precio_unit_e:
                diff = precio_unit_e - precio_unit_s
                print(f"🏆 RECOMENDACIÓN CERCHA: ¡Compra en SODIMAC! Te ahorras ${diff:,.1f} por cada tornillo.")
            elif precio_unit_e < precio_unit_s:
                diff = precio_unit_s - precio_unit_e
                print(f"🏆 RECOMENDACIÓN CERCHA: ¡Compra en EASY! Te ahorras ${diff:,.1f} por cada tornillo.")
            else:
                print("⚖️ RECOMENDACIÓN CERCHA: ¡Cuestan exactamente lo mismo por unidad! Compra en tu favorita.")
        print("="*65)

if __name__ == "__main__":
    iniciar_comparador()