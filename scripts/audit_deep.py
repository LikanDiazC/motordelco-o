import re, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Load sodimac profundo, find SKU 110295767
sp = json.load(open(r'C:\Users\Administrator\Documents\Buscop\motordelco-o\data\sodimac\catalogo_profundo.json', encoding='utf-8'))
items = sp if isinstance(sp, list) else list(sp.values())
target = [x for x in items if x.get('sku') == '110295767']
print("SODIMAC 110295767 in profundo:", len(target))
if target:
    p = target[0]
    print("keys:", list(p.keys()))
    print("titulo:", p.get('titulo'))
    print("marca:", p.get('marca'))
    print("precio:", p.get('precio_clp'))
    print("url_imagen:", p.get('url_imagen'))
    print("categorias:", p.get('categorias'))
    print("specs_keys:", list((p.get('especificaciones') or {}).keys()))
    print("specs_sample:", dict(list((p.get('especificaciones') or {}).items())[:8]))
    print("descripcion_len:", len((p.get('descripcion') or '')))
    print("descripcion_head:", (p.get('descripcion') or '')[:250])
else:
    # maybe stored under 110294025
    target2 = [x for x in items if x.get('sku') == '110294025']
    print("110294025:", len(target2), target2[0].get('titulo') if target2 else None)

# Easy profundo 239138 -> deep look
ep = json.load(open(r'C:\Users\Administrator\Documents\Buscop\motordelco-o\data\easy\catalogo_profundo.json', encoding='utf-8'))
eitems = ep if isinstance(ep, list) else list(ep.values())
e239 = [x for x in eitems if x.get('sku') == '239138']
if e239:
    p = e239[0]
    print("\n--- EASY 239138 profundo ---")
    print("categorias:", p.get('categorias'))
    print("url_imagen:", p.get('url_imagen'))
    desc = p.get('descripcion_completa') or ''
    print("descripcion_completa len:", len(desc))
    print("head:", desc[:200])
    print("especificaciones keys count:", len(p.get('especificaciones') or {}))

# Scan HTML for specific nearby content
def read(p): return open(p, encoding='utf-8', errors='ignore').read()

s2 = read(r'C:\Users\Administrator\Downloads\sodimac2.txt')
# breadcrumb items
bc_items = re.findall(r'"@type"\s*:\s*"ListItem"[^{}]*?"name"\s*:\s*"([^"]+)"', s2)
print("\nSodimac2 BreadcrumbList items:", bc_items[:12])

# Specifications key-value pairs inside JSON
specs_all = re.findall(r'"specifications"\s*:\s*(\[.*?\])', s2)
if specs_all:
    try:
        arr = json.loads(specs_all[0])
        print("specifications[0] length:", len(arr))
        for it in arr[:15]:
            print("  ", it)
    except Exception as ex:
        print("err parse specs:", ex, specs_all[0][:200])

# property-name spans
prop_names = re.findall(r'property-name[^>]*>([^<]+)<', s2)
prop_vals  = re.findall(r'property-value[^>]*>([^<]+)<', s2)
print("HTML property-name rows:", len(prop_names), prop_names[:20])
print("HTML property-value rows:", len(prop_vals), prop_vals[:20])

# Images galleries
imgs = re.findall(r'https://media\.sodimac\.cl/(?:sodimacCL|falabellaCL)/\d+[_\-][^"\s?\']+', s2)
uniq = sorted({re.sub(r'width=.*','',u) for u in imgs})
print("\nsodimac2 unique media image bases:", len(uniq), uniq[:6])

# Precio normal / precio internet
prices = re.findall(r'"(?:priceList|listPrice|normalPrice|internetPrice|cmrPrice|crossedOutPrice|lowPrice|highPrice|offerPrice|oldPrice)"\s*:\s*"?([0-9.,]+)', s2)
print("price variants in sodimac2:", prices[:10])
# Labels
price_lbls = re.findall(r'"prices"\s*:\s*(\[.{0,400}?\])', s2)
print("prices block sample:", price_lbls[:1])

# Sodimac1 - short desc on listing?
s1 = read(r'C:\Users\Administrator\Downloads\sodimac1.txt')
short = re.findall(r'"productDescription"\s*:\s*"([^"]{0,200})', s1) or re.findall(r'"description"\s*:\s*"([^"]{0,160})', s1)
print("\nsodimac1 short descriptions sample:", short[:5])
# ratings in listing
rats = re.findall(r'"ratingValue"\s*:\s*"?([0-9.]+)', s1)
revs = re.findall(r'"reviewCount"\s*:\s*"?(\d+)', s1)
print("sodimac1 ratingValue:", rats[:10])
print("sodimac1 reviewCount:", revs[:10])

# Easy1 variants/multiple sku per product?
e1 = read(r'C:\Users\Administrator\Downloads\easy1.txt')
variants_sample = re.findall(r'"variants"\s*:\s*(\[.{0,500}?\])', e1)
print("\neasy1 variants sample:", variants_sample[:1])

# Easy2 ratings
e2 = read(r'C:\Users\Administrator\Downloads\easy2.txt')
rat_e = re.findall(r'"ratingValue"\s*:\s*"?([0-9.]+)', e2)
rev_e = re.findall(r'"reviewCount"\s*:\s*"?(\d+)', e2)
print("easy2 ratings:", rat_e[:5], "reviews:", rev_e[:5])
bc_e = re.findall(r'"@type"\s*:\s*"ListItem"[^{}]*?"name"\s*:\s*"([^"]+)"', e2)
print("easy2 breadcrumb items:", bc_e[:10])
# Additional images in easy2
eimgs = re.findall(r'easycl\.vteximg\.com\.br/arquivos/ids/(\d+)[^"\s]*?([0-9]{4,})-?(\d+)?', e2)
# Better: just find distinct image URLs for product 239138
e2_imgs = re.findall(r'https://easycl\.vteximg\.com\.br/arquivos/ids/\d+[^"\s<>]*?239138[^"\s<>]*\.(?:jpg|png|jpeg|webp)[^"\s<>]*', e2)
print("easy2 images for 239138 (unique):", len(set(e2_imgs)), list(set(e2_imgs))[:6])
# Meta-description (short desc for listing)
meta = re.findall(r'"metaTagDescription"\s*:\s*"([^"]{0,200})', e2)
print("easy2 metaTagDescription:", meta[:2])

# Brand descriptions / SKU references keys in HTML JSON
keys_in = re.findall(r'"(productId|productName|brand|linkText|productReference|productTitle|categoryId|categories|Specifications|items|sellers)"\s*:', e2)
from collections import Counter
print("easy2 HTML common JSON keys counts:", Counter(keys_in).most_common(10))
