import re
import pickle
import torch
import pandas as pd
import numpy as np
import xgboost as xgb
from sentence_transformers import SentenceTransformer, util

def normalizar_titulo(titulo):
    texto = titulo.lower()
    reemplazos = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}
    for original, nuevo in reemplazos.items():
        texto = texto.replace(original, nuevo)
    
    sinonimos = {"yeso-carton": "drywall", "yesocarton": "drywall", "yeso carton": "drywall", "volcanita": "drywall", "\"": "pulgada"}
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

def iniciar_aplicacion():
    print("\n🧠 1/3 Despertando a la Inteligencia Artificial...")
    modelo_ia = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', cache_folder='./modelo_temporal')
    
    print("📚 2/3 Leyendo el cerebro vectorial de Sodimac (.pkl)...")
    try:
        with open('data/cerebro_sodimac.pkl', 'rb') as f:
            base_conocimiento = pickle.load(f)
            productos_sodimac = base_conocimiento["productos"]
            vectores_sodimac = base_conocimiento["vectores"]
    except FileNotFoundError:
        print("❌ ERROR: No encuentro el archivo data/cerebro_sodimac.pkl")
        return

    print("👨‍⚖️ 3/3 Entrenando al Juez XGBoost con 1000 casos sintéticos...")
    
    # Generamos 1000 casos ficticios aleatorios
    np.random.seed(42)
    sim = np.random.uniform(0.1, 1.0, 1000)
    dim = np.random.choice([0, 1], 1000)
    
    # Le inyectamos nuestra regla de negocio estricta: >75% + Misma dimensión = APROBADO (1)
    match = ((sim >= 0.75) & (dim == 1)).astype(int)
    
    df_entrenamiento = pd.DataFrame({
        'similitud_texto': sim,
        'misma_dimension': dim,
        'es_match': match
    })
    
    juez_xgboost = xgb.XGBClassifier(eval_metric='logloss')
    juez_xgboost.fit(df_entrenamiento[['similitud_texto', 'misma_dimension']], df_entrenamiento['es_match'])
    while True:
        busqueda_cercha = input("\n🔎 ¿Qué producto tienes en tu sistema Cercha?: ")
        
        if busqueda_cercha.lower() == 'salir':
            print("Apagando sistema... ¡Hasta luego!")
            break
            
        if not busqueda_cercha.strip():
            continue

        # 1. Normalización Cercha
        titulo_limpio = normalizar_titulo(busqueda_cercha)
        dimension_buscada = extraer_dimensiones(titulo_limpio)
        print(f"🧹 Texto procesado: '{titulo_limpio}' | 📏 Medida: {dimension_buscada}")
        
        # 2. Búsqueda Vectorial masiva
        vector_busqueda = modelo_ia.encode(titulo_limpio)
        similitudes = util.cos_sim(vector_busqueda, vectores_sodimac)[0]
        
        # 3. EL EMBUDO (Magia pura): Traemos los 15 mejores en vez de 1
        top_15_indices = torch.topk(similitudes, k=15).indices.tolist()
        
        mejor_candidato = None
        similitud_ia = 0
        misma_dimension = 0

        # Buscamos el primero dentro del Top 15 que SÍ tenga la medida correcta
        for idx in top_15_indices:
            cand = productos_sodimac[idx]
            dim_cand = cand.get('dimension_detectada', 'N/A')
            
            if dimension_buscada == dim_cand and dimension_buscada != "Dimensión no encontrada":
                mejor_candidato = cand
                similitud_ia = similitudes[idx].item()
                misma_dimension = 1
                break # Encontramos el correcto, detenemos la búsqueda
                
        # Si ninguno de los 15 calzó en medida, nos resignamos al #1 (que fallará en XGBoost)
        if mejor_candidato is None:
            idx_1 = top_15_indices[0]
            mejor_candidato = productos_sodimac[idx_1]
            similitud_ia = similitudes[idx_1].item()
            misma_dimension = 0
        
        dimension_candidato = mejor_candidato.get('dimension_detectada', 'N/A')
        
        # 4. ¡EL JUEZ XGBOOST DECIDE!
        df_evidencia = pd.DataFrame({
            'similitud_texto': [similitud_ia],
            'misma_dimension': [misma_dimension]
        })
        veredicto = int(juez_xgboost.predict(df_evidencia)[0])

        if veredicto == 1:
            mensaje_juez = "🟢 ¡ES MATCH! (Aprobado automáticamente)"
        else:
            mensaje_juez = "🔴 RECHAZADO (Similitud semántica baja o medida incorrecta)"

        specs = mejor_candidato.get('especificaciones', {})
        material = specs.get('Material', 'N/A')
        cabeza = specs.get('Tipo de cabeza', 'N/A')
        
        print("\n" + "-"*55)
        print("🎯 MEJOR CANDIDATO ENCONTRADO (Tras pasar el embudo):")
        print(f"📌 Título  : {mejor_candidato['titulo']}")
        print(f"💵 Precio  : ${mejor_candidato.get('precio_clp', 0):,.0f}")
        print(f"⚙️ Specs   : Material: {material} | Cabeza: {cabeza}")
        print(f"📏 Medida  : {dimension_candidato} (Coincide: {'Sí' if misma_dimension == 1 else 'No'})")
        print(f"🤖 IA Match: {similitud_ia * 100:.2f}% de similitud")
        print("\n👨‍⚖️ VEREDICTO DEL JUEZ XGBOOST:")
        print(f"-> {mensaje_juez}")
        print("-" * 55)

if __name__ == "__main__":
    iniciar_aplicacion()