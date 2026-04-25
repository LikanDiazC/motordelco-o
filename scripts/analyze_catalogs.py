import json
from collections import defaultdict, Counter

# ─── helpers ────────────────────────────────────────────────────────────────

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def pct(n, total):
    return f"{n}/{total} ({100*n/total:.1f}%)" if total else "0/0"

def is_filled(val):
    if val is None:
        return False
    if isinstance(val, str):
        return val.strip() != ""
    if isinstance(val, (list, dict)):
        return len(val) > 0
    if isinstance(val, (int, float)):
        return True
    return bool(val)

def cover(products, accessor, extra=None):
    count = 0
    for p in products:
        try:
            val = accessor(p)
            ok = is_filled(val)
            if ok and extra:
                ok = extra(val)
            if ok:
                count += 1
        except (KeyError, TypeError):
            pass
    return count

# ─── load ───────────────────────────────────────────────────────────────────

sodimac = load(r"C:/Users/Administrator/Documents/Buscop/motordelco-o/data/sodimac/catalogo_normalizado.json")
easy    = load(r"C:/Users/Administrator/Documents/Buscop/motordelco-o/data/easy/catalogo_normalizado.json")

stores = {"sodimac": sodimac, "easy": easy}

print("=" * 70)
print("  SECTION 1 — TOTALS & BASIC SCHEMA VALIDITY")
print("=" * 70)

REQUIRED_TOP    = ["id_producto", "tienda", "sku", "url_producto", "url_imagen",
                   "metadata_basica", "metadata_tecnica", "contenido_vectorial"]
REQUIRED_BASICA = ["marca", "titulo", "precio_clp", "precio_normal_clp",
                   "descuento_pct", "categorias", "rating", "review_count",
                   "disponibilidad", "ean"]
REQUIRED_TECNICA= ["material", "tipo_cabeza", "tipo_rosca", "tipo_punta",
                   "color", "cantidad_empaque", "dimensiones"]
REQUIRED_DIM    = ["largo_mm", "diametro_mm", "medida_cruda"]
REQUIRED_VEC    = ["texto_enriquecido", "tokens_clave"]

for name, prods in stores.items():
    print(f"\n  Store: {name.upper()}  |  Total products: {len(prods)}")
    missing_top = missing_basica = missing_tecnica = missing_dim = missing_vec = 0
    for p in prods:
        if any(k not in p for k in REQUIRED_TOP):
            missing_top += 1
        mb = p.get("metadata_basica", {})
        if any(k not in mb for k in REQUIRED_BASICA):
            missing_basica += 1
        mt = p.get("metadata_tecnica", {})
        if any(k not in mt for k in REQUIRED_TECNICA):
            missing_tecnica += 1
        dim = mt.get("dimensiones", {})
        if any(k not in dim for k in REQUIRED_DIM):
            missing_dim += 1
        cv = p.get("contenido_vectorial", {})
        if any(k not in cv for k in REQUIRED_VEC):
            missing_vec += 1
    total = len(prods)
    print(f"    Products missing top-level keys:           {pct(missing_top, total)}")
    print(f"    Products missing metadata_basica keys:     {pct(missing_basica, total)}")
    print(f"    Products missing metadata_tecnica keys:    {pct(missing_tecnica, total)}")
    print(f"    Products missing dimensiones keys:         {pct(missing_dim, total)}")
    print(f"    Products missing contenido_vectorial keys: {pct(missing_vec, total)}")

# ─── section 2: field coverage ──────────────────────────────────────────────

print("\n")
print("=" * 70)
print("  SECTION 2 — FIELD COVERAGE")
print("=" * 70)

