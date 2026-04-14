import json, glob
files = sorted(glob.glob('guias_solucion_seccion_*.json'))
total = 0
for f in files:
    data = json.load(open(f, encoding='utf-8'))
    n = len(data)
    total += n
    ids = [g['id'] for g in data]
    print(f"{f}: {n} guias ({ids[0]}..{ids[-1]})")
print(f"\nTOTAL: {total} guias de solucion")
