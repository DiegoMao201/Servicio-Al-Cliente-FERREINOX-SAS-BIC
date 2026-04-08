"""Quick RAG spot tests for the WARN/FAIL cases."""
import sys, requests, time
sys.stdout.reconfigure(encoding='utf-8')

BACKEND_URL = 'https://apicrm.datovatenexuspro.com'
ADMIN_KEY = 'ferreinox_admin_2024'
RAG_URL = f'{BACKEND_URL}/admin/rag-buscar'

tests = [
    ('con que lijo una pared pintada antes de repintar', ['viniltex','imprimante','estuco'], [], 'abrasivo'),
    ('la casa se esta cayendo a pedazos por el aguacero', ['koraza'], [], 'jerga'),
    ('esa reja ya esta muy fea como la recupero', ['corrotec','pintoxido'], [], 'jerga'),
    ('el hierro se lo esta comiendo el oxido', ['corrotec','pintoxido'], [], 'jerga'),
    ('pergola de madera al aire libre se deteriora', ['barnex','wood stain'], ['koraza'], 'madera'),
    ('barniz para mueble interior que se vea la veta', ['pintulac','barniz'], [], 'madera'),
    ('estructura de acero nueva sin pintar a la intemperie', ['corrotec','wash primer'], [], 'metal'),
    ('tubo galvanizado nuevo como pintarlo', ['wash primer','corrotec'], [], 'metal'),
    ('qué le echo al piso del parqueadero para que quede bonito', ['pintucoat','pintura canchas'], [], 'jerga'),
]

def norm(s):
    return (s.lower()
            .replace('\u00e1','a').replace('\u00e9','e').replace('\u00ed','i')
            .replace('\u00f3','o').replace('\u00fa','u').replace('\u00f1','n'))

print('RAG Spot Tests')
fail = 0
warn = 0
ok = 0
for query, expected, forbidden, cat in tests:
    try:
        r = requests.get(RAG_URL, params={'q': query, 'top_k': 6},
                         headers={'x-admin-key': ADMIN_KEY}, timeout=30)
        d = r.json()
        cands = d.get('productos_candidatos', [])
        all_text = ' '.join(norm(c) for c in cands)
        found = [e for e in expected if norm(e) in all_text]
        missed = [e for e in expected if norm(e) not in all_text]
        forb_found = [f for f in forbidden if norm(f) in all_text]
        if forb_found:
            status = 'FAIL'; fail += 1
        elif missed and found:
            status = 'WARN'; warn += 1
        elif missed:
            status = 'FAIL'; fail += 1
        else:
            status = 'PASS'; ok += 1
        print(f'[{status}] {cat}: {query[:55]}')
        if missed:
            print(f'  MISSING: {missed}')
        if forb_found:
            print(f'  FORBIDDEN: {forb_found}')
        print(f'  Cands: {cands[:4]}')
    except Exception as e:
        print(f'[ERROR] {query[:40]} => {e}')
        fail += 1
    time.sleep(0.3)

print(f'\nTOTAL: PASS={ok} WARN={warn} FAIL={fail}')