fields = [
    ("id_producto",           lambda p: p.get("id_producto"),                     None),
    ("tienda",                lambda p: p.get("tienda"),                           None),
    ("sku",                   lambda p: p.get("sku"),                              None),
    ("url_producto",          lambda p: p.get("url_producto"),                     None),
    ("url_imagen",            lambda p: p.get("url_imagen"),                       None),
    ("mb.marca",              lambda p: p["metadata_basica"].get("marca"),         None),
    ("mb.titulo",             lambda p: p["metadata_basica"].get("titulo"),        None),
    ("mb.precio_clp (>0)",    lambda p: p["metadata_basica"].get("precio_clp"),    lambda v: isinstance(v,(int,float)) and v > 0),
    ("mb.precio_normal_clp",  lambda p: p["metadata_basica"].get("precio_normal_clp"), None),
    ("mb.descuento_pct",      lambda p: p["metadata_basica"].get("descuento_pct"), None),
    ("mb.categorias",         lambda p: p["metadata_basica"].get("categorias"),    lambda v: isinstance(v,list) and len(v)>0),
    ("mb.rating",             lambda p: p["metadata_basica"].get("rating"),        None),
    ("mb.review_count",       lambda p: p["metadata_basica"].get("review_count"),  None),
    ("mb.disponibilidad",     lambda p: p["metadata_basica"].get("disponibilidad"),None),
    ("mb.ean",                lambda p: p["metadata_basica"].get("ean"),           None),
    ("mt.material",           lambda p: p["metadata_tecnica"].get("material"),     None),
    ("mt.tipo_cabeza",        lambda p: p["metadata_tecnica"].get("tipo_cabeza"),  None),
    ("mt.tipo_rosca",         lambda p: p["metadata_tecnica"].get("tipo_rosca"),   None),
    ("mt.tipo_punta",         lambda p: p["metadata_tecnica"].get("tipo_punta"),   None),
    ("mt.color",              lambda p: p["metadata_tecnica"].get("color"),        None),
    ("mt.cantidad_empaque",   lambda p: p["metadata_tecnica"].get("cantidad_empaque"), None),
    ("dim.largo_mm",          lambda p: p["metadata_tecnica"]["dimensiones"].get("largo_mm"), None),
    ("dim.diametro_mm",       lambda p: p["metadata_tecnica"]["dimensiones"].get("diametro_mm"), None),
    ("dim.medida_cruda",      lambda p: p["metadata_tecnica"]["dimensiones"].get("medida_cruda"), None),
    ("cv.texto_enriquecido",  lambda p: p["contenido_vectorial"].get("texto_enriquecido"), None),
    ("cv.tokens_clave",       lambda p: p["contenido_vectorial"].get("tokens_clave"), lambda v: isinstance(v,list) and len(v)>0),
]

print(f"\n  {'Field':<28}  {'SODIMAC':>20}  {'EASY':>20}")
print(f"  {'-'*28}  {'-'*20}  {'-'*20}")
for label, acc, extra in fields:
    sc = cover(sodimac, acc, extra)
    ec = cover(easy,    acc, extra)
    sp = f"{sc}/{len(sodimac)} ({100*sc/len(sodimac):.0f}%)"
    ep = f"{ec}/{len(easy)} ({100*ec/len(easy):.0f}%)"
    print(f"  {label:<28}  {sp:>20}  {ep:>20}")

# ─── section 3: data quality for matching ───────────────────────────────────

print("\n")
print("=" * 70)
print("  SECTION 3 — DATA QUALITY FOR MATCHING")
print("=" * 70)

