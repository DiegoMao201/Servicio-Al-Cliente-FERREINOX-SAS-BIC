"""Quick RAG audit: check diagnostic completeness."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from main import get_db_engine

engine = get_db_engine()
conn = engine.raw_connection()
cur = conn.cursor()

# Count technical profiles
cur.execute("SELECT COUNT(1) FROM agent_technical_profile")
profiles = cur.fetchone()[0]
print(f"Technical profiles: {profiles}")

# Count technical chunks
cur.execute("SELECT COUNT(1) FROM agent_technical_doc_chunk")
chunks = cur.fetchone()[0]
print(f"Technical chunks: {chunks}")

# Check guide-type docs
cur.execute("SELECT tipo_documento, COUNT(1) FROM agent_technical_profile GROUP BY tipo_documento ORDER BY COUNT(1) DESC")
print("\nProfiles by tipo_documento:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Check profiles with diagnostic_questions
cur.execute("SELECT COUNT(1) FROM agent_technical_profile WHERE profile_json::text LIKE '%diagnostic_questions%'")
diag = cur.fetchone()[0]
print(f"\nProfiles with diagnostic_questions: {diag}")

# Check profiles with surface_targets
cur.execute("SELECT COUNT(1) FROM agent_technical_profile WHERE profile_json::text LIKE '%surface_targets%'")
surf = cur.fetchone()[0]
print(f"Profiles with surface_targets: {surf}")

# Sample: piso-related profiles
cur.execute("""
    SELECT canonical_family, tipo_documento 
    FROM agent_technical_profile 
    WHERE profile_json::text ILIKE '%piso%' 
       OR canonical_family ILIKE '%piso%' 
       OR canonical_family ILIKE '%pintucoat%' 
       OR canonical_family ILIKE '%intergard%'
       OR canonical_family ILIKE '%interseal%'
    LIMIT 20
""")
print(f"\nPiso-related profiles:")
for row in cur.fetchall():
    print(f"  {row[0]} ({row[1]})")

# Sample: guide/solution docs
cur.execute("""
    SELECT canonical_family, tipo_documento 
    FROM agent_technical_profile 
    WHERE tipo_documento IN ('guia_tecnica', 'guia_aplicacion', 'guia_soluciones', 'manual_aplicacion', 'catalogo')
    LIMIT 20
""")
print(f"\nGuide/solution documents:")
for row in cur.fetchall():
    print(f"  {row[0]} ({row[1]})")

# Check a specific Pintucoat profile for diagnostic detail
cur.execute("""
    SELECT profile_json 
    FROM agent_technical_profile 
    WHERE canonical_family ILIKE '%pintucoat%' 
    LIMIT 1
""")
row = cur.fetchone()
if row:
    profile = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    print(f"\n=== PINTUCOAT PROFILE ===")
    print(f"  surfaces: {profile.get('product_identity', {}).get('surface_targets', [])}")
    print(f"  diagnostic_questions: {profile.get('diagnostic_questions', [])}")
    print(f"  alerts: {profile.get('alerts', [])}")
    print(f"  restricted_surfaces: {profile.get('product_identity', {}).get('restricted_surfaces', [])}")

# Check Intergard 2002 profile
cur.execute("""
    SELECT profile_json 
    FROM agent_technical_profile 
    WHERE canonical_family ILIKE '%intergard 2002%' 
    LIMIT 1
""")
row = cur.fetchone()
if row:
    profile = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    print(f"\n=== INTERGARD 2002 PROFILE ===")
    print(f"  surfaces: {profile.get('product_identity', {}).get('surface_targets', [])}")
    print(f"  diagnostic_questions: {profile.get('diagnostic_questions', [])}")
    print(f"  restricted_surfaces: {profile.get('product_identity', {}).get('restricted_surfaces', [])}")

# Check Viniltex profile — should NOT have piso
cur.execute("""
    SELECT profile_json 
    FROM agent_technical_profile 
    WHERE canonical_family ILIKE '%viniltex%' 
    LIMIT 1
""")
row = cur.fetchone()
if row:
    profile = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    print(f"\n=== VINILTEX PROFILE ===")
    print(f"  surfaces: {profile.get('product_identity', {}).get('surface_targets', [])}")
    print(f"  restricted_surfaces: {profile.get('product_identity', {}).get('restricted_surfaces', [])}")

# Check expert knowledge related to pisos
cur.execute("""
    SELECT contexto_tags, producto_recomendado, producto_desestimado, nota_comercial
    FROM agent_expert_knowledge 
    WHERE activo = true 
      AND (contexto_tags ILIKE '%piso%' OR nota_comercial ILIKE '%piso%')
    LIMIT 10
""")
print(f"\nExpert knowledge for pisos:")
for row in cur.fetchall():
    print(f"  tags={row[0]}, rec={row[1]}, evitar={row[2]}, nota={row[3][:100]}")

# Check how many chunks are guide-type vs ficha-type
cur.execute("""
    SELECT 
        COALESCE(metadata->>'document_scope', 'unknown') as scope,
        COALESCE(metadata->>'tipo_documento', 'unknown') as tipo,
        COUNT(1) 
    FROM agent_technical_doc_chunk 
    GROUP BY scope, tipo 
    ORDER BY COUNT(1) DESC 
    LIMIT 10
""")
print(f"\nChunks by scope/tipo:")
for row in cur.fetchall():
    print(f"  {row[0]}/{row[1]}: {row[2]}")

conn.close()
print("\nDone.")
