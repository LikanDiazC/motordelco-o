"""Análisis de clusters: utilidad para matching cruzado Easy<->Sodimac.

Responde:
  - ¿Cuántos clusters son efectivamente bi-tienda y útiles para matching?
  - ¿Cuántos pares candidatos genera el blocking?
  - ¿Qué reducción se consigue vs brute force (1421 × 2221 = 3.155.741 pares)?
  - Distribución de tamaños de cluster
  - Ejemplos de clusters bi-tienda exitosos
"""
import json
from pathlib import Path
from collections import Counter

REPORTE = Path(r"C:\Users\Administrator\Documents\Buscop\motordelco-o\data\clusters_reporte.json")

with open(REPORTE, encoding="utf-8") as f:
    rep = json.load(f)

clusters = [c for c in rep["clusters"] if c["cluster_id"] != -1]
print("=" * 70)
print("ANÁLISIS DE CLUSTERS PARA MATCHING CRUZADO")
print("=" * 70)
print(f"\nTotal productos      : {rep['n_productos']}")
print(f"Clusters detectados  : {rep['n_clusters']}")
print(f"Productos ruido (-1) : {rep['n_ruido']} ({rep['n_ruido']*100//rep['n_productos']}%)")

# --- clasificación de cada cluster por utilidad para matching ---
# (útil = tiene al menos 2 productos en cada tienda)
bi_tienda_util = []
bi_tienda_debil = []
mono_easy = []
mono_sodimac = []

for c in clusters:
    e = c["por_tienda"].get("easy", 0)
    s = c["por_tienda"].get("sodimac", 0)
    if e == 0:
        mono_sodimac.append(c)
    elif s == 0:
        mono_easy.append(c)
    elif min(e, s) >= 2:
        bi_tienda_util.append(c)
    else:
        bi_tienda_debil.append(c)

print(f"\n{'─'*70}")
print("CLASIFICACIÓN DE CLUSTERS")
print(f"{'─'*70}")
print(f"  Bi-tienda útiles  (>=2 en cada tienda) : {len(bi_tienda_util):>3}")
print(f"  Bi-tienda débiles (1 producto en una)  : {len(bi_tienda_debil):>3}")
print(f"  Mono-tienda Easy                       : {len(mono_easy):>3}")
print(f"  Mono-tienda Sodimac                    : {len(mono_sodimac):>3}")

# --- pares candidatos generados por el blocking ---
pares_brute = 1421 * 2221
pares_cluster = sum(
    c["por_tienda"].get("easy", 0) * c["por_tienda"].get("sodimac", 0)
    for c in clusters
)
reduccion = 100 * (1 - pares_cluster / pares_brute)

print(f"\n{'─'*70}")
print("BLOCKING: reducción del espacio de pares")
print(f"{'─'*70}")
print(f"  Brute force     : {pares_brute:>10,} pares (todos contra todos)")
print(f"  Con clustering  : {pares_cluster:>10,} pares candidatos")
print(f"  Reducción       : {reduccion:>9.2f} %")

# --- productos efectivamente alcanzables ---
prod_easy_bi  = sum(c["por_tienda"].get("easy", 0) for c in bi_tienda_util)
prod_sod_bi   = sum(c["por_tienda"].get("sodimac", 0) for c in bi_tienda_util)
prod_easy_debil = sum(c["por_tienda"].get("easy", 0) for c in bi_tienda_debil)
prod_sod_debil  = sum(c["por_tienda"].get("sodimac", 0) for c in bi_tienda_debil)

print(f"\n{'─'*70}")
print("COBERTURA DE PRODUCTOS EN CLUSTERS BI-TIENDA")
print(f"{'─'*70}")
print(f"  Easy    en clusters útiles : {prod_easy_bi:>4} / 2221 ({prod_easy_bi*100//2221}%)")
print(f"  Sodimac en clusters útiles : {prod_sod_bi:>4} / 1421 ({prod_sod_bi*100//1421}%)")
print(f"  Easy    en clusters débiles: {prod_easy_debil:>4}")
print(f"  Sodimac en clusters débiles: {prod_sod_debil:>4}")

# --- top 15 clusters bi-tienda útiles ---
print(f"\n{'─'*70}")
print("TOP 15 CLUSTERS BI-TIENDA ÚTILES (ordenados por equilibrio)")
print(f"{'─'*70}")
# score: harmónica entre tamaño y equilibrio
def score(c):
    e = c["por_tienda"].get("easy", 0)
    s = c["por_tienda"].get("sodimac", 0)
    balance = min(e, s) / max(e, s) if max(e, s) else 0
    return c["tamano"] * balance

bi_ordenados = sorted(bi_tienda_util, key=score, reverse=True)[:15]
print(f"  {'ID':>4} {'n':>4} {'easy':>5} {'sodi':>5} {'bal':>5}  categoria     ejemplo")
for c in bi_ordenados:
    e = c["por_tienda"].get("easy", 0)
    s = c["por_tienda"].get("sodimac", 0)
    bal = min(e, s) / max(e, s)
    cat = (c["categoria_top"] or "?")[:12]
    ej = c["ejemplos"][0]["titulo"][:60]
    print(f"  {c['cluster_id']:>4} {c['tamano']:>4} {e:>5} {s:>5} {bal:>5.2f}  {cat:<13} {ej}")

# --- tamaño del cluster más grande para matching ---
mayor = max(bi_tienda_util, key=lambda c: c["por_tienda"].get("easy", 0) * c["por_tienda"].get("sodimac", 0))
e_max = mayor["por_tienda"].get("easy", 0)
s_max = mayor["por_tienda"].get("sodimac", 0)
print(f"\n  Cluster con más pares candidatos: #{mayor['cluster_id']} "
      f"({e_max} easy × {s_max} sodimac = {e_max*s_max} pares)")
print(f"  Ejemplo: {mayor['ejemplos'][0]['titulo']}")

# --- distribución de tamaños ---
print(f"\n{'─'*70}")
print("DISTRIBUCIÓN DE TAMAÑOS DE CLUSTER")
print(f"{'─'*70}")
tams = [c["tamano"] for c in clusters]
import statistics
print(f"  Media  : {statistics.mean(tams):.1f}")
print(f"  Mediana: {statistics.median(tams):.0f}")
print(f"  Mínimo : {min(tams)}")
print(f"  Máximo : {max(tams)}")

rangos = Counter()
for t in tams:
    if t < 20:    rangos["  15-19"] += 1
    elif t < 40:  rangos["  20-39"] += 1
    elif t < 80:  rangos["  40-79"] += 1
    elif t < 150: rangos[" 80-149"] += 1
    else:         rangos["   150+"] += 1
for r, n in sorted(rangos.items()):
    bar = "#" * n
    print(f"    {r}: {n:>3} {bar}")