for name, prods in stores.items():
    total = len(prods)
    print(f"\n  --- {name.upper()} ---")

    # titulo
    titulos = [p["metadata_basica"].get("titulo","") for p in prods if p["metadata_basica"].get("titulo")]
    all_upper  = sum(1 for t in titulos if t == t.upper())
    has_prefix = sum(1 for t in titulos if any(t.lower().startswith(x) for x in ["sodimac","easy","homecenter"]))
    avg_len    = sum(len(t) for t in titulos) / len(titulos) if titulos else 0
    print(f"    titulo — {len(titulos)} present, avg {avg_len:.0f} chars")
    print(f"      all-uppercase: {pct(all_upper, len(titulos))}")
    print(f"      store-prefixed: {pct(has_prefix, len(titulos))}")
    print(f"      samples:")
    for t in titulos[:5]:
        print(f"        '{t}'")

    # marca
    marcas = [p["metadata_basica"].get("marca","") for p in prods if p["metadata_basica"].get("marca","").strip()]
    mc = Counter(marcas)
    all_upper_b = sum(1 for m in marcas if m == m.upper())
    all_lower_b = sum(1 for m in marcas if m == m.lower())
    mixed_b     = len(marcas) - all_upper_b - all_lower_b
    print(f"\n    marca — {len(marcas)} present, {len(mc)} unique brands")
    print(f"      all-uppercase: {pct(all_upper_b, len(marcas))}")
    print(f"      all-lowercase: {pct(all_lower_b, len(marcas))}")
    print(f"      mixed-case:    {pct(mixed_b, len(marcas))}")
    print(f"      top 10 brands: {mc.most_common(10)}")

    # dimensiones type check
    lm_floats = sum(1 for p in prods if isinstance(p["metadata_tecnica"]["dimensiones"].get("largo_mm"), float))
    lm_ints   = sum(1 for p in prods if isinstance(p["metadata_tecnica"]["dimensiones"].get("largo_mm"), int))
    lm_strs   = sum(1 for p in prods if isinstance(p["metadata_tecnica"]["dimensiones"].get("largo_mm"), str))
    lm_none   = sum(1 for p in prods if p["metadata_tecnica"]["dimensiones"].get("largo_mm") is None)
    dm_floats = sum(1 for p in prods if isinstance(p["metadata_tecnica"]["dimensiones"].get("diametro_mm"), float))
    dm_ints   = sum(1 for p in prods if isinstance(p["metadata_tecnica"]["dimensiones"].get("diametro_mm"), int))
    dm_strs   = sum(1 for p in prods if isinstance(p["metadata_tecnica"]["dimensiones"].get("diametro_mm"), str))
    dm_none   = sum(1 for p in prods if p["metadata_tecnica"]["dimensiones"].get("diametro_mm") is None)
    print(f"\n    largo_mm   types — float:{lm_floats}  int:{lm_ints}  str:{lm_strs}  None:{lm_none}")
    print(f"    diametro_mm types — float:{dm_floats}  int:{dm_ints}  str:{dm_strs}  None:{dm_none}")
    has_any_dim = sum(1 for p in prods
                      if p["metadata_tecnica"]["dimensiones"].get("largo_mm") is not None
                      or p["metadata_tecnica"]["dimensiones"].get("diametro_mm") is not None)
    print(f"    products with >=1 parsed dimension: {pct(has_any_dim, total)}")
    dim_samples = [(p["metadata_tecnica"]["dimensiones"].get("largo_mm"),
                    p["metadata_tecnica"]["dimensiones"].get("diametro_mm"),
                    p["metadata_tecnica"]["dimensiones"].get("medida_cruda"))
                   for p in prods if p["metadata_tecnica"]["dimensiones"].get("largo_mm") is not None
                      or p["metadata_tecnica"]["dimensiones"].get("medida_cruda")]
    print(f"    sample filled dims: {dim_samples[:6]}")

    # material
    mats = [p["metadata_tecnica"].get("material","") for p in prods if p["metadata_tecnica"].get("material","").strip()]
    mc2 = Counter(mats)
    print(f"\n    material — {len(mats)} present, {len(mc2)} unique")
    print(f"      top values: {mc2.most_common(8)}")

    for field in ["tipo_cabeza","tipo_rosca","tipo_punta"]:
        vals = [p["metadata_tecnica"].get(field) for p in prods if p["metadata_tecnica"].get(field)]
        vc = Counter(vals)
        print(f"    {field:<14} — {len(vals)} present, {len(vc)} unique: {vc.most_common(5)}")

    # texto_enriquecido quality
    texts = [p["contenido_vectorial"].get("texto_enriquecido","") for p in prods
             if p["contenido_vectorial"].get("texto_enriquecido","").strip()]
    just_title = sum(1 for t,p in zip(texts, prods)
                     if t == p["metadata_basica"].get("titulo",""))
    avg_tlen = sum(len(t) for t in texts) / len(texts) if texts else 0
    print(f"\n    texto_enriquecido — {len(texts)} present, avg {avg_tlen:.0f} chars")
    print(f"      identical to titulo: {pct(just_title, len(texts))}")
    for t in texts[:3]:
        print(f"      SAMPLE: '{t[:130]}'")

    # tokens_clave
    toks = [p["contenido_vectorial"].get("tokens_clave",[]) for p in prods]
    filled_toks = [t for t in toks if t]
    avg_toks = sum(len(t) for t in filled_toks) / len(filled_toks) if filled_toks else 0
    print(f"\n    tokens_clave — {len(filled_toks)}/{total} non-empty, avg {avg_toks:.1f} tokens")
    print(f"      sample: {filled_toks[0] if filled_toks else 'N/A'}")

    # EAN
    eans = [p["metadata_basica"].get("ean") for p in prods]
    ean_filled   = [e for e in eans if e]
    ean_13_digit = [e for e in ean_filled if isinstance(e, str) and len(e) == 13 and e.isdigit()]
    ean_other    = [e for e in ean_filled if e not in ean_13_digit]
    uniq_eans    = len(set(str(e) for e in ean_filled))
    print(f"\n    ean — filled: {pct(len(ean_filled), total)}, unique: {uniq_eans}")
    print(f"         valid EAN-13 (13 digits): {len(ean_13_digit)}")
    print(f"         other format: {len(ean_other)}")
    if ean_other:
        print(f"         sample non-EAN13: {ean_other[:5]}")

    # cantidad_empaque
    ce = [p["metadata_tecnica"].get("cantidad_empaque") for p in prods if p["metadata_tecnica"].get("cantidad_empaque") is not None]
    ce_types = Counter(type(v).__name__ for v in ce)
    ce_vals  = Counter(ce)
    print(f"\n    cantidad_empaque — {len(ce)}/{total} present, types: {dict(ce_types)}")
    print(f"      value distribution (top 8): {ce_vals.most_common(8)}")

    # categorias
    all_cats = []
    for p in prods:
        cats = p["metadata_basica"].get("categorias", [])
        if isinstance(cats, list):
            all_cats.extend(cats)
    cat_counter = Counter(all_cats)
    print(f"\n    categorias — {len(cat_counter)} unique categories across all products")
    print(f"      top 12: {cat_counter.most_common(12)}")

