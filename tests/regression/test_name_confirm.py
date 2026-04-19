import sys; sys.path.insert(0, 'backend')
from main import is_name_confirmation_response, build_name_confirmation_challenge

# Test name confirmation challenge
print('Challenge:', build_name_confirmation_challenge('JUANITO PEREZ'))

# Test positive responses
print('\n--- Positive ---')
for t in ['si', 'sí', 'soy yo', 'ese soy yo', 'correcto', 'dale', 'eso es', 'Si señor']:
    r = is_name_confirmation_response(t)
    print(f'  "{t}" -> {r}', 'OK' if r is True else 'FAIL')

# Test negative responses
print('\n--- Negative ---')
for t in ['no', 'nop', 'no soy yo', 'ese no es', 'negativo']:
    r = is_name_confirmation_response(t)
    print(f'  "{t}" -> {r}', 'OK' if r is False else 'FAIL')

# Test ambiguous
print('\n--- Ambiguous ---')
for t in ['como puedo pagar en linea', 'necesito tubos', '12345']:
    r = is_name_confirmation_response(t)
    print(f'  "{t}" -> {r}', 'OK' if r is None else 'FAIL')
