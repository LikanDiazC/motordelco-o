from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any

from cercha.pipeline import CerchaPipeline
from cercha.domain.search_engine import buscar_en_tienda, limpiar_texto

app = FastAPI(
    title="API Cercha V5.0",
    description="Motor de Cotización Híbrido (IA + Dimensional)",
    version="5.0"
)

# CORS: necesario para que el dashboard Streamlit (puerto 8501) llame a la API (puerto 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Cargando el cerebro Cercha...")
motor = CerchaPipeline()
print("¡Cerebro cargado y listo!")


class BusquedaRequest(BaseModel):
    query: str


@app.get("/")
def read_root():
    tiendas_activas = list(motor.tiendas.keys())
    return {
        "status": "ok",
        "message": "API Cercha V5.0 Activa.",
        "tiendas_activas": tiendas_activas,
    }


@app.post("/cotizar")
def cotizar_producto(req: BusquedaRequest) -> Dict[str, Any]:
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="La query no puede estar vacía.")

    if not motor.tiendas:
        raise HTTPException(
            status_code=503,
            detail="No hay cerebros vectoriales cargados. Ejecuta el pipeline primero."
        )

    query_limpia = limpiar_texto(query)
    vector_query = motor.modelo.encode([query_limpia], convert_to_tensor=False)

    resultados_tiendas = {}
    for nombre_tienda, datos_tienda in motor.tiendas.items():
        resultados_tiendas[nombre_tienda] = buscar_en_tienda(
            query_limpia=query_limpia,
            vector_query=vector_query,
            metadata=datos_tienda['metadata'],
            vectores=datos_tienda['vectores'],
            umbral_match=motor.umbral,
        )

    matches = {n: r for n, r in resultados_tiendas.items() if r.es_match}

    ganador = None
    ahorro = 0.0
    recomendacion = "No hay productos compatibles."

    if len(matches) >= 2:
        ganador = min(matches, key=lambda n: matches[n].precio_unitario)
        precios = sorted(matches.values(), key=lambda r: r.precio_unitario)
        ahorro = precios[1].precio_unitario - precios[0].precio_unitario
        recomendacion = (
            f"Compra en {ganador.upper()}. Ahorras ${ahorro:,.1f} por unidad."
            if ahorro > 0 else "Mismo precio en ambas tiendas."
        )
    elif len(matches) == 1:
        ganador = list(matches.keys())[0]
        recomendacion = f"Solo disponible en {ganador.upper()}."

    respuesta: Dict[str, Any] = {
        "busqueda": req.query,
        "ganador": ganador,
        "ahorro_unitario": ahorro,
        "recomendacion": recomendacion,
        "resultados": {},
    }

    for tienda, res in resultados_tiendas.items():
        respuesta["resultados"][tienda] = {
            "es_match": res.es_match,
            "similitud_semantica": round(res.similitud * 100, 2),
            "medidas_coinciden": res.dimensiones_coinciden,
            "producto": res.producto['titulo'] if res.es_match else None,
            "precio_total": res.producto['precio'] if res.es_match else None,
            "unidades_pack": res.cantidad if res.es_match else None,
            "precio_unitario": round(res.precio_unitario, 1) if res.es_match else None,
            "url": res.producto.get('url') if res.es_match else None,  # .get() evita KeyError
        }

    return respuesta
