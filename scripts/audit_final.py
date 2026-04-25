import re, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def read(p): return open(p, encoding='utf-8', errors='ignore').read()

# Easy2: count images tied to SKU 239138 in full (all patterns)
e2 = read(r'C:\Users\Administrator\Downloads\easy2.txt')
imgs_all = re.findall(r'"(?:imageUrl|imageURL|image)"\s*:\s*"([^"]+?(?:239138|imporper)[^"]*)"', e2, re.I)
print("easy2 image fields containing 239138 or imporper:", len(imgs_all), imgs_all[:4])
# Also find all img srcs with 239138
srcs = re.findall(r'(https?://[^"\s]+?239138[^"\s]*\.(?:jpg|jpeg|png|webp))', e2, re.I)
print("easy2 all image URLs with 239138:", len(set(srcs)), list(set(srcs))[:6])
# pattern for variants ids
imgs_0002 = re.findall(r'(239138-\d{4}-\d{3}\.\w+)', e2)
print("easy2 image filename variants for 239138:", sorted(set(imgs_0002)))

# Sodimac2 full pricing block
s2 = read(r'C:\Users\Administrator\Downloads\sodimac2.txt')
blk = re.search(r'"prices"\s*:\s*(\[.{0,1500}?\]\s*[,}])', s2)
print("\nFull prices block:", blk.group(1)[:800] if blk else "NOT FOUND")

# Sodimac2 aggregateRating structure
agg = re.search(r'"aggregateRating"\s*:\s*\{[^{}]{0,400}\}', s2)
print("\naggregateRating:", agg.group(0) if agg else "NO agg")

# Sodimac2 images - different host?
img_hosts = re.findall(r'https://[^"\s]+?(?:1908766|110295767)[^"\s]*', s2)
print("\nimage URLs matching sku/1908766:", len(set(img_hosts)), list(set(img_hosts))[:6])
# look for mediaUrls field
media_urls = re.findall(r'"mediaUrls?"\s*:\s*(\[[^\]]{0,500}\])', s2)
print("mediaUrls sample:", media_urls[:1])

# Sodimac1 aggregate/ratings structure: try alternate fields
s1 = read(r'C:\Users\Administrator\Downloads\sodimac1.txt')
cand = re.findall(r'"(?:rating|avgRating|score|totalReviews|reviews|starRating)"\s*:\s*("?[0-9.]+"?|[a-z0-9\-]+)', s1, re.I)
print("\nsodimac1 rating-like fields:", cand[:15])

# Is there "discount" / "promoLabel" / "exclusividad" on listing/product?
for t, lab in [(s1,'sodimac1'),(s2,'sodimac2')]:
    disc = re.findall(r'"(?:discount|badgeLabel|eventName|promoLabel|promotionLabels?)"\s*:\s*"([^"]{0,80})', t)
    print(f"{lab} badges/discount:", list(set(disc))[:5])

# Easy1: short description per product
e1 = read(r'C:\Users\Administrator\Downloads\easy1.txt')
sc = re.findall(r'"metaTagDescription"\s*:\s*"([^"]{0,150})', e1)
print("\neasy1 metaTagDescription count:", len(sc), "sample:", sc[:2])
# Precio normal vs oferta on easy listing
price_var = re.findall(r'"(?:priceWithoutDiscount|ListPrice|Price|BestPrice|PriceWithoutDiscount)"\s*:\s*"?([0-9.]+)', e1)
print("easy1 price variants:", price_var[:12])

# Verify sodimac crudo has categorias/rating  -> already know it does not; confirm
sc_json = json.load(open(r'C:\Users\Administrator\Documents\Buscop\motordelco-o\data\sodimac\catalogo_crudo.json', encoding='utf-8'))
sc_items = sc_json if isinstance(sc_json, list) else list(sc_json.values())
print("\nsodimac crudo sample has rating?:", any('rating' in json.dumps(x,ensure_ascii=False).lower() for x in sc_items[:3]))
print("sodimac crudo keys all:", sorted({k for x in sc_items for k in x.keys()}))
# easy crudo keys
ec = json.load(open(r'C:\Users\Administrator\Documents\Buscop\motordelco-o\data\easy\catalogo_crudo.json', encoding='utf-8'))
eci = ec if isinstance(ec, list) else list(ec.values())
print("easy crudo keys all:", sorted({k for x in eci for k in x.keys()}))
