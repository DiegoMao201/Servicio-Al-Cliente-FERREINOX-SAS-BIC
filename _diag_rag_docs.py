"""Check what RAG documents exist for fachada/humedad products"""
import sys, os
os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))
sys.path.insert(0, '.')
from main import get_db_engine
from sqlalchemy import text
engine = get_db_engine()
with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT DISTINCT doc_filename, marca, familia_producto, tipo_documento,
               COUNT(*) as chunks,
               ROUND(AVG(token_count)::numeric, 0) as avg_tokens
        FROM public.agent_technical_doc_chunk
        WHERE LOWER(doc_filename) LIKE ANY(ARRAY[
            '%%koraza%%', '%%aquablock%%', '%%estuco%%', '%%fachada%%',
            '%%humedad%%', '%%impermeab%%', '%%viniltex%%'
        ])
        GROUP BY doc_filename, marca, familia_producto, tipo_documento
        ORDER BY doc_filename
    """)).mappings().all()
    for r in rows:
        fn = r["doc_filename"]
        marca = r["marca"] or ""
        fam = r["familia_producto"] or ""
        tipo = r["tipo_documento"] or ""
        ch = r["chunks"]
        tok = r["avg_tokens"]
        print(f"  {fn}")
        print(f"    marca={marca} | familia={fam} | tipo={tipo} | chunks={ch} | avg_tok={tok}")
    print(f"\nTotal: {len(rows)} documents")

    # Also check what profiles exist
    print("\n" + "="*60)
    print("TECHNICAL PROFILES for fachada/humedad products:")
    print("="*60)
    profiles = conn.execute(text("""
        SELECT canonical_family, marca, completeness_score, extraction_status,
               source_doc_filename
        FROM public.agent_technical_profile
        WHERE LOWER(canonical_family) LIKE ANY(ARRAY[
            '%%koraza%%', '%%aquablock%%', '%%estuco%%', '%%fachada%%',
            '%%humedad%%', '%%impermeab%%', '%%viniltex%%'
        ])
        ORDER BY canonical_family
    """)).mappings().all()
    for p in profiles:
        cf = p["canonical_family"]
        marca = p["marca"] or ""
        score = p["completeness_score"]
        status = p["extraction_status"]
        src = p["source_doc_filename"] or ""
        print(f"  {cf} | marca={marca} | score={score} | status={status}")
        print(f"    source: {src}")
