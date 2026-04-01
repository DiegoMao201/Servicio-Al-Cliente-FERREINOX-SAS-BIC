import sys; sys.path.insert(0, 'backend')
from main import (
    format_draft_conversational,
    try_resolve_ambiguous_with_clarification,
)

# Test conversational format
print("=== Conversational Format ===\n")

# Test with all matched items
items_matched = [
    {"status": "matched", "original_text": "cunetes de estuco",
     "matched_product": {"descripcion": "ESTUCOMAST BLANCO 18070 18.93L 27K"},
     "product_request": {"requested_quantity": 2, "requested_unit": "cuñete"},
     "alternatives": []},
    {"status": "matched", "original_text": "viniltex blanco",
     "matched_product": {"descripcion": "VINILTEX BLANCO 1501"},
     "product_request": {"requested_quantity": 3, "requested_unit": "galon"},
     "alternatives": []},
]
text, needs = format_draft_conversational(items_matched)
print(f"All matched:\n{text}\n(needs_input={needs})\n")

# Test with ambiguous items
items_mixed = [
    {"status": "matched", "original_text": "viniltex blanco",
     "matched_product": {"descripcion": "VINILTEX BLANCO 1501"},
     "product_request": {"requested_quantity": 3, "requested_unit": "galon"},
     "alternatives": []},
    {"status": "ambiguous", "original_text": "domestico blanco",
     "matched_product": None,
     "product_request": {"core_terms": ["domestico", "blanco"]},
     "alternatives": [
         {"commercial_name": "Domestico Blanco P-11 en galón", "referencia": "P11"},
         {"commercial_name": "Domestico Blanco 6W en cuarto", "referencia": "6W"},
     ]},
    {"status": "missing", "original_text": "pegante xyz",
     "matched_product": None,
     "product_request": {"core_terms": ["pegante", "xyz"]},
     "alternatives": []},
]
text, needs = format_draft_conversational(items_mixed)
print(f"Mixed:\n{text}\n(needs_input={needs})\n")

# Test clarification matching
print("=== Clarification Matching ===\n")

existing_items = [
    {"status": "matched", "original_text": "viniltex blanco",
     "matched_product": {"descripcion": "VINILTEX BLANCO 1501"},
     "product_request": {"core_terms": ["viniltex", "blanco"]},
     "alternatives": []},
    {"status": "ambiguous", "original_text": "domestico blanco",
     "matched_product": None,
     "product_request": {"core_terms": ["domestico", "blanco"]},
     "alternatives": [
         {"commercial_name": "Domestico Blanco P-11 en galon", "referencia": "P11"},
         {"commercial_name": "Domestico Blanco 6W en cuarto", "referencia": "6W"},
     ]},
]

# "domestico blanco p-11" should match item 1 (the ambiguous one)
idx = try_resolve_ambiguous_with_clarification("domestico blanco p-11", existing_items, [], "pedido")
print(f'"domestico blanco p-11" -> matched index {idx}', "OK" if idx == 1 else "FAIL")

# "viniltex rojo" should NOT match any ambiguous (item 0 is matched, not ambiguous)
idx = try_resolve_ambiguous_with_clarification("viniltex rojo", existing_items, [], "pedido")
print(f'"viniltex rojo" -> matched index {idx}', "OK" if idx is None else "FAIL")

# "el p-11" should match the ambiguous item because p-11 is in an alternative name
idx = try_resolve_ambiguous_with_clarification("el p-11", existing_items, [], "pedido")
print(f'"el p-11" -> matched index {idx}', "OK" if idx == 1 else f"FAIL (got {idx})")
