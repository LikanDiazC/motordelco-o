from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

# Importamos tu motor de búsqueda
from cercha.pipeline import CerchaPipeline
from cercha.domain.search_engine import buscar_en_tienda, limpiar_texto

app = FastAPI(
    title="API Cercha V5.0",
    description="Motor de Cotización Híbrido (IA + Dimensional)",
    version="5.0"
)

# 🧠 Cargamos el motor en memoria al iniciar la API
print("Cargando el cerebro Cercha...")
motor = CerchaPipeline()
print("¡Cerebro cargado y listo!")

class BuesquedaRequest(BaseModel):
    query: str

@app.get("/")
def read_root():
    return {"status": "ok", "message": "API Cercha V5.0 Activa."}

@app.post("/cotizar")
def cotizar_producto(req: BuesquedaRequest) -> Dict[str, Any]:
    if not req.query:
        raise HTTPException(status_code=400, detail="La query no puede estar vacía.")
    
    query_limpia = limpiar_texto(req.query)
    
    # IMPORTANTE: Usamos convert_to_tensor=False para evitar problemas de GPU/CPU
    vector_query = motor.modelo.encode([query_limpia], convert_to_tensor=False)
    
    resultados_tiendas = {}
    
    for nombre_tienda, datos_tienda in motor.tiendas.items():
        # Ejecutamos la búsqueda en cada tienda
        match_result = buscar_en_tienda(
            query_limpia=query_limpia,
            vector_query=vector_query,
            metadata=datos_tienda['metadata'],
            vectores=datos_tienda['vectores'],
            umbral_match=motor.umbral
        )
        resultados_tiendas[nombre_tienda] = match_result

    # Analizamos qué tienda ganó en precio unitario
    matches = {n: r for n, r in resultados_tiendas.items() if r.es_match}
    
    ganador = None
    ahorro = 0.0
    recomendacion = "No hay productos compatibles."
    
    if len(matches) >= 2:
        ganador = min(matches, key=lambda n: matches[n].precio_unitario)
        precios = sorted(matches.values(), key=lambda r: r.precio_unitario)
        ahorro = precios[1].precio_unitario - precios[0].precio_unitario
        if ahorro > 0:
            recomendacion = f"Compra en {ganador.upper()}. Ahorras ${ahorro:,.1f} por unidad."
        else:
            recomendacion = "Mismo precio en ambas tiendas."
    elif len(matches) == 1:
        ganador = list(matches.keys())[0]
        recomendacion = f"Solo disponible en {ganador.upper()}."

    # Formateamos la respuesta JSON para que la lea el Frontend o la App
    respuesta = {
        "busqueda": req.query,
        "ganador": ganador,
        "ahorro_unitario": ahorro,
        "recomendacion": recomendacion,
        "resultados": {}
    }
    
    for tienda, res in resultados_tiendas.items():
        respuesta["resultados"][tienda] = {
            "es_match": res.es_match,
            "similitud_semantica": round(res.similitud * 100, 2),
            "medidas_coinciden": res.dimensiones_coinciden,
            "producto": res.producto['titulo'] if res.es_match else None,
            "precio_total": res.producto['precio'] if res.es_match else None,
            "unidades_pack": res.cantidad if res.es_match else None,
            "precio_unitario": res.precio_unitario if res.es_match else None,
            "url": res.producto['url'] if res.es_match else None
        }
        
    return respuesta