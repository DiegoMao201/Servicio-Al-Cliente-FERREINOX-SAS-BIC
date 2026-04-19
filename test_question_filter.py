from tests.regression.test_question_filter import *
print(f'"1088266407" (awaiting) -> {result}', 'OK' if result and result.get("type") == "numeric_lookup" else 'FAIL')

# A name during awaiting SHOULD still work
result = extract_identity_lookup_candidate("Juan Perez", ctx_awaiting, allow_unprompted=True)
print(f'"Juan Perez" (awaiting) -> {result}', 'OK' if result and result.get("type") == "name_lookup" else 'NOTE')