# ─── section 4: sample matching candidates ──────────────────────────────────

print("\n")
print("=" * 70)
print("  SECTION 4 — SAMPLE MATCHING CANDIDATES")
print("=" * 70)

MATCH_KW = {"tornillo","perno","tuerca","taco","ancla","clavo",
            "bulon","bulón","rosca","esparrago","espárrago","arandela"}

def is_candidate(p):
    titulo = p["metadata_basica"].get("titulo","").lower()
    cats   = " ".join(p["metadata_basica"].get("categorias",[]) or []).lower()
    return any(kw in (titulo+" "+cats) for kw in MATCH_KW)

for name, prods in stores.items():
    candidates = [p for p in prods if is_candidate(p)]
    print(f"\n  {name.upper()} — {len(candidates)}/{len(prods)} matching candidates")
    for i, p in enumerate(candidates[:3], 1):
        mb  = p["metadata_basica"]
        mt  = p["metadata_tecnica"]
        dim = mt.get("dimensiones", {})
        cv  = p.get("contenido_vectorial", {})
        print(f"\n    [{i}] {p.get('id_producto','?')}")
        print(f"        titulo:          {mb.get('titulo','')}")
        print(f"        marca:           {mb.get('marca','')}")
        print(f"        precio_clp:      {mb.get('precio_clp','')}")
        print(f"        ean:             {mb.get('ean','')}")
        print(f"        material:        {mt.get('material','')}")
        print(f"        tipo_cabeza:     {mt.get('tipo_cabeza','')}")
        print(f"        tipo_rosca:      {mt.get('tipo_rosca','')}")
        print(f"        largo_mm:        {dim.get('largo_mm','')}")
        print(f"        diametro_mm:     {dim.get('diametro_mm','')}")
        print(f"        medida_cruda:    {dim.get('medida_cruda','')}")
        print(f"        cantidad_empaque:{mt.get('cantidad_empaque','')}")
        print(f"        categorias:      {mb.get('categorias','')}")
        txt = str(cv.get('texto_enriquecido',''))
        print(f"        texto_enr:       '{txt[:120]}'")
        print(f"        tokens:          {cv.get('tokens_clave','')[:8]}")

# ─── section 5: cross-store gaps ────────────────────────────────────────────

print("\n")
print("=" * 70)
print("  SECTION 5 — GAPS & CROSS-STORE PROBLEMS")
print("=" * 70)

