"""Quick test of the new diagnostic fixes."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / 'backend'
sys.path.insert(0, str(BACKEND_DIR))
from agent_context import extract_diagnostic_data, classify_intent, is_diagnostic_incomplete

# Test 1: Galvanized pipe - surface should be 'metal', not 'techo'
msg1 = 'Hicimos un techo con tubería galvanizada nueva y el soldador le aplicó esmalte directo pero se está descascarando todo'
d1 = extract_diagnostic_data(msg1, [])
print(f"Test 1 - Galvanized pipe:")
print(f"  surface={d1['surface']} (expected: metal)")
print(f"  condition={d1['condition']}")
assert d1['surface'] == 'metal', f"FAIL: got {d1['surface']}"

# Test 2: Bathroom with mold - should detect interior + condensation
msg2 = 'Las paredes del baño están negras de moho por el vapor de la ducha'
d2 = extract_diagnostic_data(msg2, [])
print(f"\nTest 2 - Bathroom mold:")
print(f"  surface={d2['surface']} (expected: interior húmedo)")
print(f"  condition={d2['condition']} (expected: moho/hongos)")
print(f"  interior_exterior={d2['interior_exterior']} (expected: interior)")
print(f"  humidity_source={d2['humidity_source']} (expected: condensación)")
assert d2['surface'] == 'interior húmedo', f"FAIL: got {d2['surface']}"
assert d2['interior_exterior'] == 'interior', f"FAIL: got {d2['interior_exterior']}"
assert 'condensación' in (d2['humidity_source'] or ''), f"FAIL: got {d2['humidity_source']}"

# Test 3: Bathroom intent should be asesoria
intent2 = classify_intent(msg2, {}, [], {})
print(f"\nTest 3 - Bathroom intent: {intent2} (expected: asesoria)")
assert intent2 == 'asesoria', f"FAIL: got {intent2}"

# Test 4: Bathroom diagnostic should NOT be incomplete
blocked2 = is_diagnostic_incomplete(intent2, d2)
print(f"  diagnostic blocked: {blocked2} (expected: False)")
assert not blocked2, f"FAIL: should not be blocked"

# Test 5: Galvanized intent should be asesoria
intent1 = classify_intent(msg1, {}, [], {})
print(f"\nTest 5 - Pipe intent: {intent1} (expected: asesoria)")
assert intent1 == 'asesoria', f"FAIL: got {intent1}"

# Test 6: Interior húmedo exempt from interior_exterior requirement
d6 = {'surface': 'interior húmedo', 'condition': 'moho/hongos', 'interior_exterior': None, 'humidity_source': 'condensación/vapor'}
blocked6 = is_diagnostic_incomplete('asesoria', d6)
print(f"\nTest 6 - Interior húmedo exempt:")
print(f"  blocked={blocked6} (expected: False)")
assert not blocked6, f"FAIL: should not be blocked"

# Test 7: Galvanized with full context → should NOT block
msg1b = 'interior'  # follow-up
d1b = extract_diagnostic_data(msg1b, [{"direction": "inbound", "contenido": msg1}])
print(f"\nTest 7 - Galvanized with follow-up 'interior':")
print(f"  surface={d1b['surface']}, ie={d1b['interior_exterior']}, cond={d1b['condition']}")
blocked1b = is_diagnostic_incomplete('asesoria', d1b)
print(f"  blocked={blocked1b} (expected: False - all data present)")

# Test 8: Regular techo without galvanized signals → should stay as 'techo'
msg8 = 'El techo de mi casa tiene goteras'
d8 = extract_diagnostic_data(msg8, [])
print(f"\nTest 8 - Regular techo:")
print(f"  surface={d8['surface']} (expected: techo)")
assert d8['surface'] == 'techo', f"FAIL: got {d8['surface']}"

# Test 9: Condition + surface → asesoria (not product inquiry)
msg9 = 'Tengo una reja oxidada qué le echo'
intent9 = classify_intent(msg9, {}, [], {})
print(f"\nTest 9 - Reja oxidada intent: {intent9} (expected: asesoria)")
assert intent9 == 'asesoria', f"FAIL: got {intent9}"

print("\n\nALL TESTS PASSED ✅")
