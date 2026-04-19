import psycopg2, json
DATABASE_URL = 'postgresql://postgres:o5S3X9VIYcbBWqd525hqT24UhYAc8AdjtevyHtlZHhGxJkfMQVZXReCTxkcjSOAX@192.81.216.49:3000/postgres'
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute("""
    SELECT canonical_family, 
           profile_json->'surface_targets' as st,
           profile_json->'restricted_surfaces' as rs,
           profile_json->'solution_guidance'->'recommended_surfaces' as rec_surf,
           profile_json->'solution_guidance'->'restricted_surfaces' as rest_surf,
           profile_json->'commercial_context'->'compatible_surfaces' as compat,
           profile_json->'commercial_context'->'incompatible_surfaces' as incompat
    FROM agent_technical_profile
    WHERE extraction_status = 'ready'
    AND canonical_family IN (
        'PINTUCO ALTAS TEMPERATURAS', 'PINTUCO VINILTEX ADVANCED', 
        'PINTUCO KORAZA', 'PINTUCO CORROTEC', 'PINTUCO WASH PRIMER', 
        'PINTUCO PINTULUX 3 EN 1', 'ACRILICA MANTENIMIENTO ES', 
        'ACRILICA BASE AGUA UDA600 ES', 'PINTUCO ACRILICA PARA MANTENIMIENTO'
    )
""")
for row in cur.fetchall():
    print(f'=== {row[0]} ===')
    for i, label in enumerate(['surface_targets', 'restricted_surfaces', 'recommended_surfaces(guide)', 'restricted_surfaces(guide)', 'compatible_surfaces', 'incompatible_surfaces'], 1):
        val = row[i]
        if val:
            print(f'  {label}: {json.dumps(val, ensure_ascii=False)}')
    print()

# Also count how many profiles have surface metadata
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE profile_json->'surface_targets' IS NOT NULL AND jsonb_array_length(profile_json->'surface_targets') > 0) as has_st,
        COUNT(*) FILTER (WHERE profile_json->'restricted_surfaces' IS NOT NULL AND jsonb_array_length(profile_json->'restricted_surfaces') > 0) as has_rs,
        COUNT(*) FILTER (WHERE profile_json->'solution_guidance'->'recommended_surfaces' IS NOT NULL) as has_rec,
        COUNT(*) FILTER (WHERE profile_json->'solution_guidance'->'restricted_surfaces' IS NOT NULL) as has_rest
    FROM agent_technical_profile
    WHERE extraction_status = 'ready'
""")
row = cur.fetchone()
print(f"=== COBERTURA METADATA SUPERFICIES ===")
print(f"  Total perfiles ready: {row[0]}")
print(f"  Con surface_targets: {row[1]}")
print(f"  Con restricted_surfaces: {row[2]}")
print(f"  Con recommended_surfaces (guide): {row[3]}")
print(f"  Con restricted_surfaces (guide): {row[4]}")

cur.close()
conn.close()
