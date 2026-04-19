from tests.regression.test_name_confirm import *
for t in ['como puedo pagar en linea', 'necesito tubos', '12345']:
    r = is_name_confirmation_response(t)
    print(f'  "{t}" -> {r}', 'OK' if r is None else 'FAIL')
