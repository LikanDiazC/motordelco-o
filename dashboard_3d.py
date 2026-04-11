import streamlit as st
import plotly.graph_objects as go
import numpy as np
from sklearn.decomposition import PCA
import requests
from datetime import datetime

from cercha.domain.search_engine import limpiar_texto

st.set_page_config(page_title="Cercha MLOps Dashboard", layout="wide")

st.title("Centro de Diagnóstico MLOps — Cercha V5.0")
st.caption("Espacio Latente Vectorial · Historial de Búsquedas · Líneas de Decisión del Algoritmo")


# ==========================================
# 1. MOTOR (una sola vez en memoria)
# ==========================================
@st.cache_resource
def cargar_motor():
    from cercha.pipeline import CerchaPipeline
    return CerchaPipeline()


with st.spinner("Cargando modelo semántico y bases vectoriales..."):
    motor = cargar_motor()

if not any(t in motor.tiendas for t in ('sodimac', 'easy')):
    st.error("No hay cerebros vectoriales disponibles. Ejecuta el pipeline primero.")
    st.stop()


# ==========================================
# 2. PCA 384D → 3D (cacheado, vectores como args con _ para skip hashing)
# ==========================================
@st.cache_data
def generar_universo_3d(_vs, _ve):
    todos = np.vstack([_vs, _ve])
    pca = PCA(n_components=3)
    coords = pca.fit_transform(todos)
    n = len(_vs)
    return pca, coords[:n], coords[n:]


vs = motor.tiendas.get('sodimac', {}).get('vectores', np.empty((0, 384)))
ve = motor.tiendas.get('easy', {}).get('vectores', np.empty((0, 384)))
pca_model, coords_sodimac, coords_easy = generar_universo_3d(vs, ve)


# ==========================================
# 3. ESTADO DE SESIÓN
# ==========================================
if 'query_history' not in st.session_state:
    st.session_state['query_history'] = []   # [{query, timestamp, query_3d, api_result, api_error}]
if 'selected_idx' not in st.session_state:
    st.session_state['selected_idx'] = None


# ==========================================
# 4. BARRA DE BÚSQUEDA (ancho completo, arriba)
# ==========================================
with st.form("busqueda_form", clear_on_submit=False):
    c_input, c_btn = st.columns([5, 1])
    with c_input:
        query_usuario = st.text_input(
            "query",
            placeholder="ej: tornillo madera 50mm  /  clavo 3 pulgadas  /  perno 1/4 x 2 1/2",
            label_visibility="collapsed",
        )
    with c_btn:
        submitted = st.form_submit_button("Buscar", use_container_width=True)

if submitted and query_usuario.strip():
    query = query_usuario.strip()
    query_limpia = limpiar_texto(query)
    vector_query = motor.modelo.encode([query_limpia], convert_to_tensor=False)
    query_3d = pca_model.transform(vector_query)

    api_result, api_error = None, None
    try:
        res = requests.post(
            "http://127.0.0.1:8000/cotizar",
            json={"query": query},
            timeout=10,
        )
        api_result = res.json() if res.status_code == 200 else None
        api_error = res.text if res.status_code != 200 else None
    except requests.exceptions.ConnectionError:
        api_error = "API offline — inicia con: `uvicorn api:app`"

    st.session_state['query_history'].append({
        'query': query,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'query_3d': query_3d,
        'api_result': api_result,
        'api_error': api_error,
    })
    st.session_state['selected_idx'] = len(st.session_state['query_history']) - 1


# ==========================================
# 5. LAYOUT PRINCIPAL: historial (izq) + gráfico 3D (der, grande)
# ==========================================
col_hist, col_plot = st.columns([1, 3])

# ------------------------------------------
# PANEL IZQUIERDO: historial + diagnóstico
# ------------------------------------------
with col_hist:
    history = st.session_state['query_history']
    sel = st.session_state.get('selected_idx')

    st.subheader("Historial")
    if not history:
        st.caption("Ninguna búsqueda aún.")
    else:
        # Más reciente primero
        for i in range(len(history) - 1, -1, -1):
            e = history[i]
            is_sel = (sel == i)
            label = f"{'▶  ' if is_sel else '   '}{e['timestamp']}  —  {e['query']}"
            if st.button(label, key=f"hist_{i}", use_container_width=True):
                st.session_state['selected_idx'] = i
                sel = i          # efecto inmediato en este mismo render

    st.divider()

    # Diagnóstico del item seleccionado
    st.subheader("Diagnóstico")
    if sel is not None and history:
        e = history[sel]

        st.markdown(f"**`{e['query']}`**  ·  {e['timestamp']}")

        if e['api_result']:
            datos = e['api_result']
            st.success(datos['recomendacion'])
            for tienda, r in datos['resultados'].items():
                color = "🟠" if tienda == 'sodimac' else "🔵"
                if r['es_match']:
                    with st.expander(f"{color} {tienda.upper()} — {r['similitud_semantica']}% match"):
                        st.write(f"**{r['producto']}**")
                        st.write(f"Pack: {r['unidades_pack']} u · ${r['precio_total']:,.0f}")
                        st.write(f"Unitario: **${r['precio_unitario']:,.1f}**")
                        if r.get('url'):
                            st.write(r['url'])
                else:
                    st.info(f"{color} {tienda.upper()}: Sin match")

        elif e['api_error']:
            st.warning(e['api_error'])
        else:
            st.caption("Sin resultado de API para esta búsqueda.")
    else:
        st.caption("Busca un producto para ver el diagnóstico.")


