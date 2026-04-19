import psycopg2, json
conn = psycopg2.connect('postgresql://postgres:o5S3X9VIYcbBWqd525hqT24UhYAc8AdjtevyHtlZHhGxJkfMQVZXReCTxkcjSOAX@192.81.216.49:3000/postgres')
cur = conn.cursor()

for pattern in ['%altas temp%', '%viniltex adv%', '%koraza%', '%pintulux%']:
    cur.execute("""
        SELECT canonical_family, 
               profile_json->'surface_targets',
               profile_json->'restricted_surfaces',
               profile_json->'commercial_context'->'not_recommended_for'
        FROM agent_technical_profile
        WHERE extraction_status='ready' AND canonical_family ILIKE %s
    """, (pattern,))
    for r in cur.fetchall():
        print(f'{r[0]}')
        print(f'  targets: {json.dumps(r[1], ensure_ascii=False) if r[1] else "NULL"}')
        print(f'  restricted: {json.dumps(r[2], ensure_ascii=False) if r[2] else "NULL"}')
        print(f'  not_recommended_for: {json.dumps(r[3], ensure_ascii=False) if r[3] else "NULL"}')
        print()

cur.close()
conn.close()
