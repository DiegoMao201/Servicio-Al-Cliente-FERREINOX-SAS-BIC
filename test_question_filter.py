import sys; sys.path.insert(0, 'backend')
from main import extract_identity_lookup_candidate

ctx_awaiting = {"awaiting_verification": True}
ctx_normal = {}

# "como puedo pagar en linea" should NOT be treated as name lookup
result = extract_identity_lookup_candidate("como puedo pagar en linea", ctx_awaiting, allow_unprompted=True)
print(f'"como puedo pagar en linea" (awaiting) -> {result}', 'OK' if result is None else 'FAIL')

# "donde puedo pagar" should NOT match
result = extract_identity_lookup_candidate("donde puedo pagar", ctx_awaiting, allow_unprompted=True)
print(f'"donde puedo pagar" (awaiting) -> {result}', 'OK' if result is None else 'FAIL')

# "necesito ayuda" should NOT match
result = extract_identity_lookup_candidate("necesito ayuda", ctx_awaiting, allow_unprompted=True)
print(f'"necesito ayuda" (awaiting) -> {result}', 'OK' if result is None else 'FAIL')

# A numeric cedula SHOULD still be extracted  
result = extract_identity_lookup_candidate("1088266407", ctx_awaiting, allow_unprompted=True)
print(f'"1088266407" (awaiting) -> {result}', 'OK' if result and result.get("type") == "numeric_lookup" else 'FAIL')

# A name during awaiting SHOULD still work
result = extract_identity_lookup_candidate("Juan Perez", ctx_awaiting, allow_unprompted=True)
print(f'"Juan Perez" (awaiting) -> {result}', 'OK' if result and result.get("type") == "name_lookup" else 'NOTE')