# ------------------------------------------
# PANEL DERECHO: gráfico 3D grande
# ------------------------------------------
with col_plot:
    st.subheader("Universo Vectorial — Espacio Latente 3D")

    fig = go.Figure()

    # Nube de productos Sodimac
    if 'sodimac' in motor.tiendas and coords_sodimac.shape[0] > 0:
        fig.add_trace(go.Scatter3d(
            x=coords_sodimac[:, 0],
            y=coords_sodimac[:, 1],
            z=coords_sodimac[:, 2],
            mode='markers',
            marker=dict(size=2.5, color='#f97316', opacity=0.35),
            name='Sodimac',
            hovertext=[m['titulo'] for m in motor.tiendas['sodimac']['metadata']],
            hoverinfo='text',
        ))

    # Nube de productos Easy
    if 'easy' in motor.tiendas and coords_easy.shape[0] > 0:
        fig.add_trace(go.Scatter3d(
            x=coords_easy[:, 0],
            y=coords_easy[:, 1],
            z=coords_easy[:, 2],
            mode='markers',
            marker=dict(size=2.5, color='#3b82f6', opacity=0.35),
            name='Easy',
            hovertext=[m['titulo'] for m in motor.tiendas['easy']['metadata']],
            hoverinfo='text',
        ))

    # ---- Query seleccionada + líneas punteadas ----
    sel = st.session_state.get('selected_idx')
    if sel is not None and st.session_state['query_history']:
        entry = st.session_state['query_history'][sel]
        q3d = entry['query_3d']
        qx, qy, qz = float(q3d[0][0]), float(q3d[0][1]), float(q3d[0][2])

        # Cruz roja = vector de la query
        fig.add_trace(go.Scatter3d(
            x=[qx], y=[qy], z=[qz],
            mode='markers',
            marker=dict(size=14, color='#ef4444', symbol='cross', opacity=1.0),
            name=f"Query: {entry['query']}",
            hovertext=[f"QUERY: {entry['query']}"],
            hoverinfo='text',
        ))

        # Líneas punteadas hacia los productos matcheados
        colores_tienda = {'sodimac': '#fb923c', 'easy': '#60a5fa'}
        if entry['api_result']:
            for tienda, resultado in entry['api_result']['resultados'].items():
                if not resultado['es_match'] or not resultado['producto']:
                    continue

                titulo = resultado['producto']
                metadata_t = motor.tiendas.get(tienda, {}).get('metadata', [])
                coords_t = coords_sodimac if tienda == 'sodimac' else coords_easy
                color_t = colores_tienda.get(tienda, '#aaa')

                # Buscar coordenadas del producto en el espacio 3D
                prod_3d = None
                for i, m in enumerate(metadata_t):
                    if m['titulo'] == titulo:
                        prod_3d = coords_t[i]
                        break

                if prod_3d is None:
                    continue

                px, py, pz = float(prod_3d[0]), float(prod_3d[1]), float(prod_3d[2])
                sim = resultado['similitud_semantica']
                precio_u = resultado['precio_unitario']

                # Línea punteada query → producto
                fig.add_trace(go.Scatter3d(
                    x=[qx, px], y=[qy, py], z=[qz, pz],
                    mode='lines',
                    line=dict(color=color_t, width=3, dash='dash'),
                    name=f"Decisión {tienda.upper()}",
                    hoverinfo='skip',
                    showlegend=True,
                ))

                # Diamante = producto seleccionado por el motor
                fig.add_trace(go.Scatter3d(
                    x=[px], y=[py], z=[pz],
                    mode='markers',
                    marker=dict(
                        size=9,
                        color=color_t,
                        symbol='diamond',
                        opacity=1.0,
                        line=dict(color='white', width=1),
                    ),
                    name=f"Match {tienda.upper()}",
                    hovertext=[
                        f"<b>{tienda.upper()}</b><br>"
                        f"{titulo}<br>"
                        f"Similitud: {sim}%<br>"
                        f"Unitario: ${precio_u:,.1f}"
                    ],
                    hoverinfo='text',
                ))

    # ---- Estilo del gráfico ----
    fig.update_layout(
        height=810,
        margin=dict(l=0, r=0, b=0, t=0),
        paper_bgcolor='#0f172a',
        legend=dict(
            font=dict(color='#cbd5e1', size=11),
            bgcolor='rgba(15,23,42,0.85)',
            bordercolor='#334155',
            borderwidth=1,
            itemsizing='constant',
        ),
        uirevision='cercha-universe',  # conserva la posición de cámara entre re-renders
        scene=dict(
            bgcolor='#0f172a',
            xaxis=dict(
                backgroundcolor='#1e293b',
                gridcolor='#334155',
                showbackground=True,
                zerolinecolor='#475569',
                title=dict(text='PC 1', font=dict(color='#94a3b8', size=11)),
                tickfont=dict(color='#64748b', size=8),
            ),
            yaxis=dict(
                backgroundcolor='#1e293b',
                gridcolor='#334155',
                showbackground=True,
                zerolinecolor='#475569',
                title=dict(text='PC 2', font=dict(color='#94a3b8', size=11)),
                tickfont=dict(color='#64748b', size=8),
            ),
            zaxis=dict(
                backgroundcolor='#1e293b',
                gridcolor='#334155',
                showbackground=True,
                zerolinecolor='#475569',
                title=dict(text='PC 3', font=dict(color='#94a3b8', size=11)),
                tickfont=dict(color='#64748b', size=8),
            ),
            camera=dict(
                eye=dict(x=1.45, y=1.45, z=0.75),
                up=dict(x=0, y=0, z=1),
                center=dict(x=0, y=0, z=-0.1),
            ),
            aspectmode='auto',
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Puntos = productos en el catálogo.  "
    "Cruz roja = vector de tu búsqueda.  "
    "Diamantes = productos seleccionados por el motor híbrido.  "
    "Líneas punteadas = decisión del algoritmo (qué conectó y por qué)."
)
