"""Diagnostic: what does RAG return for 'fachada con humedad'?"""
import json, sys, os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
os.chdir(REPO_ROOT)
sys.path.insert(0, str(BACKEND_DIR))
from main import (
    fetch_expert_knowledge,
    search_technical_chunks,
    search_supporting_technical_guides,
    normalize_text_value,
    PORTFOLIO_CATEGORY_MAP,
    _build_structured_diagnosis,
    _build_structured_technical_guide,
    _build_hard_policies_for_context,
)

SEP = "=" * 60

# 1. Expert rules
print(SEP)
print("EXPERT KNOWLEDGE: fachada humedad pintar")
print(SEP)
rules = fetch_expert_knowledge("fachada humedad pintar pintura en mal estado", limit=8)
for r in rules:
    rid = r.get("id", "?")
    tipo = r.get("tipo", "")
    tags = r.get("contexto_tags", "")[:100]
    rec = r.get("producto_recomendado", "")
    des = r.get("producto_desestimado", "")
    nota = r.get("nota_comercial", "")[:250]
    print(f"Rule #{rid} [{tipo}]: tags={tags}")
    print(f"  Recomendado: {rec}")
    if des:
        print(f"  Desestimado: {des}")
    print(f"  Nota: {nota}")
    print()

# 2. RAG chunks
print(SEP)
print("RAG CHUNKS: pintar fachada con humedad y pintura en mal estado")
print(SEP)
chunks = search_technical_chunks("pintar fachada con humedad y pintura en mal estado", top_k=6)
for i, c in enumerate(chunks):
    sim = c.get("similarity", 0)
    fname = c.get("doc_filename", "")
    family = c.get("familia_producto", "")
    text = c.get("chunk_text", "")[:300]
    print(f"Chunk {i+1}: sim={sim:.4f} file={fname} family={family}")
    print(f"  Text: {text}")
    print()

# 3. Guide chunks
print(SEP)
print("GUIDE CHUNKS")
print(SEP)
guides = search_supporting_technical_guides("pintar fachada con humedad y pintura en mal estado", top_k=3)
for i, g in enumerate(guides):
    sim = g.get("similarity", 0)
    fname = g.get("doc_filename", "")
    text = g.get("chunk_text", "")[:300]
    print(f"Guide {i+1}: sim={sim:.4f} file={fname}")
    print(f"  Text: {text}")
    print()

# 4. Portfolio map
print(SEP)
print("PORTFOLIO MAP: fachada / humedad / estuco / koraza")
print(SEP)
for key in ["fachada", "fachadas", "humedad", "humedad interna", "estuco", "koraza", "aquablock"]:
    if key in PORTFOLIO_CATEGORY_MAP:
        print(f"  {key} -> {PORTFOLIO_CATEGORY_MAP[key]}")

# 5. Structured diagnosis
print()
print(SEP)
print("STRUCTURED DIAGNOSIS")
print(SEP)
diag = _build_structured_diagnosis("pintar fachada con humedad y pintura en mal estado", "", 0.75)
print(json.dumps(diag, indent=2, ensure_ascii=False))

# 6. Structured guide
print()
print(SEP)
print("STRUCTURED GUIDE")
print(SEP)
guide = _build_structured_technical_guide(
    "pintar fachada con humedad y pintura en mal estado",
    "",
    diag,
    rules,
    0.75,
)
print(json.dumps(guide, indent=2, ensure_ascii=False))

# 7. Hard policies
print()
print(SEP)
print("HARD POLICIES")
print(SEP)
policies = _build_hard_policies_for_context(
    "pintar fachada con humedad y pintura en mal estado",
    "",
    diag,
    guide,
    rules,
)
print(json.dumps(policies, indent=2, ensure_ascii=False))
