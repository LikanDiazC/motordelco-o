import re, sys, json, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def scan(path, label):
    print(f"\n=== {label} : {path} ===")
    try:
        t = open(path, encoding='utf-8', errors='ignore').read()
    except Exception as e:
        print("ERR", e); return ""
    print("LEN", len(t))
    return t

def show(label, vals, n=6):
    vs = list(vals)
    print(f"  {label}: count={len(vs)} sample={vs[:n]}")

def scan_product(t, tag):
    show("articulo_ids", re.findall(r'articulo/(\d+)/[^"?\s<>]+?/(\d+)', t))
    show("productId", re.findall(r'"productId"\s*:\s*"?(\d+)', t))
    show("skuId", re.findall(r'"skuId"\s*:\s*"?(\d+)', t))
    show("sku", re.findall(r'"sku"\s*:\s*"?([A-Z0-9\-]+)"?', t))
    show("currentProduct", re.findall(r'currentProduct["\']?\s*[:=]\s*["\']([^"\']+)', t))
    show("ean", re.findall(r'"ean"\s*:\s*"?(\d{6,})', t, re.I))
    show("gtin", re.findall(r'"gtin\d*"\s*:\s*"?(\d{6,})', t, re.I))
    show("ratingValue", re.findall(r'"ratingValue"\s*:\s*"?([0-9.]+)', t))
    show("reviewCount", re.findall(r'"reviewCount"\s*:\s*"?(\d+)', t))
    show("numReviews", re.findall(r'numReviews["\']?\s*[:=]\s*"?(\d+)', t))
    show("availability", re.findall(r'"availability"\s*:\s*"([^"]+)"', t))
    show("isAvailable", re.findall(r'isAvailable["\']?\s*[:=]\s*(true|false)', t, re.I))
    show("stock", re.findall(r'"stock(?:Quantity)?"\s*:\s*"?(\d+)', t, re.I))
    show("price", re.findall(r'"price"\s*:\s*"?([0-9.]+)', t))
    show("lowPrice", re.findall(r'"(?:lowPrice|highPrice|priceNormal|priceOffer|offerPrice|listPrice)"\s*:\s*"?([0-9.]+)', t))
    show("brand", re.findall(r'"brand"\s*:\s*(?:"([^"]+)"|{[^}]*"name"\s*:\s*"([^"]+)")', t))
    show("image_urls_media", re.findall(r'https://media\.sodimac\.cl/[^"\s<>]+', t), 4)
    show("image_urls_easy", re.findall(r'https://[a-z0-9.]+\.easy[^"\s<>]*\.(?:jpg|png|jpeg|webp)[^"\s<>]*', t, re.I), 4)
    show("vtex_img_ids", re.findall(r'arquivos/ids/(\d+)', t), 6)
    show("BreadcrumbList", re.findall(r'"BreadcrumbList"|breadcrumb|Breadcrumb', t), 3)
    show("spec_property_name", re.findall(r'"property-name"', t))
    show("spec_property_value", re.findall(r'"property-value"', t))
    show("specification-table", re.findall(r'specification-table', t))
    show("specifications_block", re.findall(r'"specifications"\s*:\s*\[', t))
    show("variants", re.findall(r'"variants?"\s*:\s*\[|variationsGroup|colorVariant', t))
    show("meta_description", re.findall(r'<meta[^>]+name="description"[^>]+content="([^"]{0,120})', t), 2)
    show("short_desc", re.findall(r'"shortDescription"\s*:\s*"([^"]{0,120})', t), 2)
    show("desc_prod", re.findall(r'"productDescription"\s*:\s*"([^"]{0,120})', t), 2)

# HTMLs
paths = {
    "easy1": r"C:\Users\Administrator\Downloads\easy1.txt",
    "easy2": r"C:\Users\Administrator\Downloads\easy2.txt",
    "sodimac1": r"C:\Users\Administrator\Downloads\sodimac1.txt",
    "sodimac2": r"C:\Users\Administrator\Downloads\sodimac2.txt",
}

for k, p in paths.items():
    t = scan(p, k)
    if t:
        scan_product(t, k)
