import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
import time
import requests

st.set_page_config(page_title="Cercha MLOps Dashboard", layout="wide")

st.title("🧠 Centro de Diagnóstico MLOps: Cercha V5.0")
st.markdown("Visualización en tiempo real del Espacio Latente (Vectores) y Sesgos Semánticos.")

# ==========================================
# 1. CARGA DE DATOS (Caché para no saturar RAM)
# ==========================================
@st.cache_resource
def cargar_motor():
    from cercha.pipeline import CerchaPipeline
    return CerchaPipeline()

with st.spinner("Cargando Redes Neuronales y Bases Vectoriales..."):
    motor = cargar_motor()

# ==========================================
# 2. REDUCCIÓN DE DIMENSIONALIDAD (384D -> 3D)
# ==========================================
@st.cache_data
def generar_universo_3d():
    """Reduce los vectores de las tiendas a 3 dimensiones para graficarlos."""
    vectores_sodimac = motor.tiendas['sodimac']['vectores']
    vectores_easy = motor.tiendas['easy']['vectores']
    
    # Juntamos todos los vectores para calcular el PCA global
    todos_los_vectores = np.vstack([vectores_sodimac, vectores_easy])
    
    pca = PCA(n_components=3)
    vectores_3d = pca.fit_transform(todos_los_vectores)
    
    # Separamos las coordenadas 3D para cada tienda
    num_sodimac = len(vectores_sodimac)
    coords_sodimac = vectores_3d[:num_sodimac]
    coords_easy = vectores_3d[num_sodimac:]
    
    return pca, coords_sodimac, coords_easy

pca_model, coords_sodimac, coords_easy = generar_universo_3d()

# ==========================================
# 3. INTERFAZ DE BÚSQUEDA Y DIAGNÓSTICO
# ==========================================
query_usuario = st.text_input("🔍 Busca un producto para diagnosticar:", "tornillo madera 50mm")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📋 Diagnóstico de la API")
    if st.button("Ejecutar Búsqueda Híbrida"):
        with st.spinner("Consultando API local..."):
            try:
                # OJO: Asume que tu API FastAPI está corriendo en el puerto 8000
                res = requests.post("http://127.0.0.1:8000/cotizar", json={"query": query_usuario})
                
                if res.status_code == 200:
                    datos = res.json()
                    st.success(f"Recomendación: {datos['recomendacion']}")
                    st.json(datos["resultados"])
                else:
                    st.error(f"Error de la API: {res.text}")
            except Exception as e:
                st.error("⚠️ La API (api.py) no está corriendo. Enciende el servidor con: `uvicorn api:app`")

with col2:
    st.subheader("🌌 Universo Vectorial (Espacio Latente 3D)")
    
    # Creamos el gráfico base con los puntos de las tiendas
    fig = go.Figure()

    # Puntos de Sodimac (Naranjas)
    fig.add_trace(go.Scatter3d(
        x=coords_sodimac[:, 0], y=coords_sodimac[:, 1], z=coords_sodimac[:, 2],
        mode='markers',
        marker=dict(size=3, color='orange', opacity=0.5),
        name='Sodimac',
        hovertext=[m['titulo'] for m in motor.tiendas['sodimac']['metadata']]
    ))

    # Puntos de Easy (Azules)
    fig.add_trace(go.Scatter3d(
        x=coords_easy[:, 0], y=coords_easy[:, 1], z=coords_easy[:, 2],
        mode='markers',
        marker=dict(size=3, color='blue', opacity=0.5),
        name='Easy',
        hovertext=[m['titulo'] for m in motor.tiendas['easy']['metadata']]
    ))
    
    # Si hay una búsqueda, la codificamos y la dibujamos como un punto gigante
    if query_usuario:
        from cercha.domain.search_engine import limpiar_texto
        query_limpia = limpiar_texto(query_usuario)
        vector_query = motor.modelo.encode([query_limpia], convert_to_tensor=False)
        
        # Reducimos el vector de la búsqueda de 384D a 3D usando el mismo modelo matemático
        query_3d = pca_model.transform(vector_query)
        
        fig.add_trace(go.Scatter3d(
            x=[query_3d[0][0]], y=[query_3d[0][1]], z=[query_3d[0][2]],
            mode='markers',
            marker=dict(size=10, color='red', symbol='cross'),
            name='Tu Búsqueda (Input)',
            hovertext=[f"Query: {query_usuario}"]
        ))

    fig.update_layout(margin=dict(l=0, r=0, b=0, t=0), height=600)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.markdown("**Diagnóstico Semántico:** Cada punto es un tornillo. Los tornillos con usos, cabezas y materiales similares se agrupan en 'galaxias'. La cruz roja es tu búsqueda aterrizando en el espacio matemático.")