# brand overlap
sod_brands = set(p["metadata_basica"].get("marca","").strip().lower()
                 for p in sodimac if p["metadata_basica"].get("marca","").strip())
eas_brands = set(p["metadata_basica"].get("marca","").strip().lower()
                 for p in easy if p["metadata_basica"].get("marca","").strip())
common_brands = sod_brands & eas_brands
print(f"\n  Brand overlap (case-insensitive):")
print(f"    sodimac unique brands: {len(sod_brands)}")
print(f"    easy unique brands:    {len(eas_brands)}")
print(f"    brands in BOTH:        {len(common_brands)}")
print(f"    shared sample: {sorted(common_brands)[:20]}")

# category overlap
sod_cats = set(c.strip().lower() for p in sodimac
               for c in (p["metadata_basica"].get("categorias") or []) if c)
eas_cats = set(c.strip().lower() for p in easy
               for c in (p["metadata_basica"].get("categorias") or []) if c)
common_cats = sod_cats & eas_cats
print(f"\n  Category overlap (case-insensitive):")
print(f"    sodimac unique categories: {len(sod_cats)}")
print(f"    easy unique categories:    {len(eas_cats)}")
print(f"    shared categories:         {len(common_cats)}")
print(f"    shared sample: {sorted(common_cats)[:10]}")
print(f"    sodimac-only sample:  {sorted(sod_cats - eas_cats)[:10]}")
print(f"    easy-only sample:     {sorted(eas_cats - sod_cats)[:10]}")

# texto_enriquecido == titulo?
for name, prods in stores.items():
    with_text = [(p["contenido_vectorial"].get("texto_enriquecido",""),
                  p["metadata_basica"].get("titulo","")) for p in prods
                 if p["contenido_vectorial"].get("texto_enriquecido","").strip()]
    same = sum(1 for te, ti in with_text if te == ti)
    print(f"\n  {name}: texto_enriquecido == titulo: {pct(same, len(with_text))} of filled")

# dimension coverage summary
print("\n  Dimension extraction coverage:")
for name, prods in stores.items():
    has_l  = sum(1 for p in prods if p["metadata_tecnica"]["dimensiones"].get("largo_mm") is not None)
    has_d  = sum(1 for p in prods if p["metadata_tecnica"]["dimensiones"].get("diametro_mm") is not None)
    has_mc = sum(1 for p in prods if p["metadata_tecnica"]["dimensiones"].get("medida_cruda"))
    has_both = sum(1 for p in prods
                   if p["metadata_tecnica"]["dimensiones"].get("largo_mm") is not None
                   and p["metadata_tecnica"]["dimensiones"].get("diametro_mm") is not None)
    n = len(prods)
    print(f"    {name}: largo_mm={pct(has_l,n)}  diametro_mm={pct(has_d,n)}  "
          f"medida_cruda={pct(has_mc,n)}  BOTH={pct(has_both,n)}")

# EAN cross-store overlap
sod_eans = set(str(p["metadata_basica"].get("ean","")) for p in sodimac if p["metadata_basica"].get("ean",""))
eas_eans = set(str(p["metadata_basica"].get("ean","")) for p in easy   if p["metadata_basica"].get("ean",""))
ean_overlap = sod_eans & eas_eans
print(f"\n  EAN cross-store overlap:")
print(f"    sodimac unique EANs: {len(sod_eans)}")
print(f"    easy unique EANs:    {len(eas_eans)}")
print(f"    EANs in BOTH stores: {len(ean_overlap)}")
if ean_overlap:
    print(f"    sample overlapping EANs: {sorted(ean_overlap)[:5]}")

# tokens_clave usefulness
print("\n  tokens_clave inspection:")
for name, prods in stores.items():
    all_toks = [tok for p in prods for tok in (p["contenido_vectorial"].get("tokens_clave") or [])]
    tok_counter = Counter(all_toks)
    print(f"    {name}: total tokens={len(all_toks)}, unique={len(tok_counter)}")
    print(f"      top 15: {tok_counter.most_common(15)}")

print("\n")
print("=" * 70)
print("  ANALYSIS COMPLETE")
print("=" * 70)
