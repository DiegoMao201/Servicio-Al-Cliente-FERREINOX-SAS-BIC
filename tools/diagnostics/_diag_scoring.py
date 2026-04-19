"""Trace expert scoring for fachada+humedad query"""
import json, sys, os, re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
os.chdir(REPO_ROOT)
sys.path.insert(0, str(BACKEND_DIR))
from main import normalize_text_value

query = "fachada humedad pintar pintura en mal estado"
normalized = normalize_text_value(query)
raw_terms = re.findall(r"[a-z0-9\xe1\xe9\xed\xf3\xfa\xf1]+", normalized)
stop_terms = {"para","con","sin","por","que","como","sobre","entre","desde","hasta","este","esta","estos","estas","solo","necesito","quiero","techo","techos","pintar","pintado","exterior","interior","anos","ano","hace","viejo","vieja","nuevo","nueva","usar","aplicar","producto","productos","sistema","recomendar","recomendacion"}
terms = [t for t in raw_terms if len(t) >= 3 and t not in stop_terms]
terms = list(dict.fromkeys(terms))
anchor_terms = [t for t in terms if len(t) >= 6 or t in {"eternit","fibrocemento","asbesto","sellomax","koraza","intervinil"}]
print(f"TERMS: {terms}")
print(f"ANCHORS: {anchor_terms}")
print()

rules = json.loads((REPO_ROOT / "reglas_experto_ferreinox.json").read_text(encoding="utf-8"))
target_ids = [6, 37, 52, 58, 63, 91, 92, 93, 94, 95, 97]
results = []
for r in rules:
    rid = r.get("id")
    if rid not in target_ids:
        continue
    ctx = normalize_text_value(r.get("contexto_tags", ""))
    nota = normalize_text_value(r.get("nota_comercial", ""))
    rec = normalize_text_value(r.get("producto_recomendado", ""))
    des = normalize_text_value(r.get("producto_desestimado", ""))
    searchable = ctx + " " + nota + " " + rec + " " + des
    matched = [t for t in terms if t in searchable]
    if not matched:
        print(f"Rule #{rid}: NO MATCH")
        continue
    score = 0.0
    ctx_hits = 0
    for t in matched:
        score += 1.0
        if t in ctx:
            score += 2.0
            ctx_hits += 1
        elif t in nota:
            score += 1.0
        elif t in rec or t in des:
            score += 0.4
        if len(t) >= 7:
            score += 0.35
    anchor_ctx = sum(1 for t in anchor_terms if t in ctx)
    if anchor_ctx:
        score += 2.5 * anchor_ctx
    elif anchor_terms:
        score -= 1.5
    if r.get("tipo") == "alerta_superficie" and ctx_hits:
        score += 1.5
    if r.get("tipo") == "evitar" and any(t in des for t in matched):
        score += 0.75
    tipo = r.get("tipo", "")
    print(f"Rule #{rid:3d} [{tipo:20s}] score={score:6.2f}  matched={matched}  ctx_hits={ctx_hits}  anchor_ctx={anchor_ctx}")
    print(f"         tags: {ctx[:80]}")
    results.append((score, rid))

print()
print("RANKING:")
results.sort(key=lambda x: -x[0])
for score, rid in results:
    marker = " <-- SHOULD BE TOP" if rid in [6, 37, 52, 58, 63] else ""
    print(f"  #{rid:3d}: {score:6.2f}{marker}")
