"""
Test: RAG semantic search quality for critical use cases.
Connects directly to DB to test what the agent would find.
"""
import os
import sys
import psycopg2

# Try to get DB URL from env or from the running server
DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    print("ERROR: Set DATABASE_URL environment variable")
    print("Example: set DATABASE_URL=postgresql://user:pass@host:port/db")
    sys.exit(1)

try:
    from openai import OpenAI
    client = OpenAI()
except Exception as e:
    print(f"ERROR: OpenAI client failed: {e}")
    sys.exit(1)

def get_embedding(text):
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding

def search_rag(query, top_k=6):
    emb = get_embedding(query)
    emb_str = "[" + ",".join(str(x) for x in emb) + "]"
    
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT doc_filename, familia_producto, chunk_text,
               1 - (embedding <=> %s::vector) AS similarity
        FROM public.agent_technical_doc_chunk
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (emb_str, emb_str, top_k))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ── Critical test cases ──
TEST_CASES = [
    {
        "query": "tengo humedad interna en los muros, se filtran las paredes por dentro",
        "expect": "Aquablock",
        "must_not": "Koraza",
    },
    {
        "query": "necesito pintar la fachada exterior de mi edificio que está deteriorada por lluvia y sol",
        "expect": "Koraza",
        "must_not": "Aquablock",
    },
    {
        "query": "necesito impermeabilizar el techo de mi casa que tiene goteras",
        "expect": "Pintuco Fill",
        "must_not": "Koraza",  
    },
    {
        "query": "tengo una reja oxidada y necesito protegerla del óxido",
        "expect": "Corrotec",
        "must_not": None,
    },
    {
        "query": "necesito pintar un piso de bodega industrial con tráfico de montacargas",
        "expect": "Pintucoat",
        "must_not": None,
    },
    {
        "query": "quiero pintar una piscina para que no se filtre el agua",
        "expect": "__NO_PRODUCT__",
        "must_not": "Pintucoat",
    },
    {
        "query": "necesito un sellador para grietas y filtraciones en muros interiores con presión de agua negativa",
        "expect": "Aquablock",
        "must_not": "Koraza",
    },
]

print("=" * 90)
print("TEST DE CALIDAD RAG: Búsqueda semántica para casos críticos")
print("=" * 90)

for i, tc in enumerate(TEST_CASES, 1):
    query = tc["query"]
    expect = tc["expect"]
    must_not = tc["must_not"]
    
    print(f"\n{'─' * 90}")
    print(f"TEST {i}: '{query}'")
    print(f"  ESPERA: {expect}")
    if must_not:
        print(f"  NO DEBE DEVOLVER: {must_not}")
    print()
    
    results = search_rag(query, top_k=6)
    
    found_expected = False
    found_forbidden = False
    
    for j, (filename, familia, chunk_text, similarity) in enumerate(results, 1):
        # Check first 200 chars of chunk
        snippet = chunk_text[:200].replace('\n', ' ').strip()
        
        if expect.upper() in (filename or "").upper() or expect.upper() in (familia or "").upper() or expect.upper() in chunk_text[:500].upper():
            found_expected = True
        if must_not and (must_not.upper() in (filename or "").upper() or must_not.upper() in (familia or "").upper()):
            found_forbidden = True
        
        sim_bar = "█" * int(similarity * 40) if similarity else ""
        print(f"  #{j} sim={similarity:.3f} {sim_bar}")
        print(f"     📄 {filename} | familia={familia}")
        print(f"     📝 {snippet}...")
        print()
    
    # Verdict
    if expect == "__NO_PRODUCT__":
        print(f"  ✅ CORRECTO" if not found_forbidden else f"  ❌ FALLÓ - devolvió {must_not}")
    elif found_expected and not found_forbidden:
        print(f"  ✅ CORRECTO - encontró {expect}")
    elif found_expected and found_forbidden:
        print(f"  ⚠️ PARCIAL - encontró {expect} pero también {must_not}")
    else:
        print(f"  ❌ FALLÓ - no encontró {expect}")

print("\n" + "=" * 90)
