"""Test the universal product validation guard."""
import sys, re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / 'backend'
sys.path.insert(0, str(BACKEND_DIR))
from agent_v3 import _ALL_PRODUCT_BRANDS_RE

# Test 1: Regex matches ALL known Ferreinox product brands
known_brands = [
    "Viniltex", "Koraza", "Intervinil", "Acriltex", "Toptex",
    "Aquablock", "Sellomax", "Sellamur", "Siliconite", "Construcleaner",
    "Pintulux", "Pintoxido", "Corrotec", "Pintuco Fill", "Pintutecho",
    "Pintutrafico", "Pintura para Canchas", "Pintura Canchas",
    "Barnex", "Wood Stain",
    "Pintucoat", "Intergard", "Interseal", "Interthane", "Intertherm", "Interfine",
    "Primer 50RS", "Primer 50 RS",
    "Altas Temperaturas", "Wash Primer",
    "Baños y Cocinas", "Ultralavable", "Doble Vida",
    "Estuco Profesional", "Estuco Prof Ext", "Estuco Multiuso",
    "Pinturama", "Epoxipoliamida",
]

print("Test 1 - All known brands detected:")
missed = []
for brand in known_brands:
    if not _ALL_PRODUCT_BRANDS_RE.search(brand):
        missed.append(brand)
if missed:
    print(f"  FAIL: missed brands: {missed}")
    assert False, f"Missed brands: {missed}"
print(f"  PASS: all {len(known_brands)} brands detected")

# Test 2: Regex does NOT match generic terms
generic_terms = [
    "pintura", "imprimante", "anticorrosivo", "sellador", "acabado",
    "sistema", "preparación", "brocha", "rodillo", "lija",
    "galón", "cuñete", "cuarto", "blanco", "gris",
]
print("\nTest 2 - Generic terms NOT matched:")
false_positives = []
for term in generic_terms:
    if _ALL_PRODUCT_BRANDS_RE.search(term):
        false_positives.append(term)
if false_positives:
    print(f"  FAIL: false positives: {false_positives}")
    assert False, f"False positives: {false_positives}"
print(f"  PASS: {len(generic_terms)} generic terms correctly ignored")

# Test 3: Product extraction from a real response
response = """¡Claro que sí! Para tu tubería galvanizada te recomiendo:
🔹 Preparación: Lijar con lija 150 y limpiar con Varsol
🔹 Promotor de adherencia: Wash Primer (obligatorio en galvanizado)
🔹 Anticorrosivo: Corrotec gris
🔹 Acabado: Pintulux 3 en 1 blanco
"""
products = set()
for match in _ALL_PRODUCT_BRANDS_RE.finditer(response):
    products.add(match.group(0).lower().strip())
print(f"\nTest 3 - Product extraction from response:")
print(f"  Found: {products}")
assert "wash primer" in products, "Should detect Wash Primer"
assert "corrotec" in products, "Should detect Corrotec"
assert "pintulux" in products, "Should detect Pintulux"
print("  PASS")

# Test 4: Negated mentions shouldn't be stripped by the guard logic
response_negated = "NO uses Koraza en interiores. NO apliques Altas Temperaturas 905 aquí."
products_negated = set()
for match in _ALL_PRODUCT_BRANDS_RE.finditer(response_negated):
    products_negated.add(match.group(0).lower().strip())
print(f"\nTest 4 - Negated mentions detected (guard will skip them):")
print(f"  Found: {products_negated}")
assert "koraza" in products_negated, "Should still detect Koraza (guard handles negation)"
assert "altas temperaturas" in products_negated, "Should still detect Altas Temperaturas"
print("  PASS (negation handling is in the guard function, not the regex)")

# Test 5: Cross-reference simulation
tool_result_text = "viniltex baños y cocinas blanco galón referencia 12345 lavable antihongos"
unsupported = []
for product in ["viniltex", "baños y cocinas", "koraza"]:
    if product not in tool_result_text:
        unsupported.append(product)
print(f"\nTest 5 - Cross-reference simulation:")
print(f"  Tool result: '{tool_result_text[:60]}...'")
print(f"  Unsupported: {unsupported}")
assert "koraza" in unsupported, "Koraza not in tool results → unsupported"
assert "viniltex" not in unsupported, "Viniltex IS in tool results → supported"
assert "baños y cocinas" not in unsupported, "Baños y Cocinas IS in tool results → supported"
print("  PASS")

# Test 6: Comprehensive coverage — test with a response that has ALL common hallucinations
hallucinated_response = "Usa Altas Temperaturas 905 para la tubería, Koraza para el interior, y Viniltex Advanced."
products_found = set()
for match in _ALL_PRODUCT_BRANDS_RE.finditer(hallucinated_response):
    products_found.add(match.group(0).lower().strip())
print(f"\nTest 6 - All hallucinations detected:")
print(f"  Found: {products_found}")
assert "altas temperaturas" in products_found
assert "koraza" in products_found
assert "viniltex" in products_found
print("  PASS")

print("\n\nALL TESTS PASSED ✅")
