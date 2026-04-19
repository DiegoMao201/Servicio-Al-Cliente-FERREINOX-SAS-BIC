import psycopg2, json
conn = psycopg2.connect('postgresql://postgres:o5S3X9VIYcbBWqd525hqT24UhYAc8AdjtevyHtlZHhGxJkfMQVZXReCTxkcjSOAX@192.81.216.49:3000/postgres')
cur = conn.cursor()
cur.execute("""
    SELECT canonical_family,
           profile_json->'commercial_context'->'recommended_uses' as uses,
           profile_json->'commercial_context'->'summary' as summary,
           profile_json->'solution_guidance'->'decision_clues' as clues
    FROM agent_technical_profile
    WHERE extraction_status='ready' AND canonical_family ILIKE '%altas temp%905%'
""")
for r in cur.fetchall():
    print(f'=== {r[0]} ===')
    print(f'  uses: {json.dumps(r[1], ensure_ascii=False, indent=2) if r[1] else "NULL"}')
    print(f'  summary: {json.dumps(r[2], ensure_ascii=False) if r[2] else "NULL"}')
    print(f'  clues: {json.dumps(r[3], ensure_ascii=False, indent=2) if r[3] else "NULL"}')
cur.close()
conn.close()
