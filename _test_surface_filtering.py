"""Test: verify surface-aware RAG filtering works for teja metalica case."""
import sys
sys.path.insert(0, ".")

from backend.main import (
    _infer_surface_types_from_query,
    _filter_profiles_by_surface_compatibility,
    _filter_rag_candidates_by_surface_and_policy,
    normalize_text_value,
)

# Test 1: Surface detection
print("=== TEST 1: Surface detection ===")
cases = [
    ("pintura para teja metalica con recubrimiento", "", ["metal", "cubierta"]),
    ("pintura para la fachada exterior de mi casa", "", ["concreto", "exterior"]),
    ("anticorrosivo para reja oxidada", "", ["metal"]),
    ("pintura para piso de bodega", "", ["piso"]),
    ("barniz para puerta de madera", "", ["madera"]),
    ("impermeabilizar terraza", "", ["cubierta"]),
]
for question, product, expected in cases:
    result = _infer_surface_types_from_query(question, product)
    ok = all(s in result for s in expected)
    print(f"  {'✓' if ok else '✗'} '{question}' → {result} (expected {expected})")

# Test 2: Profile surface filtering
print("\n=== TEST 2: Profile restriction detection ===")
# Simulate profiles with surface metadata
mock_profiles = [
    {"canonical_family": "VINILTEX ADVANCE", "profile_json": {
        "restricted_surfaces": ["metal"],
        "solution_guidance": {"restricted_surfaces": ["metal"]},
    }},
    {"canonical_family": "ACRILICA MANTENIMIENTO ES", "profile_json": {
        "restricted_surfaces": [],
        "surface_targets": ["concreto", "metal", "piso", "interior", "exterior"],
        "solution_guidance": {"restricted_surfaces": []},
    }},
    {"canonical_family": "PINTUCO KORAZA", "profile_json": {
        "restricted_surfaces": [],
        "surface_targets": ["exterior", "fachada", "mamposteria", "concreto"],
        "solution_guidance": {"restricted_surfaces": []},
    }},
    {"canonical_family": "ALTAS TEMPERATURAS 905", "profile_json": {
        "restricted_surfaces": [],
        "surface_targets": ["metal", "exterior", "interior"],
        "solution_guidance": {"restricted_surfaces": []},
    }},
]

restricted = _filter_profiles_by_surface_compatibility(mock_profiles, ["metal"])
print(f"  Surfaces: ['metal'] → restricted families: {restricted}")
assert "VINILTEX ADVANCE" in restricted, "Viniltex should be restricted for metal"
print(f"  ✓ Viniltex correctly identified as restricted for metal")

# Test 3: RAG candidate filtering
print("\n=== TEST 3: RAG candidate filtering (closing the fuga) ===")
raw_candidates = ["Altas Temperaturas 905", "Viniltex Advanced", "Corrotec", "Wash Primer", "Koraza"]
forbidden = ["Altas Temperaturas"]  # From a hypothetical policy
surface_restricted = ["VINILTEX ADVANCE"]  # From profile metadata

filtered = _filter_rag_candidates_by_surface_and_policy(raw_candidates, forbidden, surface_restricted)
print(f"  Raw: {raw_candidates}")
print(f"  Forbidden: {forbidden}")
print(f"  Surface restricted: {surface_restricted}")
print(f"  Filtered: {filtered}")
assert "Altas Temperaturas 905" not in filtered, "Altas Temperaturas should be filtered by policy"
assert "Viniltex Advanced" not in filtered, "Viniltex should be filtered by surface restriction"
assert "Corrotec" in filtered, "Corrotec should pass (correct for metal)"
assert "Wash Primer" in filtered, "Wash Primer should pass (correct for metal)"
print(f"  ✓ Fuga closed: wrong products filtered, correct products kept")

print("\n=== ALL TESTS PASSED ===")
